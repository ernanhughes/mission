# W9G DeepSeek cross-family review packet (bounded, deterministic excerpts)

You are an independent code reviewer. You have no access to the repository;
review ONLY the excerpts below. Return ACCEPTED / CONDITIONAL / BLOCKED with
file:line findings. Do not invent evidence: every finding must cite an excerpt
label (E1..E12) and line. If the excerpts do not show a defect, say so.

## Context (programme WORK-OUTCOME-01, W9 conditional acceptance)
Work-observation pipeline: deterministic observation -> episode reconstruction
-> evaluation (mechanical deterministic + optional semantic) -> finding closure.
Safety invariants claimed: (1) DB-target fail-closed at ORM boundary; (2)
SafeJSON/metadata-only envelopes; (3) policy ladder enforcement for scheduled
AND manual paths; (4) envelope digest binding; (5) proposal approval by human +
human finding closure; (6) severity policy; (7) no unattended semantic; (8) no
auto-execution. Prior Mistral-family review (W9A) returned CONDITIONAL;
B (auto-closure without human evidence) was FIXED (human actor+reason now
required), A accepted as architecture, E corrected on evidence.

## Excerpts

### E1 verify.py assess_requirement_deterministic (mechanical lane)
- Existence-kind requirements (or text hint file/manifest/endpoint/page)
  with resolved file/git_commit evidence -> satisfied_verified (strong).
- Anything else with resolved evidence -> satisfied_reported (moderate),
  missing="independent correctness judgement". No resolved evidence +
  mandatory + siblings have evidence -> not_satisfied. Ambiguous authority
  with no evidence -> insufficient_evidence.
- RUBRIC_VERSION = "w4-v1".

### E2 verify.py rollup_completion (verify.py:162-182)
- complete requires EVERY mandatory requirement satisfied_verified.
  satisfied_reported is NEVER completion: any reported/partial -> "partial"
  ("requirements reported/partial but not all verified"). not_satisfied/
  contradicted -> "incomplete". Unknown/missing -> "unknown"/"blocked".

### E3 evaluate.py _validate_eval (evaluate.py:520-563)
- F2: ambiguous-authority requirement upgraded past insufficient_evidence ->
  rejected ("ambiguous requirement must not be upgraded").
- F4: satisfied_verified with no resolved git_commit/review/test_report ref ->
  rejected ("satisfied_verified requires resolved evidence").
- Unknown evidence ref, rationale <20 chars, vacuous instruction echo ->
  rejected. satisfied_verified evidence refs are restricted to resolved
  git_commit/review/test_report kinds (file refs do NOT count here).

### E4 evaluate.py closure gates (evaluate.py:903-969)
- reconcile_resolved: closes missing_requirement findings whose requirement
  is satisfied_*. REQUIRES human actor (rejects empty/"system"/"model") AND
  non-empty reason. Closure text records actor+reason+assessment id.
- resolve_finding: REQUIRES cited evidence >=20 chars AND human actor
  (rejects "system"/"model"). History preserved; reopen via status change.
  Comment states: "Never called automatically."

### E5 policies.py ladder (policies.py:1-60,103-147)
- Levels: disabled < observe < reconstruct < manual_evaluation <
  continuous_mechanical < continuous_semantic.
- Unknown capability or level -> False (fail closed). Semantic split:
  evaluate_semantic_manual needs manual_evaluation+;
  evaluate_semantic_scheduled needs continuous_semantic.
- set_policy: rejects unknown level, empty project_key, empty actor, and
  actor "system"/"model" ("policy change requires a human actor").
- resolve_project_key: unknown scopes resolve to themselves, default
  disabled (fail closed). get_policy: unknown level -> disabled.
- Corrective execution is NEVER authorized by a policy level (docstring).

### E6 continuous.py _gated + run_pass (continuous.py:1-17,46-64,94-118)
- Module docstring: "Never performs corrective execution"; "paid inference
  budget is hard zero"; "scheduled loop ... intentionally NOT started here".
- _gated: policies None OR no project scope -> semantic evaluation REFUSED
  (fail closed); other capabilities keep historical manual behaviour but
  receipt records "policy_unscoped". Gate exceptions -> False.
- run_pass: allow_semantic AND NOT _gated("evaluate_semantic") ->
  allow_semantic=False + receipt "semantic:policy_disallows".
  evaluate_mechanical gate refusal -> receipt "evaluate_mechanical:
  policy_disallows" (visible, not silent skip).

