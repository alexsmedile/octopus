---
status: draft
updated: 2026-05-25
---

# Glyph audit — drift table

Spec: `.spectacular/specs/TUI-GLYPHS.md`. Code: `cli/src/octopus/tui/*.py`.

Verdict column:
- **OK** — spec and code agree.
- **SPEC-WINS** — code should change to match spec.
- **CODE-WINS** — spec should change to document the de-facto behavior.
- **NEW-LOCK** — undocumented glyph in use; needs a spec entry.
- **DECIDE** — needs Alessandro's call.

---

## A. Slot 1 — Status glyphs (per-task)

| Glyph | Spec meaning | Code usage | Color (code) | Color (spec) | Verdict |
|---|---|---|---|---|---|
| `·` | parked (backlog idle) | `icons.PARKED`; `status_glyph` returns for backlog+null progress | `#8A8D9A` dim grey | "dim grey" | OK |
| `○` | open / progress≈0 | `icons.OPEN`; `status_glyph` for next bucket / progress>0 | bucket color | bucket color | OK |
| `◐` | half / progress≈0.5 | `icons.HALF`; `status_glyph` for now bucket / progress 0.25-0.625 | bucket color (pink for now) | bucket color (yellow for now per spec) | **DECIDE** — color drift, see §F |
| `◑` | most-done / progress≈0.75 | `icons.MOSTLY`; returned for progress 0.625-0.875 | bucket color | bucket color | OK |
| `●` | done (terminal) | `icons.DONE_FULL`; returned for bucket=done | `#A6E3A1` done-green | `#86EFAC` done-green | **DECIDE** — hex drift (close shades), see §F |
| `▶` | session live | `icons.SESSION_RUN`; **not yet wired** — `active_session` defaults False everywhere | `#89DCEB` cyan | "now-yellow, bold" | **SPEC-WINS** on color *if* we wire sessions; but spec says cyan in §C ("State row"). Spec is internally inconsistent — fix the spec. |
| `✕` | dropped (terminal) | `icons.DROPPED`; returned for bucket=dropped | `#8A8D9A` grey | "drop-pink, dim" | **CODE-WINS** — grey reads better, dropped is "fade out" not "alert" |
| `!` | blocked (slot 1) | `icons.BLOCKED_BANG`; `status_glyph` for run_state=blocked | `#FAB387` warn-amber | "drop-pink" | **CODE-WINS** — amber is the warn vocabulary, pink is for `now`; keep them distinct |
| `?` | waiting | `icons.WAITING`; returned for run_state=waiting | `#F5C76E` mustard | "drop-pink" | **CODE-WINS** — same reasoning, waiting is warn-ish, not now-ish |
| `+` | migrated | `icons.MIGRATED`; returned for run_state=migrated OR `migrated` field | `#CBA6F7` lavender | "lavender" | OK |

### Slot-1 issues

1. **Precedence vs trigger drift** — spec precedence: `! > ? > ▶ > +`. Code matches. ✓
2. **`migrated` trigger** — spec says "`promoted_to` is set"; code checks `run_state=migrated OR row.get("migrated")` (neither is `promoted_to`). **SPEC-WINS** — code should check `promoted_to` per `SCHEMA-TASK.md`.
3. **`waiting` source** — spec says "`issue=waiting`"; code checks `run_state=waiting`. **DECIDE** — check schema: which field actually holds it? (See §G.)

---

## B. Slot 2 — Flag glyphs (post-title)

| Glyph | Spec flag | Code constant | Used in code? | Verdict |
|---|---|---|---|---|
| `*` | pinned | `FLAG_PINNED="*"`, also `PINNED="*"` | `focus.py:259` uses literal `"★"` for "★ pinned" in preview row — NOT `*` | **DECIDE** — preview row uses `★`, chip row uses `*`. Pick one. |
| `!` | priority high | `FLAG_PRIORITY="!"` | **not rendered anywhere** — chip code only renders `[kind]`, pinned, blocked, promoted | **NEW-LOCK** or remove from spec until shipped |
| `:` | has refs | `FLAG_REFS=":"` | **not rendered** | same — defer to v1.x |
| `^` | has session log | `FLAG_LOG="^"` | **not rendered** | same |
| `&` | scheduled | `FLAG_SCHEDULED="&"` | **not rendered** | same |
| `#` | tagged | `FLAG_TAGGED="#"` | **not rendered** | same |

### Slot-2 issues

4. **Pinned glyph collision** — spec defines `*` for pinned. `focus.py:259` (`_row_preview`) renders `"★ pinned"` (filled black star, U+2605). The chip row uses `★`-not-`*` too: look at `_row_chips` → uses `icons.PINNED` which is `*`. So preview = `★`, chip = `*`. **SPEC-WINS** — both should be `*`.
5. **Unshipped flags in spec** — `! : ^ & #` are documented but unrendered. **DECIDE** — keep as forward-spec or remove until rendered? Recommend: mark as **reserved** in spec (mirroring how `◆ ⬢ »` are handled).

