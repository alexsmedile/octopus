---
updated: 2026-05-21
---

# Stack

Locked choices for the Octopus v1 implementation. Derived from PRD §8.

## Language & runtime

- **Python 3.11+** — single CLI package.
- Rationale: best TUI ecosystem (Textual), mature markdown/YAML, easiest Apple Reminders integration via `subprocess`, fastest iteration speed, consistent with vault tooling.

## Libraries

| Concern | Choice | Notes |
|---|---|---|
| CLI framework | **Typer** | Click under the hood, type-hint driven |
| TUI | **Textual** | The killer feature — mature, themable, mouse-aware |
| Frontmatter | **python-frontmatter** | YAML + body parsing |
| YAML | `PyYAML` | via python-frontmatter dependency |
| Config | **TOML** via stdlib `tomllib` | read-only stdlib; `tomli-w` for writes |
| Index | **SQLite** via stdlib `sqlite3` | no ORM |
| Web (v1.5) | **Textual `serve`** | reuse the TUI; FastAPI only if v2 justifies |
| Filesystem watch (v1.5) | **watchdog** | cross-platform fsevents wrapper |
| Apple Reminders | `osascript` / `shortcuts run` via `subprocess` | no third-party lib |
| Testing | **pytest** + `pytest-snapshot` | snapshot tests for CLI output |

## Packaging

- **`pyproject.toml`** (PEP 621), `setuptools` backend or `hatch` (TBD in request 11).
- Entry point: `octopus = octopus.cli:app`.
- Distribution v1: `pipx install octopus-cli`.
- Distribution v2: Homebrew tap; single-file binary via `shiv` or `pyinstaller`.

## Repo layout

```
octopus/                            # this folder, monorepo
├── cli/                            # Python package — the system tool
│   ├── pyproject.toml
│   ├── src/octopus/
│   │   ├── __main__.py
│   │   ├── cli.py                  # Typer entrypoint
│   │   ├── core/                   # Activity, Task, Session models
│   │   ├── fs/                     # filesystem walking + IO
│   │   ├── index/                  # SQLite indexer
│   │   ├── viewers/
│   │   │   ├── tui.py
│   │   │   └── web.py
│   │   ├── adapters/
│   │   │   ├── base.py             # Adapter protocol
│   │   │   ├── obsidian.py
│   │   │   └── reminders.py
│   │   └── config.py
│   └── tests/
│
├── plugin/                         # Claude Code plugin (markdown + shell only)
│   ├── .claude-plugin/plugin.json
│   ├── skills/octopus/SKILL.md
│   ├── agents/
│   ├── commands/octopus.md
│   └── hooks/on-session-start.sh
│
├── .spectacular/                   # this directory
├── _archive/                       # legacy design docs
├── PRD.md
└── README.md
```

## System paths

- Config: `~/.config/octopus/`
- Data / index / logs: `~/.local/share/octopus/`
- Cache (active sessions, transient): `~/.cache/octopus/`

## Non-choices (explicitly excluded for v1)

- Async (asyncio) — not needed at this scale.
- ORM (SQLAlchemy) — overkill for a derived index.
- Heavyweight web framework (Django, etc.) — out of scope.
- Cross-language reimplementation — spec is the lock-in, not the language.