### E7 db.py target fail-closed (persistence/db.py:58-89,146-160)
- PostgreSQL targets REQUIRE explicit target= label (e.g. "server",
  "scratch:<name>"); missing label = fail-closed error, never silently
  opens operational DB.
- Under pytest: Database may target ONLY tmp SQLite or exactly MC_TEST_DSN;
  anything else (production MC_DSN, repo data file) refused before connect.

### E8 envelopes.py registration authorization (envelopes.py:89-148)
- Authorization = approved wo_proposal (pinned id+version+scope_hash) OR
  explicit human attestation. proposal status != "approved" -> rejected.
  Direct authorization requires human actor + note; actor "system"/"model"
  -> rejected ("authorization requires a human actor"). No auto-authorization.

### E9 envelopes.py digest binding (envelopes.py:149-184)
- commission_digest = sha256(objective text, requirement id+version list,
  scope, acceptance criteria, auth ref, repositories, policy ref).
  Duplicate digest -> "duplicate" (no new envelope). New scope ->
  version+1, previous "superseded".

### E10 proposals.py no auto-execution (proposals.py:1-18,58-76)
- Status machine draft->ready_for_review->approved->queued->running->
  reported_complete->verification_pending->verified_resolved.
  "No auto-execution: queued/running/report transitions are recorded
  handoff states, never performed by this service."

### E11 Pilot 08C facts (W8E + W8D + W9C docs)
- Episode ep:task:W8-PILOT-VERIFY-08C, C:\Projects\ai repo, commit 88b7c04,
  remote https://github.com/ernanhughes/ai.git, ref origin/main.
- 3 acceptance requirements (merge-base ancestry / origin/main lists commit /
  remote URL exact match). Envelope v1->v2 on adding repository scope.
- Two independent agents re-ran all 3 checks; byte-identical outputs
  (merge-base exit 0, origin/main listed, URL exact match).
- Assessment: 3/3 satisfied_reported -> completion partial (reported, not
  verified). Assessment consumes linked evidence, not executor count.
- Stated blockers for verified-complete: (1) no independent REVIEW of the
  acceptance criteria; (2) no test receipt bound to episode; (3) rubric
  verified lane is mechanical-existence-only, relational facts cannot enter.

### E12 Self-evaluation (W9F doc)
- System graded its own programme: 11 satisfied_reported, 3 not_satisfied
  (cross-family assurance complete / verified-complete episode exists /
  controlled multi-project operation), 1 insufficient_evidence (usefulness).
  Result "incomplete" — matches human reviewer; did not over-claim.

## Questions (answer ALL)

a) W1-W9 integrated assurance: for each of the 8 invariants in Context,
   state whether the excerpts support it (SUPPORTED / GAP + file:line).
   Flag any bypass you can construct SOLELY from these excerpts.

b) Verified-lane amendment (proposed, NOT implemented): relational git
   requirements (ancestor/contains/remote-URL) may reach satisfied_verified
   ONLY when ALL hold: (i) resolved git_commit (uid:sha bound to episode) +
   resolved remote_ref (exact URL+ref bound to same repo+sha); (ii) >=2
   independent re-executions with byte-identical outputs; (iii) independent
   review record accepting the criteria; (iv) rubric version bump (w4-v1 ->
   w4-v2) documenting the widened lane. Does this weaken completion
   semantics? Return explicit APPROVE (with conditions) or REJECT (with
   reasons). Consider: does E2 still guarantee verified means verified?

c) 08C pilot: is partial the correct verdict TODAY under E1+E2 (give the
   mechanical reason)? List exactly what would be needed for
   verified-complete under (i) current rubric, (ii) the proposed amendment.

d) Wave 1 readiness: projects mission/worker/workbench at manual_evaluation,
   no scheduler, no paid inference. Under E5+E6, is it safe to enable?
   State what remains gated and what an operator must do to escalate.

## Required output format
1. Verdict table: rows A authorization, B false-completion, C severity
   policy, D auto-execution/scheduler, E DB targeting, F policy ladder,
   G envelope integrity; columns verdict (PASS/CONDITIONAL/FAIL).
2. Overall: ACCEPTED / CONDITIONAL / BLOCKED (one word).
3. Findings list: id, severity (critical/major/minor), excerpt+line, one
   sentence each. Zero-invention rule: mark each finding EXCERPT-BASED.
4. Amendment: APPROVE (conditions) or REJECT (reasons).
5. Pilot: CORRECT/INCORRECT + mechanical reason + needs-lists (i),(ii).
6. Wave 1: SAFE / UNSAFE + what stays gated.
