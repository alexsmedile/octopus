---
status: queued
priority: low
owner: alex
updated: 2026-05-23
summary: "Clean up ruff debt deferred from #11 — 10 suppressed rules, 96 original violations, ~70 remaining after safe auto-fixes."
related:
  - 11-distribution-pipx
gates:
  - 11-distribution-pipx
---

# Lint cleanup

## Goal

Re-tighten ruff config to the original strict set (`E, F, I, B, UP, SIM`, no per-rule ignores) by fixing the violations rather than suppressing them. Restore `cli/pyproject.toml` `[tool.ruff.lint]` to a single `select = ...` line with no `ignore`.

## Why

During #11 (distribution + CI), the first GitHub Actions run would have failed on 96 pre-existing lint issues. To unblock shipping v0.1.0, ruff was loosened with 10 documented per-rule ignores. The shipped wheel and runtime behavior are unaffected — but the lint debt should not stay.

One rule in particular (`B904` — raise-without-from inside except) is more than cosmetic: it makes tracebacks lose the original cause, which hurts debuggability for users hitting bugs we'd diagnose via `octopus diagnose`. The other rules are stylistic.

## Suppressed rules to address

Inventory at close-of-#11 (post auto-fix):

| Rule | Count | Type | Notes |
|---|---|---|---|
| `E501` | 36 | line-too-long | Mostly in tests. Line-wrap or accept `# noqa: E501` on data-table literals. |
| `B904` | 12 | raise-without-from | **Debuggability — handle deliberately.** Each site decides: `raise X from exc` (chain) or `raise X from None` (suppress). |
| `E402` | 9 | import-not-at-top | `cli.py` uses deferred imports inside command bodies for startup speed. Either move them top-of-file (measure the cost) or add inline `# noqa: E402` with a one-line reason. |
| `F841` | 5 | unused-variable | Delete or rename to `_`. |
| `SIM108` | 2 | if-else→ternary | Apply the ternary. |
| `B008` | 1 | function-call-in-default-arg | Inspect — usually move into the body. |
| `B017` | 1 | assert-raises-Exception | Narrow the exception type in the test. |
| `SIM105` | 1 | suppressible-exception | Apply `contextlib.suppress`. |
| `UP028` | 1 | yield-in-for-loop | Apply `yield from`. |
| `UP038` | 1 | non-pep604-isinstance | Apply `A \| B` form. |

Total: ~69 violations remaining after #11's safe auto-fixes.

## Approach

1. **Audit pass** — run `ruff check src tests --statistics` against current code, refresh the inventory above. Numbers may shift if other work landed in between.
2. **B904 first** — 12 sites, each touched deliberately. Default: `raise X from exc` everywhere it's an internal re-raise; `from None` only where chaining adds noise (e.g. CLI validation errors users see).
3. **E402 audit** — for each deferred import in `cli.py`, decide: keep deferred (add `# noqa: E402  # deferred for startup speed`) or move top-of-file. Probably worth profiling once with `python -X importtime` before deciding.
4. **Stylistic batch** — `SIM108`, `SIM105`, `UP028`, `UP038`, `B017` — apply mechanically.
5. **E501 + F841 in tests** — line-wrap where reasonable, `# noqa: E501` for tabular data fixtures, delete unused vars.
6. **Restore strict ruff config** — remove `ignore = [...]` and per-file ignores from `cli/pyproject.toml`.
7. **CI verify** — push branch, watch CI go green with the strict config.

## Deliverables

- `cli/pyproject.toml` `[tool.ruff.lint]` reduced to a single `select = ["E", "F", "I", "B", "UP", "SIM"]` line, no ignores, no per-file overrides.
- All test suite still passing.
- Optional: one-line note in CHANGELOG under a future v0.1.1 or v0.2.0 entry.

## Out of scope

- Adding new ruff rules beyond the original set.
- Switching to a different linter (mypy, pyright, etc).
- Type-annotation cleanup (separate concern).
- Pre-commit hook config (lives in tooling, not this request).

## Risks

- **B904 changes traceback shape** — if any user has scripted around the current (lossy) traceback, the chained form will break that. Very unlikely; flag in commit message anyway.
- **Deferred-import removal could slow startup** — measure before changing. `python -X importtime octopus --version` should stay under 200ms on a warm cache.
- **Per-file ignores creep back** — be honest about which sites genuinely need a `# noqa` and document the reason inline. Avoid blanket suppressions.

## Estimate

30–45 minutes focused work, plus one CI cycle to verify.
