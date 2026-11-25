# W8F-OPERATIONAL-INTEGRATION — What runs where, and what stays off

- Retrospective pipeline (W1–W6): untouched and retained. Historical
  episodes, mixed instrumentation, manual associations, partial
  instrumentation, old contract versions — all supported; nothing
  requires re-registration (§23).
- Prospective path (W8C–E): envelope API live on operational code
  (048 tables exist, empty); pilot rows on scratch only.
- UI: existing views extended only where necessary (envelope read
  surface is API-first in W8; display folds into Episodes detail as
  follow-up — no new dashboard built, deliberately).
- What stays off: scheduler, semantic eval, auto-execution,
  auto-close/confirm, paid inference. The W8A operational Proposals
  tab (1 live proposal, zero console errors) is the current
  operational frontier.

W9 entry requirements: real worker/workbench propagation (live, not
manual links); receipt-bound test evidence on a pilot; cross-family
review; episode-level verified-complete via the now-existing
mechanism; confirmation backlog triage; pagination for groups at
scale.
