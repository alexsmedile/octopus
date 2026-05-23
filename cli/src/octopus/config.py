"""Config loader per SCHEMA-CONFIG.md.

Precedence: per-activity (.octopus/config.toml) overrides system-wide
(~/.config/octopus/config.toml) overrides shipped defaults.

Implemented keys in v1:
- [storage] mode
- [slug] noise_words, max_length
- [roots] paths
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from octopus.core.slug import DEFAULT_MAX_LENGTH, DEFAULT_NOISE_WORDS

SYSTEM_CONFIG_DIR = Path(
    os.environ.get("OCTOPUS_CONFIG_HOME", Path.home() / ".config" / "octopus")
)
SYSTEM_CONFIG_PATH = SYSTEM_CONFIG_DIR / "config.toml"


@dataclass
class Config:
    storage_mode: str = "folders"
    noise_words: frozenset[str] = field(default_factory=lambda: DEFAULT_NOISE_WORDS)
    max_length: int = DEFAULT_MAX_LENGTH
    # Roots are stored as Path objects after expansion; default empty per
    # SCHEMA-INDEX.md §4.6 — user must `octopus config root add` to opt in.
    roots: list[Path] = field(default_factory=list)
    # Session thresholds (request 04, D41).
    # `stale_warn_days` — surface a warning when a session has been open with
    # no append activity for longer than this. `prune_days` — default for the
    # auto-close threshold used by `octopus session prune`. Both overridable
    # in `[sessions]` in `~/.config/octopus/config.toml`.
    session_stale_warn_days: int = 7
    session_prune_days: int = 14


def _load_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def _expand(p: str | Path) -> Path:
    return Path(p).expanduser().resolve()


def _merge(base: Config, data: dict) -> Config:
    storage_mode = data.get("storage", {}).get("mode", base.storage_mode)
    if storage_mode not in {"folders", "fields"}:
        storage_mode = base.storage_mode

    slug_block = data.get("slug", {})
    noise = slug_block.get("noise_words")
    noise_words = frozenset(noise) if noise else base.noise_words
    max_length = int(slug_block.get("max_length", base.max_length))

    roots_block = data.get("roots", {})
    raw_paths = roots_block.get("paths")
    if raw_paths is None:
        roots = base.roots
    else:
        roots = [_expand(p) for p in raw_paths]

    sessions_block = data.get("sessions", {})
    stale_warn = int(sessions_block.get("stale_warn_days", base.session_stale_warn_days))
    prune_days = int(sessions_block.get("prune_days", base.session_prune_days))

    return Config(
        storage_mode=storage_mode,
        noise_words=noise_words,
        max_length=max_length,
        roots=roots,
        session_stale_warn_days=stale_warn,
        session_prune_days=prune_days,
    )


def load_config(activity_octopus_dir: Path | None = None) -> Config:
    """Load merged config: defaults < system-wide < per-activity."""
    cfg = Config()
    cfg = _merge(cfg, _load_toml(SYSTEM_CONFIG_PATH))
    if activity_octopus_dir is not None:
        cfg = _merge(cfg, _load_toml(activity_octopus_dir / "config.toml"))
    return cfg


# ── Roots mutation (writes back to system config) ────────────────────


def _read_system_config_raw() -> dict:
    return _load_toml(SYSTEM_CONFIG_PATH)


def _write_system_config(data: dict) -> None:
    """Re-serialize the system config as TOML.

    We hand-write the file because tomllib is read-only and we don't want
    to pull tomli-w as a hard dep for the walking-skeleton stage.
    """
    SYSTEM_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    storage = data.get("storage")
    if storage:
        lines.append("[storage]")
        for k, v in storage.items():
            lines.append(f'{k} = "{v}"')
        lines.append("")
    slug = data.get("slug")
    if slug:
        lines.append("[slug]")
        for k, v in slug.items():
            if isinstance(v, list):
                items = ", ".join(f'"{x}"' for x in v)
                lines.append(f"{k} = [{items}]")
            elif isinstance(v, int):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    roots = data.get("roots")
    if roots is not None:
        lines.append("[roots]")
        paths = roots.get("paths", [])
        if paths:
            items = ", ".join(f'"{p}"' for p in paths)
            lines.append(f"paths = [{items}]")
        else:
            lines.append("paths = []")
        lines.append("")
    sessions = data.get("sessions")
    if sessions:
        lines.append("[sessions]")
        for k, v in sessions.items():
            if isinstance(v, int):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    SYSTEM_CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")


def list_roots() -> list[str]:
    """Return the configured roots as strings (un-expanded, as stored)."""
    data = _read_system_config_raw()
    return list(data.get("roots", {}).get("paths", []))


def add_root(path: str) -> tuple[bool, str]:
    """Append a root to the system config.

    Returns (added, message). `added=False` if duplicate.
    """
    data = _read_system_config_raw()
    roots = data.setdefault("roots", {})
    paths = roots.setdefault("paths", [])
    if path in paths:
        return False, f"already configured: {path}"
    paths.append(path)
    _write_system_config(data)
    return True, f"added: {path}"


def remove_root(path: str) -> tuple[bool, str]:
    """Remove a root from the system config.

    Returns (removed, message). `removed=False` if not present.
    """
    data = _read_system_config_raw()
    paths = data.get("roots", {}).get("paths", [])
    if path not in paths:
        return False, f"not configured: {path}"
    paths.remove(path)
    data["roots"]["paths"] = paths
    _write_system_config(data)
    return True, f"removed: {path}"
