---
request: 35-textual-upgrade-to-8
updated: 2026-05-25
---

# Tasks — Textual 0.46 → 8.2.7

## Phase 1 — Dependency upgrade & triage

- [ ] Cut branch `feat/textual-8x` from `main` at `v0.9.7-rc1`
- [ ] Bump `cli/pyproject.toml` Textual constraint to `>=8.2,<9`
- [ ] `pip install -e .` and capture full dep tree (record Rich version)
- [ ] `pytest -x` — capture first failure
- [ ] `octopus tui` — capture first crash / visual regression
- [ ] Write `TRIAGE.md` in this folder: ordered list of failing call sites

## Phase 2 — Port

- [ ] `focus.py` + `board.py` — ListView events, key bindings, screen lifecycle
- [ ] `prompts.py` — ModalScreen lifecycle, `dismiss()` signatures
- [ ] `filter_bar.py` — same
- [ ] `overlay.py` — same
- [ ] `help.py` — same
- [ ] `header_bar.py` — `render() -> RenderResult`, reactive watch decorators
- [ ] `mascot.py` — verify rich-pixels still works with new Rich version (vendor wrapper or pin if not)
- [ ] `theme.tcss` — fix only what the new CSS parser rejects
- [ ] `pytest` — full suite green (603/603)

## Phase 3 — Validation gate

- [ ] `octopus tui` opens in Focus mode
- [ ] `H` cycles header modes (Full / Mid / Compact / Slim)
- [ ] Arrow keys + Tab — focus walks, bucket colors flip on focus
- [ ] `n` capture works
- [ ] `m` move works
- [ ] `f` finish works
- [ ] `p` pin works
- [ ] `d` drop works (confirm prompt)
- [ ] `b` block works (reason prompt)
- [ ] `B` unblock works
- [ ] `y` yank-slug copies to clipboard
- [ ] `g` go-to-slug works
- [ ] **`e` opens `$EDITOR`** — the point of this upgrade
- [ ] `,` toggles detail pane, scrolling works
- [ ] `?` opens help, Esc closes
- [ ] `/` filter modal works
- [ ] `2` → Board mode, `1` → Focus mode
- [ ] Mascot still animates (ambient interrupt within 90s)
- [ ] `q` quits cleanly
- [ ] Write `SMOKE.md` in this folder

## Phase 4 — Merge & release

- [ ] PR `feat/textual-8x` → `main`
- [ ] After merge: `/wrap-up` → tag `v0.9.8` (post-RC)
- [ ] Update `DECISIONS.md` with the Textual version pin
- [ ] Set `status: done` in PLAN.md frontmatter