---

## C. Slot 3 — Header glyphs

| Glyph | Spec | Code | Verdict |
|---|---|---|---|
| `⌂` | path row | `icons.HOME="⌂"`, used in header path row | OK |
| `◇` | activity row prefix | `icons.ACTIVITY="◇"`, used | OK |
| `⬡` | repo row prefix (git) | `icons.REPO="⬡"`, used | OK |
| `◆` | reserved (activity variant) | `icons.ACTIVITY_FILLED`, defined but unused; **BUT** the ASCII docstring at `header_bar.py:9` shows `◆ session 12m` — a stale doc-art using the reserved glyph for "session" | **SPEC-WINS** — fix the docstring art (replace `◆ session` with `▶ session`). D91 retired the `◆=session` allocation. |
| `⬢` | reserved (repo variant) | `icons.REPO_FILLED`, defined but unused | OK |
| `▶` | human session (active) | `icons.SESSION_RUN="▶"`; not yet wired into header state row | OK (deferred wiring is acceptable) |
| `»` | reserved (agent run) | `icons.AGENT_RUN="»"`, defined, not used | OK |
| `⟳` | TUI ready/refresh state | `icons.SPINNER="⟳"`; used in `status_bar.py:55` and toast refresh messages | OK |

### Slot-3 issues

6. **Stale ASCII docstring** — `header_bar.py:9-10` references `◆ session 12m` (retired allocation). Cosmetic but reads as spec-truth in code. **SPEC-WINS** — update docstring.
7. **Header `header_bar.py:201` comment** — `# row 2: ⟳ ready / ◆ session …` — same stale reference. **SPEC-WINS** — update.

---

## D. Operational glyphs used in code but not formally specced

These are not "status glyphs" per the spec model — they're cursor / chrome / toast affordances. The spec doesn't catalog them. The audit recommends adding a "Slot 0 / chrome glyphs" section to the spec.

| Glyph | Code constant | Where | Recommendation |
|---|---|---|---|
| `▸` | `icons.CURSOR` | Selected-row indicator on every list | **NEW-LOCK** — add to spec as "cursor glyph" |
| `✓` | `icons.DONE` | Toast success prefix (`✓ saved`), board DONE column title (`✓ DONE`) | **NEW-LOCK** — add as "success affordance" |
| `✗` | (literal) | Toast error prefix (`✗ failed`), board DROPPED column title (`✗ DROPPED`), edit-modal save-failed banner | **NEW-LOCK** — add as "error affordance". Note: `✗` is **not** the same as `✕` (which is slot-1 dropped). Visually similar, semantically distinct: `✗` = "operation failed", `✕` = "task in dropped bucket". |
| `★` | (literal in `_row_preview`) | Preview row "★ pinned" label | **SPEC-WINS** — replace with `*` per spec (see issue 4). |

### Operational issues

8. **`✕` vs `✗` collision risk** — these are different code points (U+2715 and U+2717) and ~look identical in most terminals. Code uses `✕` only for dropped-bucket status, and `✗` for failure toasts + DROPPED column title. The DROPPED column title using `✗` instead of `✕` is the only drift. **SPEC-WINS** — DROPPED column title should be `✕ DROPPED` to match the slot-1 glyph (visual consistency: when you finish a task, the row glyph and the column header should match).
9. **`✓ DONE` column title** — uses `✓` (chrome) where slot-1 uses `●` for done. **DECIDE** — column titles intentionally use a different vocabulary (check-mark = "things that succeeded") to read as "header banner", not "task state". Recommend: **CODE-WINS**, but document the deliberate split in spec.

---

## E. Board / Focus border-title glyphs

`board.py:161-166`:
```python
C_BACKLOG: "BACKLOG",
C_NEXT:    "○ NEXT",
C_NOW:     "● NOW",
C_DONE:    "✓ DONE",
C_DROPPED: "✗ DROPPED",
```

`focus.py:491, 497`:
```python
now_panel.border_title  = "● NOW"
next_panel.border_title = "○ NEXT"
```

| Title | Glyph used | Slot-1 glyph for that bucket | Drift? |
|---|---|---|---|
| BACKLOG | (none) | `·` | OK — uniform-mute treatment, no glyph |
| ○ NEXT | `○` | `○` (open / next) | OK |
| ● NOW | `●` | `◐` (half / now per spec) — code uses `◐` in `status_glyph` too | **inconsistent** — column header says NOW=`●`, task rows in NOW say `◐`. **DECIDE** — pick a vocabulary. Option A: column header = full-disk for terminal/active states (`●` NOW, `●` DONE) and ring for upcoming (`○` NEXT). Option B: align column header with slot-1 (NOW = `◐`). Option A reads better. Recommend: keep `●` for NOW header and **rename it from "done" alias** — `●` is overloaded. |
| ✓ DONE | `✓` | `●` | See issue 9 — intentional chrome split |
| ✗ DROPPED | `✗` | `✕` | See issue 8 — fix to `✕ DROPPED` |

