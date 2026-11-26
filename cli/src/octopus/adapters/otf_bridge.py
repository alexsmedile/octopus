"""Thin Octopus adapters delegating cloud sync to the upstream `otf` CLI (JSON contract).

Architecture decision:
- `otf` owns schemas, fixtures, lossless Markdown I/O, and all cloud tracker APIs
  (GitHub Issues + Projects V2, Plane, Linear).
- `octopus` owns daily UX, TUI, SQLite index, sessions/handoffs, and macOS Reminders,
  wrapping `otf` via its stable JSON CLI so cloud API code is maintained in one place.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    ExternalTask,
    PullResult,
    PushResult,
)
from octopus.adapters.journal import read_journal
from octopus.config import load_adapter_config
from octopus.core.models import Task
from octopus.fs.io import write_task

OtfRunner = Callable[[list[str]], dict[str, Any]]

_OTF_STATE_TO_BUCKET = {
    "inactive": "backlog",
    "active": "now",
    "closed": "done",
}


def _default_otf_runner(args: list[str]) -> dict[str, Any]:
    exe = shutil.which("otf")
    if not exe:
        raise RuntimeError("`otf` CLI not found on PATH; install/link ~/code/libs/otf")
    proc = subprocess.run([exe, *args], capture_output=True, text=True, check=False)
    payload_text = (proc.stdout or proc.stderr or "").strip()
    try:
        data = json.loads(payload_text) if payload_text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON output from otf ({proc.returncode}): {payload_text}") from exc
    if proc.returncode != 0 or data.get("ok") is False:
        raise RuntimeError(str(data.get("error") or payload_text or f"otf exited {proc.returncode}"))
    return data


def _otf_dict_to_external_task(item: dict[str, Any], source_group: str) -> ExternalTask:
    refs = item.get("external_refs") or []
    source_ref = next((r for r in refs if isinstance(r, dict) and r.get("role") == "source"), None)
    external_id = str(source_ref.get("id") if source_ref else item.get("id", ""))

    state = str(item.get("state", "active"))
    outcome = item.get("outcome")
    bucket = "dropped" if state == "closed" and outcome in {"cancelled", "duplicate"} else _OTF_STATE_TO_BUCKET.get(state, "backlog")
    impediment = item.get("impediment")
    reason = item.get("impediment_reason")

    def _d(val: Any) -> date | None:
        return date.fromisoformat(str(val)[:10]) if val else None

    priority = item.get("priority")
    assignees = item.get("assignees") or []

    return ExternalTask(
        external_id=external_id,
        title=str(item.get("title", "")),
        body=item.get("description"),
        suggested_bucket=bucket,
        suggested_stage=item.get("stage"),
        suggested_issue=impediment if impediment in {"blocked", "waiting"} else None,
        suggested_blocked_by=str(reason) if impediment == "blocked" and reason else None,
        suggested_waiting_for=str(reason) if impediment == "waiting" and reason else None,
        suggested_due=_d(item.get("due")),
        suggested_scheduled=_d(item.get("scheduled")),
        suggested_priority=priority if priority in {"low", "high", "urgent"} else None,
        suggested_owner=str(assignees[0]) if assignees else None,
        suggested_kind=item.get("kind"),
        suggested_tags=list(item.get("labels") or []),
        source_group=source_group,
    )


class _BaseOtfBridgeAdapter:
    name: str
    provider: str
    capabilities: set[Capability]

    def __init__(self, runner: OtfRunner | None = None) -> None:
        self._run = runner or _default_otf_runner

    def status(self) -> AdapterStatus:
        journal = read_journal(self.name)
        has_otf = shutil.which("otf") is not None
        return AdapterStatus(
            name=self.name,
            healthy=has_otf,
            last_pull=journal.last_pull,
            last_push=journal.last_push,
            error=None if has_otf else "`otf` CLI not found on PATH",
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        groups = data.get("groups")
        if groups is not None and not isinstance(groups, list):
            return [f"{self.name}.groups must be a list of target identifiers"]
        return []

    def list_groups(self) -> list[str]:
        cfg = load_adapter_config(self.name)
        return [str(g) for g in (cfg.get("groups") or [])]

    def _pull_one(self, target: str, extra_args: list[str]) -> list[ExternalTask]:
        with tempfile.TemporaryDirectory(prefix=f"octo-otf-{self.provider}-") as td:
            self._run(["pull", f"{self.provider}:{target}", "--dir", td, *extra_args])
            listed = self._run(["list", td])
            return [_otf_dict_to_external_task(t, target) for t in (listed.get("tasks") or [])]

    def pull(self, groups: list[str] | None = None) -> PullResult:
        targets = groups if groups is not None else self.list_groups()
        if not targets:
            return PullResult(errors=[f"No target groups configured for '{self.name}'"])
        cfg = load_adapter_config(self.name)
        extra_args: list[str] = []
        if self.provider == "github" and cfg.get("projects", True):
            extra_args.append("--projects")
        if self.provider == "plane" and cfg.get("base_url"):
            extra_args.extend(["--base-url", str(cfg["base_url"])])

        tasks: list[ExternalTask] = []
        errors: list[str] = []
        for target in targets:
            try:
                tasks.extend(self._pull_one(target, extra_args))
            except Exception as exc:
                errors.append(f"{target}: {exc}")
        return PullResult(tasks=tasks, errors=errors)

    def peek(self, groups: list[str] | None = None) -> PullResult:
        return self.pull(groups)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        res = self.pull(groups)
        q = query.lower()
        filtered = [t for t in res.tasks if q in t.title.lower() or (t.body and q in t.body.lower())]
        return PullResult(tasks=filtered, errors=res.errors)

    def push(self, task: Task) -> PushResult:
        return PushResult(error=f"push not supported for '{self.name}'")


class OtfGitHubAdapter(_BaseOtfBridgeAdapter):
    """GitHub Issues + Projects V2 adapter backed by `otf pull/push github:...`."""

    name = "github"
    provider = "github"
    capabilities = {Capability.PULL, Capability.PUSH}

    def push(self, task: Task, *, repo: str | None = None, project: int | None = None, apply: bool = True) -> PushResult:
        cfg = load_adapter_config(self.name)
        target_repo = repo or (cfg.get("groups") or [None])[0]
        if not target_repo:
            return PushResult(error="No target GitHub repo configured for 'github' adapter")
        proj_num = project if project is not None else cfg.get("project")

        with tempfile.TemporaryDirectory(prefix="octo-otf-push-") as td:
            tmp_file = Path(td) / f"{task.slug or 'task'}.md"
            write_task(tmp_file, task, "", format="otf")
            args = ["push", str(tmp_file), f"github:{target_repo}"]
            if proj_num is not None:
                args.extend(["--project", str(proj_num)])
            if apply:
                args.append("--apply")
            try:
                res = self._run(args)
                ref = res.get("issueUrl") or res.get("issueNodeId")
                return PushResult(ref=str(ref) if ref else None)
            except Exception as exc:
                return PushResult(error=str(exc))


class OtfPlaneAdapter(_BaseOtfBridgeAdapter):
    """Plane Work Items adapter backed by `otf pull plane:<workspace>/<project-id>`."""

    name = "plane"
    provider = "plane"
    capabilities = {Capability.PULL}
