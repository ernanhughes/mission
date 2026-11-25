# W9-ENTRY-GATE — Qualification, controlled rollout, programme closure

Authorized: W9 qualification + bounded rollout (W9A–F gated). Final
planned stage. Stop conditions §32 acknowledged (no W9+ invention, no
unrestricted backfill, no unattended semantic eval, no auto-execution/
confirm/close, no fabrication, no competing infra, no OpenCode writes,
no unauthorized migrations, no paid inference, no commit/push, no
unrelated staging).

## Entry state (verified 2026-11-25)

- Repo `C:\Projects\mission`, HEAD `fd11db6`; 62 changed entries
  (mix of W6–W9 work + other workstreams: testing.py, pub06/,
  aitest 049/050s, publication docs). No commits by this commission.
- Operational DB `mc`: schema v51, 31 episodes, 9 requirements,
  293 findings (287 open / 6 resolved), 24 groups. W8A demo rows
  present and legitimate (1 proposal approved+handed-off, 1
  confirmation, 1 execution link, 1 resolved finding).
- Backup: pre-W8A dump verified + restored to scratch (w6e mirrors
  operational; W8 pilot rows live there).
- Scheduler OFF, paid budget $0, no unattended semantic eval.
- Worker :7317 DOWN (opencode CLI missing → opencode backend
  unavailable; dry_run/direct paths possible). Workbench :7420 UP
  but workflow runtime unconfigured + owner-gated. AITest live on
  :8790 (28 projects inventoried; ai has no receipt yet).
- Outstanding: cross-family review (in progress via Mistral —
  CONDITIONAL, see W9A doc); confirmation backlog; episode-level
  verified-complete; live propagation; JSON audit (in progress).

## Gate order

W9A (assurance + safety) → W9B (live propagation) → W9C (verified
complete) → W9D (coverage + calibration) → W9E (policies + waves +
scheduler qual) → W9F (acceptance + closure). No W9+ will be
invented; residual obligations become an explicit closure commission
or are deferred with reasons.
