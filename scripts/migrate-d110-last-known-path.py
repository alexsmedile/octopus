#!/usr/bin/env python3
"""
migrate-d110-last-known-path.py — fleet migration for Octopus D110.

Moves `last_known_path` out of every indexed activity's `activity.md`
(committable, machine-portable) into `.octopus/config.local.toml`
(gitignored, machine-local), and ensures the local file is gitignored.

Why: an absolute path in activity.md leaks `/Users/<you>/...` into git
history and is wrong on every other machine. D110 made the path
machine-local; this script applies that retroactively to activities
indexed before D110 (or never re-written since).

Discovery: reads activity paths from the Octopus SQLite index, filtering
out pytest temp fixtures and non-absolute rows.

DRY-RUN BY DEFAULT. Pass --apply to actually write. Never deletes.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path.home() / ".local/share/octopus/index.db"
LOCAL_FILE = "config.local.toml"
IGNORE_LINE = ".octopus/config.local.toml"
# Paths we never touch: pytest temp dirs and OS temp.
EXCLUDE_PREFIXES = ("/private/tmp/", "/private/var/folders/", "/tmp/")

# Matches a `last_known_path:` frontmatter line (any value), whole line.
LKP_RE = re.compile(r"^last_known_path:.*\n?", re.MULTILINE)


def discover(db_path: Path) -> list[tuple[str, Path]]:
    """Return [(id, abs_path)] of real activities from the index."""
    if not db_path.exists():
        sys.exit(f"index DB not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT id, path FROM activities ORDER BY path").fetchall()
    conn.close()
    out: list[tuple[str, Path]] = []
    for aid, path in rows:
        if not path or path == "." or not path.startswith("/"):
            continue  # relative / sentinel rows — skip
        if path.startswith(EXCLUDE_PREFIXES):
            continue  # pytest / temp fixtures
        out.append((aid, Path(path)))
    return out


def is_git_repo(folder: Path) -> bool:
    p = folder
    for _ in range(40):
        if (p / ".git").exists():
            return True
        if p.parent == p:
            return False
        p = p.parent
    return False


def gitignore_for(folder: Path) -> Path:
    """The .gitignore at the git root (or folder root if no repo)."""
    p = folder
    for _ in range(40):
        if (p / ".git").exists():
            return p / ".gitignore"
        if p.parent == p:
            break
        p = p.parent
    return folder / ".gitignore"


def plan_one(aid: str, folder: Path) -> dict:
    """Compute the per-activity action plan. No writes."""
    octo = folder / ".octopus"
    activity_md = octo / "activity.md"
    local_toml = octo / LOCAL_FILE
    plan = {
        "id": aid,
        "folder": folder,
        "exists": activity_md.is_file(),
        "lkp_value": None,
        "strip_line": False,
        "write_local": False,
        "add_ignore": False,
        "is_git": is_git_repo(folder),
        "gitignore": gitignore_for(folder),
        "notes": [],
    }
    if not activity_md.is_file():
        plan["notes"].append("activity.md missing — path stale in index, SKIP")
        return plan

    text = activity_md.read_text(encoding="utf-8")
    m = re.search(r"^last_known_path:\s*(.+?)\s*$", text, re.MULTILINE)
    if m:
        plan["lkp_value"] = m.group(1).strip()
        plan["strip_line"] = True

    # Determine the path to record locally: prefer the activity.md value,
    # else the current folder (which is where the index found it).
    recorded = plan["lkp_value"] or str(folder)
    plan["recorded_path"] = recorded

    if not local_toml.is_file():
        plan["write_local"] = True
    else:
        existing = local_toml.read_text(encoding="utf-8")
        if "last_known_path" not in existing:
            plan["write_local"] = True
            plan["notes"].append("config.local.toml exists but lacks last_known_path")

    # gitignore only matters inside a git repo
    if plan["is_git"]:
        gi = plan["gitignore"]
        if not gi.exists():
            plan["add_ignore"] = True
            plan["notes"].append("no .gitignore — will create")
        else:
            if IGNORE_LINE not in gi.read_text(encoding="utf-8"):
                plan["add_ignore"] = True
    else:
        plan["notes"].append("not a git repo — gitignore step N/A")

    if not (plan["strip_line"] or plan["write_local"] or plan["add_ignore"]):
        plan["notes"].append("already clean — nothing to do")
    return plan


def apply_one(plan: dict) -> None:
    folder: Path = plan["folder"]
    octo = folder / ".octopus"
    activity_md = octo / "activity.md"
    local_toml = octo / LOCAL_FILE

    if plan["write_local"]:
        local_toml.write_text(
            f'last_known_path = "{plan["recorded_path"]}"\n', encoding="utf-8"
        )

    if plan["strip_line"] and activity_md.is_file():
        text = activity_md.read_text(encoding="utf-8")
        new = LKP_RE.sub("", text, count=1)
        if new != text:
            activity_md.write_text(new, encoding="utf-8")

    if plan["add_ignore"] and plan["is_git"]:
        gi: Path = plan["gitignore"]
        block = (
            "\n# Octopus machine-local activity state (absolute paths) — D110\n"
            f"{IGNORE_LINE}\n"
        )
        if gi.exists():
            content = gi.read_text(encoding="utf-8")
            sep = "" if content.endswith("\n") else "\n"
            gi.write_text(content + sep + block, encoding="utf-8")
        else:
            gi.write_text(block.lstrip("\n"), encoding="utf-8")


def fmt_plan(plan: dict) -> str:
    acts = []
    if plan["strip_line"]:
        acts.append(f"strip last_known_path ({plan['lkp_value']})")
    if plan["write_local"]:
        acts.append(f"write {LOCAL_FILE}")
    if plan["add_ignore"]:
        acts.append("add .gitignore rule")
    action = " · ".join(acts) if acts else "—"
    notes = f"  [{'; '.join(plan['notes'])}]" if plan["notes"] else ""
    return f"  {plan['id']:<28} {action}{notes}\n      {plan['folder']}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="index.db path")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    args = ap.parse_args()

    activities = discover(args.db)
    plans = [plan_one(aid, folder) for aid, folder in activities]

    actionable = [p for p in plans if p["strip_line"] or p["write_local"] or p["add_ignore"]]
    clean = [p for p in plans if p not in actionable and p["exists"]]
    missing = [p for p in plans if not p["exists"]]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n=== Octopus D110 migration · {mode} ===")
    print(f"index: {args.db}")
    print(f"real activities: {len(activities)}  ·  actionable: {len(actionable)}  ·  "
          f"already-clean: {len(clean)}  ·  stale(missing activity.md): {len(missing)}\n")

    if actionable:
        print("WILL CHANGE:" if not args.apply else "CHANGED:")
        for p in actionable:
            print(fmt_plan(p))
            if args.apply:
                apply_one(p)
        print()

    if missing:
        print("STALE (skipped — index path has no activity.md on disk):")
        for p in missing:
            print(f"  {p['id']:<28} {p['folder']}")
        print()

    if clean:
        print(f"ALREADY CLEAN: {len(clean)} ({', '.join(p['id'] for p in clean)})\n")

    if not args.apply and actionable:
        print("Re-run with --apply to perform these changes. Nothing was written.")
    print("Tip: run `octopus reindex` afterwards so the index reflects the cleaned files.\n")


if __name__ == "__main__":
    main()
