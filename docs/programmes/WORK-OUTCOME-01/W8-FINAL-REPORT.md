# W8-FINAL-REPORT — Prospective Work Instrumentation: CONDITIONAL ACCEPTANCE

## Verdict: CONDITIONAL ACCEPTANCE (pilot-proven, rollout-gated)

W8 replaces archaeology with architecture where it counts: work can
now be registered before execution with pinned intent, executed
against an explicit envelope, linked to its evidence, evaluated
against its own acceptance criteria, and closed on proof. Demonstrated
end to end on a real task with a real (partial, honest) verdict.

## Sub-stage verdicts

- **W8A activation + migration governance: CONDITIONAL ACCEPTANCE.**
  Proposals UI live on operational :8790 (1 real proposal, approved,
  handed off; 1 real requirement confirmation; zero console errors).
  Backup + restore verified (11.4 MB, sha256 recorded). Governance
  investigation complete: startup auto-applies working-tree
  migrations with no approval gate (recommendation: banner + watermark
  + read-only drift view; no new system). Accepted with the caveat
  that 048–051 reached operational via that mechanism (additive,
  validated first, empty tables except authorized demo rows).
- **W8B contracts + ownership: ACCEPTED.** Inventories from code (not
  slides): worker/workbench/sidecar/AITest/harness/ECK contracts with
  file:line refs; ownership map (Mission Control owns intent/approval
  rows; everyone references, nobody duplicates).
- **W8C envelope: ACCEPTED.** work-envelope.v1 (671 bytes, metadata
  only), digest-bound (now including authorization), versioned with
  supersession, validated refs.
- **W8D propagation: CONDITIONAL ACCEPTANCE.** Linkage resolves
  (sessions/commits/receipts/reviews) or rejects; remote_ref kind
  added with regression test; worker/workbench paths designed with
  manual fallback demonstrated (live propagation not yet wired).
- **W8E pilot + completion: CONDITIONAL ACCEPTANCE.** Full 10-step
  lifecycle on a real task: 3/3 reported → partial (withheld verified,
  precisely blockered). Retrospective comparison documented (n=1,
  no broad claims).
- **W8F integration: ACCEPTED.** Retrospective pipeline retained;
  read-only Envelope tab; no new dashboard; scratch/operational
  separation kept (one documented incident below).

## Incidents (handled, disclosed)

1. **Author's debug-write to operational mc (2026-11-24T23:25).** A
   diagnostic one-liner ran without `MC_DSN` set, so `Database()`
   resolved to the default operational DSN and inserted 3 fixture
   rows (ep:w, rqw, we:ee9dad). Zero dependents existed. All 3 rows
   removed after dependency check; counts restored (31/9/293) and
   re-verified. No programme record was altered. Lesson recorded:
   ad-hoc scripts must set MC_DSN explicitly (tests are guarded by
   conftest; scripts are not).
2. **JSON-over-TEXT returns strings on PG.** Mechanical links and
   envelope reads hardened with `_jl` normalization (SQLite already
   deserializes). Pre-existing W-code mostly slices (works on both);
   remaining readers flagged for audit (W9 input).

## Stop conditions: all held (§31 verified)

No W9; scheduler still disabled; no unattended semantic eval; no auto
corrective execution; no competing infra/bus; no history rewrites
(except the documented removal of the author's own accidental rows,
which were never programme records); no fabrication; no OpenCode
writes; no operational backend restarts by us; no unauthorized
migrations by hand (051 validated on scratch; operational v51 arrived
via operator restart of present files); no paid inference ($0);
no commit/push; unrelated work preserved.

## Outstanding (W9 entry)

Cross-family review (gates unattended operation); live
worker/workbench propagation; test-receipt-bound pilot +
unconditional verified-complete exemplar; confirmation backlog;
finding-volume UX at scale; JSON-column audit beyond the envelope
path; group-membership history annotation for fully-resolved classes.
