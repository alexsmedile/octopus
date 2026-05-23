"""`octopus diagnose` — collect a redacted bug-report bundle.

Gathers version, platform, config, index stats, log tail. Writes to a zip
in cwd by default, or prints to stdout with --no-zip.

All `$HOME` paths are redacted to `~/` so users can share the payload safely.
"""

from __future__ import annotations

import json
import platform
import sys
import zipfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from octopus import __spec_version__, __version__
from octopus.config import SYSTEM_CONFIG_PATH, load_config
from octopus.core.logging import default_log_path
from octopus.db.connection import default_db_path, get_db

LOG_TAIL_LINES = 500


def _redact(s: str) -> str:
    """Replace $HOME prefix with `~/` so payload is shareable."""
    home = str(Path.home())
    return s.replace(home, "~")


def _redact_path(p: Path | None) -> str | None:
    return _redact(str(p)) if p is not None else None


def _read_log_tail(path: Path, lines: int = LOG_TAIL_LINES) -> list[str]:
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            buf = fh.readlines()
    except OSError:
        return []
    return [_redact(line.rstrip("\n")) for line in buf[-lines:]]


def _index_stats(db_path: Path) -> dict:
    if not db_path.is_file():
        return {"exists": False}
    try:
        conn = get_db(db_path)
    except Exception as exc:
        return {"exists": True, "error": str(exc)}
    try:
        tables = ("activities", "tasks", "sessions")
        counts: dict[str, int] = {}
        for t in tables:
            row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            counts[t] = int(row[0])
        size_bytes = db_path.stat().st_size
        return {
            "exists": True,
            "path": _redact_path(db_path),
            "size_bytes": size_bytes,
            "row_counts": counts,
        }
    except Exception as exc:
        return {"exists": True, "error": str(exc)}
    finally:
        conn.close()


def _config_dump() -> dict:
    cfg = load_config()
    raw = ""
    if SYSTEM_CONFIG_PATH.is_file():
        try:
            raw = _redact(SYSTEM_CONFIG_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            raw = f"<read error: {exc}>"
    return {
        "system_config_path": _redact_path(SYSTEM_CONFIG_PATH),
        "system_config_raw": raw,
        "resolved": {
            "storage_mode": cfg.storage_mode,
            "roots": [_redact_path(p) for p in cfg.roots],
            "session_stale_warn_days": cfg.session_stale_warn_days,
            "session_prune_days": cfg.session_prune_days,
            "slug_max_length": cfg.max_length,
        },
    }


def collect_diagnostics() -> dict:
    """Build the diagnostic payload as a plain dict (JSON-safe)."""
    log_path = default_log_path()
    db_path = default_db_path()
    return OrderedDict(
        [
            ("octopus_version", __version__),
            ("spec_version", __spec_version__),
            ("collected_at", datetime.now().isoformat(timespec="seconds")),
            (
                "python",
                {
                    "version": sys.version.split()[0],
                    "implementation": platform.python_implementation(),
                    "executable": _redact_path(Path(sys.executable)),
                },
            ),
            (
                "platform",
                {
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                },
            ),
            (
                "paths",
                {
                    "log": _redact_path(log_path),
                    "log_exists": log_path.is_file(),
                    "db": _redact_path(db_path),
                    "db_exists": db_path.is_file(),
                    "home": "~",
                },
            ),
            ("config", _config_dump()),
            ("index", _index_stats(db_path)),
            ("log_tail_lines", LOG_TAIL_LINES if log_path.is_file() else 0),
        ]
    )


def format_summary(payload: dict) -> str:
    """Human-readable summary for stdout."""
    lines = [
        f"octopus version : {payload['octopus_version']}",
        f"spec version   : {payload['spec_version']}",
        f"collected at   : {payload['collected_at']}",
        f"python         : {payload['python']['version']} ({payload['python']['implementation']})",
        f"platform       : {payload['platform']['system']} {payload['platform']['release']} "
        f"({payload['platform']['machine']})",
        "",
        "paths:",
        f"  log  : {payload['paths']['log']} (exists={payload['paths']['log_exists']})",
        f"  db   : {payload['paths']['db']} (exists={payload['paths']['db_exists']})",
        "",
        "config:",
        f"  system config : {payload['config']['system_config_path']}",
        f"  storage_mode  : {payload['config']['resolved']['storage_mode']}",
        f"  roots         : {payload['config']['resolved']['roots'] or '(none configured)'}",
        f"  prune_days    : {payload['config']['resolved']['session_prune_days']}",
        "",
        "index:",
    ]
    idx = payload["index"]
    if not idx.get("exists"):
        lines.append("  (no index db yet)")
    elif "error" in idx:
        lines.append(f"  error: {idx['error']}")
    else:
        lines.append(f"  path        : {idx['path']}")
        lines.append(f"  size_bytes  : {idx['size_bytes']}")
        for t, n in idx["row_counts"].items():
            lines.append(f"  {t:12s}: {n}")
    return "\n".join(lines)


def default_out_path() -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return Path.cwd() / f"octopus-diagnose-{stamp}.zip"


def write_zip(payload: dict, out_path: Path, log_tail: list[str]) -> Path:
    """Write payload + log tail into a zip at `out_path`. Returns the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnose.json", json.dumps(payload, indent=2, default=str))
        if log_tail:
            zf.writestr("octopus.log.tail", "\n".join(log_tail) + "\n")
    return out_path