### Border-title issues

10. **`●` overload** — code uses `●` for *both* "DONE column slot-1 glyph" *and* "NOW column header". Visually identical, semantically different. **SPEC-WINS** — disambiguate. Suggestion: NOW header keeps `●` (it reads as "current focus"), but DONE slot-1 task glyph is already `●` per spec → no conflict at the column title level since DONE uses `✓`. The conflict is only at the *legend* level. Acceptable, but document.

---

## F. Color drift (orthogonal to glyph drift)

Spec §"Bucket axis" lists:

| Bucket | Spec hex | Code hex (`status_glyph_color`) | Notes |
|---|---|---|---|
| backlog | `#7AB8FF` (or muted grey idle) | `#8A8D9A` grey | **CODE-WINS** — code uses grey-only, never blue. The spec's blue is aspirational and unused. |
| next | `#5EEAD4` | `#89DCEB` cyan | **DECIDE** — both are cyan-teal family but different values. Code value is consistent across header chips + status glyphs. Likely **CODE-WINS**. |
| now | `#FACC15` yellow | `#F38BA8` pink | **MAJOR DRIFT** — spec is yellow, code is pink. Pink is also used for `now-pink` accents (cursor selection, urgent indicators). **DECIDE** — needs Alessandro's call. This is the most consequential drift. |
| done | `#86EFAC` | `#A6E3A1` | both mint-green; **CODE-WINS** (close enough) |
| dropped | `#F38BA8` dim | `#8A8D9A` grey | **CODE-WINS** — grey reads as "fade out", pink would clash with `now` |

The color spec was written aspirationally before the visual redesign landed. Code colors are what shipped. Recommend: **CODE-WINS across the table**, update spec to match shipped palette. The exception is `now`, which deserves an explicit decision.

---

## G. Schema field drift

| Spec says | Code reads | Verdict |
|---|---|---|
| `! blocked` ← `run_state=blocked` | `run_state=blocked` ✓ | OK |
| `? waiting` ← `issue=waiting` | `run_state=waiting` ✗ | **SPEC-WINS** if `issue` is the field per `SCHEMA-TASK.md`; otherwise **CODE-WINS** |
| `+ migrated` ← `promoted_to` is set | `run_state=migrated OR row["migrated"]` ✗ | **SPEC-WINS** — `promoted_to` is the schema field |

Need to read `SCHEMA-TASK.md` to confirm. The audit flags this; reconciliation phase will resolve.

---

## H. Summary of action items

### Spec changes (CODE-WINS or NEW-LOCK)
- S1. Document chrome glyphs: `▸ cursor`, `✓ success affordance`, `✗ error affordance`, `★` retired in favor of `*`.
- S2. Mark unshipped flag glyphs (`! : ^ & #`) as **reserved**, mirroring `◆ ⬢ »` convention.
- S3. Update color table to shipped palette (backlog grey, next cyan `#89DCEB`, done mint `#A6E3A1`, dropped grey).
- S4. Document the deliberate column-header chrome vs slot-1 status vocab split (`✓ DONE` header vs `●` slot-1).
- S5. Fix internal spec inconsistency: §"Slot 1" says session is "now-yellow"; §"Slot 3" says cyan. Pick cyan (matches code, matches §C).
- S6. Resolve `now` color (§F) — Alessandro's call, then update spec or code accordingly.

### Code changes (SPEC-WINS)
- C1. `focus.py:259` — replace `"★ pinned"` with `"* pinned"`.
- C2. `header_bar.py:9, 201` — replace `◆ session` with `▶ session` in docstring art.
- C3. `board.py:166` — `"✗ DROPPED"` → `"✕ DROPPED"` (slot-1 consistency).
- C4. `icons.py:status_glyph` — change `migrated` trigger to `promoted_to` field per schema.
- C5. `icons.py:status_glyph` — change `waiting` trigger if schema says `issue` field (verify first).
- C6. `icons.py:status_glyph_color` — verify `BLOCKED_BANG` returns warn-amber `#FAB387` (already does); update spec to match (see S5).

### Decisions needed from Alessandro
- D1. **now color** — pink (shipped) or yellow (spec)?
- D2. **Pinned chip glyph** — `*` (spec) or `★` (preview row literal)? Recommend `*`.
- D3. **Schema field for `migrated`/`waiting`** — confirm against SCHEMA-TASK.md.
