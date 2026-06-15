# D38 — actor enum expanded; priority enum reshaped

- `actor`: `human | ai | automation` (added `automation` for deterministic scripts).
- `priority`: `low | high | urgent`, absent = normal. (Previously `low | medium | high` with default `medium`.)
- Asymmetric default (normal is implicit) — preferred over symmetric explicit default.
