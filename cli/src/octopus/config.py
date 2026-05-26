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
    # Promotion providers (D48). Default ships with `spectacular` only.
    provider_default: str = "spectacular"
    provider_chips: dict[str, str] = field(
        default_factory=lambda: {"spectacular": "spec"}
    )
    spectacular_auto_number: bool = True
    # UI persistence — request #44. Opt-in for L3 (disk-backed view state).
    # L1 + L2 (in-memory cursor + last-active tab) are always-on regardless.
    restore_last_view: bool = False


# Registered providers — extend here when new adapters land.
REGISTERED_PROVIDERS = {"spectacular"}


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

    providers_block = data.get("providers", {})
    default_provider = providers_block.get("default", base.provider_default)
    if default_provider not in REGISTERED_PROVIDERS:
        default_provider = base.provider_default
    chips_block = providers_block.get("chips", {})
    chips = dict(base.provider_chips)
    for provider, chip in chips_block.items():
        if not isinstance(chip, str):
            continue
        if not chip.isascii() or len(chip) > 6 or not chip:
            continue
        if provider not in REGISTERED_PROVIDERS:
            continue
        chips[provider] = chip
    spec_block = providers_block.get("spectacular", {})
    auto_number = bool(spec_block.get("auto_number", base.spectacular_auto_number))

    ui_block = data.get("ui", {})
    restore_last_view = bool(ui_block.get("restore_last_view", base.restore_last_view))

    return Config(
        storage_mode=storage_mode,
        noise_words=noise_words,
        max_length=max_length,
        roots=roots,
        session_stale_warn_days=stale_warn,
        session_prune_days=prune_days,
        provider_default=default_provider,
        provider_chips=chips,
        spectacular_auto_number=auto_number,
        restore_last_view=restore_last_view,
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


# ── Adapter config (D58, hybrid layout) ─────────────────────────────


def bridges_dir() -> Path:
    """`~/.config/octopus/bridges/` — per-adapter content files."""
    return SYSTEM_CONFIG_DIR / "bridges"


def adapter_config_path(name: str) -> Path:
    """Per-adapter TOML path: `bridges/<name>.toml`."""
    return bridges_dir() / f"{name}.toml"


def load_adapter_config(name: str) -> dict:
    """Read `bridges/<name>.toml`. Missing file → empty dict."""
    return _load_toml(adapter_config_path(name))


def write_adapter_config(name: str, data: dict) -> None:
    """Persist `bridges/<name>.toml` as TOML.

    Hand-rolled writer (no `tomli-w` dep). Supports: strings, ints, bools,
    lists-of-strings. Adapter validators are expected to enforce key types,
    so we don't need general-purpose serialization.
    """
    bridges_dir().mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k} = {v}")
        elif isinstance(v, list):
            items = ", ".join(f'"{x}"' for x in v)
            lines.append(f"{k} = [{items}]")
        else:
            lines.append(f'{k} = "{v}"')
    adapter_config_path(name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_adapter_enabled(name: str) -> bool:
    """Read `[adapters.<name>] enabled` from the main config. Missing = False."""
    data = _load_toml(SYSTEM_CONFIG_PATH)
    return bool(data.get("adapters", {}).get(name, {}).get("enabled", False))


def set_adapter_enabled(name: str, enabled: bool) -> None:
    """Flip `[adapters.<name>] enabled` in the main config."""
    data = _read_system_config_raw()
    adapters = data.setdefault("adapters", {})
    adapters.setdefault(name, {})["enabled"] = bool(enabled)
    _write_full_system_config(data)


def list_enabled_adapters() -> list[str]:
    """Sorted list of adapter names with `enabled = true` in main config."""
    data = _load_toml(SYSTEM_CONFIG_PATH)
    adapters = data.get("adapters", {}) or {}
    return sorted(
        name for name, cfg in adapters.items()
        if isinstance(cfg, dict) and cfg.get("enabled") is True
    )


def list_all_configured_adapters() -> list[str]:
    """Every adapter that appears in either main config OR has a bridges file."""
    names = set()
    data = _load_toml(SYSTEM_CONFIG_PATH)
    for n in (data.get("adapters", {}) or {}):
        names.add(n)
    bd = bridges_dir()
    if bd.is_dir():
        for f in bd.glob("*.toml"):
            names.add(f.stem)
    return sorted(names)


def _write_full_system_config(data: dict) -> None:
    """Extended writer that handles [adapters.*] sections in addition to
    what `_write_system_config` covers.

    Existing sections (storage, slug, roots, sessions, providers) are still
    handled by `_write_system_config`; we delegate to it and append adapter
    sections at the end.
    """
    # Reuse the existing writer for the canonical sections.
    _write_system_config(data)
    # Then append [adapters.*] sections that the original writer doesn't know about.
    adapters = data.get("adapters") or {}
    if not adapters:
        return
    existing = SYSTEM_CONFIG_PATH.read_text(encoding="utf-8") if SYSTEM_CONFIG_PATH.exists() else ""
    extra_lines: list[str] = []
    for name, cfg in adapters.items():
        if not isinstance(cfg, dict):
            continue
        extra_lines.append(f"[adapters.{name}]")
        for k, v in cfg.items():
            if isinstance(v, bool):
                extra_lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, int):
                extra_lines.append(f"{k} = {v}")
            elif isinstance(v, list):
                items = ", ".join(f'"{x}"' for x in v)
                extra_lines.append(f"{k} = [{items}]")
            else:
                extra_lines.append(f'{k} = "{v}"')
        extra_lines.append("")
    if extra_lines:
        SYSTEM_CONFIG_PATH.write_text(existing.rstrip() + "\n\n" + "\n".join(extra_lines), encoding="utf-8")
