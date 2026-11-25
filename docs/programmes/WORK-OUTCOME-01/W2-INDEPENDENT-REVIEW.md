# W2-INDEPENDENT-REVIEW — Open obligation + external commission

Status: CARRIED. No governed model route exists (verified W1: no Muse/Codex
route strings; Worker `127.0.0.1:7317` refused again at W2). Deterministic W2
proceeded with zero model calls; no ungoverned AI judgement was used. W2
final acceptance explicitly reports this instead of claiming it.

## Self-check performed (not independent verification)

10-point challenge over the W2 diff: identity stability, association
correctness on fixtures (chain 15/15, zero false task memberships),
false-association guards (4 negative controls), hierarchy cycles, incremental
idempotence, duplicate prevention, provenance completeness, PG safety
(additive 042), existing-infra reuse (no new git/history system), privacy
(synthetic fixtures only; frozen ids + counts in reports, no bodies).
No unresolved implementation findings. Review cost: 0.

## External commission (to run when a route exists)

Reviewer task: independently verify the W2 implementation, not the
reconstruction results.

1. Read `W2-ENTRY-GATE.md` through `W2-TEST-EVIDENCE.md` in
   `docs/programmes/WORK-OUTCOME-01/`.
2. Inspect the diff: `backend/mission_control/work_observation/reconstruct.py`
   (engine), `episodes.py` (service), `api/work_episodes.py`,
   `opencode_adapter.py` (2 new extractor patterns), migration `042_*`,
   `models.py` (`WoEpisode*`), `backend/tests/test_work_episodes.py`.
3. Re-run: `pytest backend/tests/test_work_episodes.py
   backend/tests/test_work_observation.py backend/tests/test_migrations_and_seed.py`.
4. Adversarially examine: episode-id stability under replays with new
   evidence; association correctness on the 7 frozen sessions (ids in
   W2-SEVEN-CASE-PILOT); false-association risk of stage/programme
   heuristics (`W\d+`, known programme roots); unresolved-bucket growth on
   noisier projects; `diff-tree` subprocess bounds; cycle rejection against
   pre-existing DB parents; migration 042 on a pre-existing PG.
5. Return: ACCEPTED / CONDITIONAL / BLOCKED with file:line findings.

Suggested routes when available: DeepSeek `deepseek-v4.1-flash-free` →
fallback `deepseek-v4.1-flash`; strong review `gpt-6-luna`. Track cost
separately from the $0 pipeline cost.
