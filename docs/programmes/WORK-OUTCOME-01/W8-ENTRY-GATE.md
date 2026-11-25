# W8-ENTRY-GATE — Prospective instrumentation + W7A activation

Authorized: W7 conditionally accepted; W7A activation + W8A–F gated.
Stop conditions §31 acknowledged (no W9, no unattended semantic eval,
no scheduler enablement, no auto-execution, no competing infra/event
bus, no history rewrites, no fabrication, no OpenCode writes, no
unauthorized migrations, no paid inference, no commit/push).

## Entry state (verified 2026-11-25)

- Repo `C:\Projects\mission`, HEAD `a6a358a`; 9 modified + 41
  untracked (W6/W7 tree + other workstreams: testing.py M, pub06/,
  aitest 049 pair, publication docs).
- Operational DB `mc`: schema v49, 31 episodes, 9 requirements,
  293 findings (287 open / 6 resolved), 24 groups, 05 partial.
  Pre-W8A backup: `data/backups/mc-pre-w8a-20261125T000000Z.dump`
  (11.4 MB, sha256 2d4739b7…), restore-verified into w6e (49/31/293/0).
- :8790 serves W6+W7 code AND rebuilt dist (operator restarts on the
  working tree; verified live: groups API 24, work-corrective routes).
  No page-load execution anywhere (tested).
- Scheduler OFF, paid budget $0, semantic routes disabled.
- Outstanding: cross-family review; re-verifications; confirmation
  backlog (20+ episodes); episode-level verified-complete (finding-
  level done); 048 activation (tables exist operationally, empty —
  pilot rows on scratch by design).

## Gate order

W8A (activate + migration governance) → W8B (contracts/ownership) →
W8C (envelope) → W8D (propagation) → W8E (prospective pilot) → W8F
(integration/acceptance). Stop at any failed gate.
