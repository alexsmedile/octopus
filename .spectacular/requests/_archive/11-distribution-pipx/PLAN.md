---
status: done
priority: medium
owner: alex
updated: 2026-05-23
activated: 2026-05-23
closed: 2026-05-23
closes_decision: D42
summary: "Package for pipx — pyproject finalized, octopus diagnose, logs, --version, basic CI."
related:
  - 08-plugin-claude-code
gates:
  - 03-index-sqlite
  - 04-sessions-memory
---

# Distribution — pipx

## Goal

Polish the v1 release into something `pipx install`-able: real `pyproject.toml` at 0.1.0, log infrastructure, `octopus diagnose` for bug reports, basic GitHub Actions CI, and a finalized README install section.

## Why

The plugin scaffold (#08) assumes `octopus` is on the user's `PATH`. Right now the only way to install is `pip install -e cli/` from a checkout — fine for the author, not for outside testers. This request makes the repo installable cleanly from a wheel (and eventually PyPI), and gives users a way to file useful bug reports via `octopus diagnose`.

## Current state (audited 2026-05-23)

- `cli/pyproject.toml` already 90% there: hatchling, deps, classifiers, scripts, urls all present.
- `octopus --version` **already wired** at `cli/src/octopus/cli.py:79` via `_version_callback`. No work needed.
- No `octopus diagnose` verb yet.
- No logging infrastructure — nothing writes to `~/.local/share/octopus/logs/`.
- No `.github/workflows/` directory — no CI.
- README has no installation section beyond "clone + pip install -e".

## Approach

Six discrete deliverables, smallest-to-largest:

1. **Version + classifier bump** — `0.0.1` → `0.1.0`, "Pre-Alpha" → "Alpha", verify `python -m build` produces clean wheel.
2. **Logging infrastructure** — `core/logging.py` sets up a rotating file logger at `~/.local/share/octopus/logs/octopus.log` (XDG-aware), INFO+ to file only, silent on stdout in normal operation. Wire from `cli.py` entry point.
3. **`octopus diagnose` verb** — collect `--version`, Python version, OS, config dump (redacted), recent log tail, index DB stats. Show contents before zipping. Write to `./octopus-diagnose-YYYY-MM-DD-HHMMSS.zip` in cwd.
4. **GitHub Actions CI** — two workflows:
   - `.github/workflows/test.yml` — runs `ruff check` + `pytest` on push/PR against `main`. Matrix: Python 3.11, 3.12, 3.13.
   - `.github/workflows/release.yml` — on tag `v*.*.*`, builds wheel + sdist, uploads as release artifacts (no PyPI publish yet — manual gate).
5. **Local wheel install test** — `python -m build`, then `pipx install ./dist/octopus_cli-0.1.0-py3-none-any.whl`. Verify `octopus --version` and `octopus where` work. Document the gotchas in README.
6. **README installation section** — pipx install + uninstall + upgrade instructions, plus a "from source" subsection.

## Deliverables

- `cli/pyproject.toml` updated to 0.1.0 + Alpha
- `cli/src/octopus/core/logging.py` (new)
- `cli/src/octopus/diagnose.py` (new) — verb registered under `octopus diagnose`
- `.github/workflows/test.yml` + `release.yml`
- `README.md` updated with installation section
- One eval: `pipx install ./dist/*.whl && octopus --version && octopus where` runs clean

## Out of scope

- PyPI publish (manual, post-#11).
- Homebrew tap.
- `octopus upgrade` self-updater.
- Signed releases / SBOM.
- Telemetry opt-in for diagnose payloads (currently local-only).

## Open questions

- Should `diagnose` zip the **whole** log file or only the last N lines? *Recommend: last 500 lines + roll into the zip alongside config dump, to keep payload small.*
- Should `release.yml` auto-publish to PyPI on tag? *Recommend: no, keep manual until after first external user installs cleanly.*
- Log rotation policy? *Recommend: 1 MB per file, 5 backups kept (`RotatingFileHandler`).*
- Should `diagnose` redact paths under `$HOME`? *Recommend: yes, replace with `~/` — paths can leak project names.*

## Risks

- **Wheel doesn't include `schema.sql`** — already addressed by `force-include` in pyproject; verify it survives the version bump.
- **Logging silently fills disk** — rotation policy mitigates; cap at 6 MB total (1 MB × 5 backups + active).
- **CI matrix flakiness on 3.13** — register_adapter fix should hold; if not, drop 3.13 from matrix and document.

