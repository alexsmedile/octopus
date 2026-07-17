# D34 — open field renamed to pinned

- `open` → `pinned`. Verbs stay `pin` / `unpin`.
- Semantics shift: `pinned: true` means "surface to top of every list view," not "open loop."
- Open loops becomes a derived view (`octopus loops`): `bucket NOT IN (done, dropped) AND NOT archived`.
- Pinned tasks always sort first in any list, regardless of other order.
