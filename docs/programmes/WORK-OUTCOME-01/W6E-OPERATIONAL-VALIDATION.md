# W6E-OPERATIONAL-VALIDATION — What was proven, where, and what was not switched on

## Environment

Live operational DB `mc` (schema v47) for all recorded passes.
Interactive dashboard evidence from an isolated stack: dev backend
`:8791` on a full `mc` copy (`w6e`, pg_dump restore verified identical:
31 episodes / 293 findings / 24 groups / 9 requirements) + vite dev
(`:5173`, allowlisted origin) serving the W6 frontend. Zero console
errors on all captures. The operator's `:8790` backend was never
restarted, reconfigured, or written through; its served product is
unchanged by W6.

## End-to-end lifecycle (§24), genuine bounded example: AI-CORE-05

1. Objective existed (inferred "Achieve AI-CORE-05") but empty of content.
2. Repository artifacts located deterministically (14 candidates for
   08C, 2 for 05, 5 for 08B-1) + git history (R1 SHAs resolve in MC).
3. 9 requirements recovered human-reviewed with digests + review basis.
4. 4 R1 evidence commits associated; 13 human-attested file links added.
5. Deterministic evaluation: 05 `unknown → partial`, outcome `mixed`,
   6× reported + 1× verified (mechanical existence).
6. 5 stale findings closed by §21 reconciliation with cited assessments.
7. Scratch lifecycle passes: observe (0 new, checkpoints current) →
   recon completed → queue empty (all current) → 0 evals → 24 groups;
   replay byte-identical in effect (no duplicates, 7–8s).
8. Closure where justified (5×); the 288 remaining gaps stay open for
   want of execution/push/SHA records — the system withholds, not the
   operator's data.

Dashboard acceptance (§25): Overview (31/0/26/1 + PARTIAL 05),
Groups (24 × 288, nothing hidden, closure criteria per group),
Controls (off-by-default schedule, manual triggers, queue, freshness).
Screenshots: w6-overview/groups/controls.png. Commits/Notes tabs
untouched in the same sessions (W5 suite green).

## Not activated (explicit)

The scheduled timer was NOT started anywhere; `wo_auto_enabled` is off
on operational; no ecosystem backfill ran; unattended semantic
evaluation stays BLOCKED. Bounded live activation = the recorded manual
passes above. Switching the schedule on is an operator decision with
the W6D policy already enforced in code.
