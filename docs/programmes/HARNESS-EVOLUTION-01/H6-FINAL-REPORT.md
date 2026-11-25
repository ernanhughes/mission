# HARNESS-EVOLUTION-01 — H6 final report

## Verdict

**ACCEPTED — ISOLATED INTEGRATION ONLY**

Mission Control now contains a usable Harness area, and one isolated synthetic execution traversed its UI, Mission authorization adapter, Work Envelope, Worker strategy runtime, H3 ledger, and artifact viewer. Operational activation remains unapproved and unperformed. H7 remains design-only.

## Result

1. **Changes:** added the Mission Harness API, optional loopback Worker URL, six-tab Harness UI, sidebar/route, project Harness panel, focused tests, and H6 fixture/evidence/document set.
2. **Reuse:** Mission Work Outcome episodes/objectives and Work Envelope; Worker strategy/model catalogue, runtime, H3 ledger, jobs, decisions and retained artifacts; existing Work Evaluation and episode outcome surfaces.
3. **Interfaces:** `/api/harness/catalogue`, `/executions`, `/executions/{request_id}`, `/jobs`, `/executions/{request_id}/artifacts`, and bounded `POST /executions`. Worker routes remain authoritative. No database migration.
4. **Navigation:** Mission left navigation → **Harness** → Overview, Strategies, Execute, Executions, Decisions, Experiments. Projects include a Harness tab using the same ledger.
5. **Execution:** one UI-confirmed `adaptive.v1` request used an existing current synthetic objective, local-only scripted route, one-attempt policy, 30-second requested timeout and 256-token requested output cap; no workspace or tools were attached.
6. **Correlation:** Mission verifies Work Outcome links by matching Worker `operation_id` to its Work Envelope and checking exact episode/objective identity. Worker’s `caller_supplied_unverified` label remains visible. Project scope is exact and checked by the API.
7. **Evaluation/acceptance:** output returned `AWAITING_ACCEPTANCE`; no independent evaluation was recorded; episode stayed `established`; no acceptance/promotion occurred. Result correctness and effectiveness remain unestablished.
8. **Inspect:** boundary documented; discovered capability does not become executable without a verified invocation contract, permissions, bounded Worker adapter, independent evaluator, and separate authority.
9. **Resource controls:** 60-second request ceiling, 2,048 output-token ceiling per invocation, Worker max two calls, configured free/local-only routes. Provider inference is none in the fixture; output-cap enforcement and remote termination remain `UNKNOWN`; billed cost is null, route/policy declared free.
10. **Deterministic E2E:** Worker normalized a complete JSON fence with `json-fence.v1`; one scripted invocation; raw `{"answer":42}` remained distinguishable from the fenced raw text and the normalized artifact. This qualifies integration behavior only.
11. **Actual UI evidence:** isolated browser DOM and screenshot showed correlation, raw/normalized artifacts, no evaluation, and separate acceptance. Machine-readable execution evidence is retained in `h6-fixtures/runs/e2e-20261125-b/`.
12. **Focused checks:** backend 10 passed; frontend 22 passed; frontend typecheck/build passed; Worker strategies/server 32 passed; Worker typecheck passed. Full suites and long corpora were deliberately deferred. See `H6-TEST-EVIDENCE.md`.
13. **Independent review:** separate Codex reviewer identified three material defects and two follow-up residuals; all were corrected, focused regressions passed, and final read-only follow-up found no further material concern. See `H6-INDEPENDENT-REVIEW.md`.
14. **Use/activation:** exact operating guide and activation/rollback sequence are in `H6-USER-GUIDE.md` and `H6-ACTIVATION-AND-ROLLBACK.md`. Do not use operational port 8790 as an H6 surface until separately activated.
15. **H7 inputs:** read-only identity/evidence contract, comparison conditions, independent evaluator ownership, isolated candidates, explicit budgets/authority, and Inspect boundary are specified in `H7-INTEGRATION-INPUTS.md`. No H7 code was implemented.
16. **Preservation:** Mission and Worker HEADs did not move; no staging, commit, push, deployment, operational migration, operational DB mutation, or manuscript edit occurred. Inherited unmerged Mission files remain unmerged; see the preservation refresh in `PRESERVATION-SNAPSHOT.md`.

### Limits

This is isolated integration acceptance only. The single route was scripted and made no provider inference, so no answer correctness, model effectiveness, or provider qualification is established. Raw artifacts are Worker-process-memory retained and may disappear after restart. Operator actor/note fields are attestations; no authenticated-user identity binding was established. No operational activation occurred.
