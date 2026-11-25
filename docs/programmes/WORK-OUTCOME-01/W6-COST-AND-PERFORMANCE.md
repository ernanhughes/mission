# W6-COST-AND-PERFORMANCE — Every call accounted for

## Model usage (all local loopback, $0.00 provider spend)

| Activity | Calls | Cost | Notes |
| -------- | ----- | ---- | ----- |
| W6A benchmark (mistral-small, 2 packets × 2 attempts) | 4 | $0 | 1 cold timeout, warm 112s/27s/131s |
| W6 operational evaluations (05 ×3, 08B-1, 08C) | 5 runs, 0 semantic | $0 | deterministic only |
| Semantic auto-eval | 0 | $0 | flag off, budget unwirable |
| **Cumulative W4+W5A+W6 provider spend** | — | **$0.00** | tracked in wo_extraction_runs / get_cost |

Per-call latency (~60–180s) still bounds unattended semantic use to a
handful of episodes — consistent with the ≤30-call cap and the
manual-first posture.

## Operational deltas (live mc, schema v46 → v47)

- Episodes 31 → 31 (no new episodes; recon re-runs upsert). Associations
  291 → 295 (+4 R1 commits to 05). Objectives 27 → 27. Requirements
  0 → 9 (+9 human-reviewed, +9 provenance rows). Claim verifications
  1,267 → 1,267 (untouched). Requirement assessments 0 → 29.
  Episode assessments 126 → 132 (+6 W6A evals). Findings 278 → 293
  (+15 genuine new: 10 verification gaps on new requirements, 5
  missing_requirement later resolved). Finding groups 0 → 24; members
  288 (5 resolved excluded, preserved). Eval-state rows 0 → 3.
- Findings resolved with closure evidence: 5. Findings deleted: 0.
- Non-wo_* rows touched: 0 (verified: projects/commits counts unchanged;
  dev-backend seeds went to scratch w6e only).
- Timings: deterministic episode eval ~seconds; group persist over
  ~290 findings trivial; lifecycle pass on scratch 7–8s end to end.
- Job failures: 1 (recon cross-scope PK collision on scratch,
  root-caused, fixed, regression-tested — see W6C doc). No data lost
  (transaction rolled back; no partial writes).
