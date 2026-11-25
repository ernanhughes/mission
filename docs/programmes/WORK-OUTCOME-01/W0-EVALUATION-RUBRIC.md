# W0-EVALUATION-RUBRIC — Requirement-level, evidence-bound

No composite quality score in W0. No bulk historical AI analysis performed.

## 1. Requirement states (mutually exclusive per requirement)

`requested → reported → observed → tested → verified → integrated → demonstrated → complete`,
with `incomplete | blocked | unknown | na` as terminal/inapplicable.

- `requested`: objective text asks for it (with locator).
- `reported`: AI claims done/passed/merged (claim locator, not proof).
- `observed`: matching change present in source (`repo_id/sha/path/hunk` or worktree hash).
- `tested`: test artifact names it (with digest + result, not just "tests passed" text).
- `verified`: independent check re-executed or re-read it (own digest + evaluator identity).
- `integrated`: present in intended branch/system (merge/registration proof, not claim).
- `demonstrated`: usable through intended interface (run output, UI evidence, accepted review).
- `complete`: all applicable gates for its kind passed (see §3).
- `incomplete/blocked/unknown/na` with reason + evidence (or explicit absence).

A commit proves state change, not correctness. A passing-report proves a report,
not a reproduction. A manifest proves a manifest, not implementation.
A corrected defect does not prove the failure mode is gone without a re-test.

## 2. Dimensions (assessed per episode, evidenced per requirement)

Intent alignment · Completeness · Correctness · Implementation quality ·
Architectural alignment · Integration quality · Evidence quality ·
Operational usability · Efficiency · Outstanding obligations.
Each: `pass | concern | fail | unknown` + one-line reason + evidence refs.
Narrative allowed; arithmetic averaging forbidden (precedent: Writer six subdimensions,
Living Book labelled measures, `NOT_RUN` never zero).

Reuse existing code-review findings instead of re-reviewing: `git_reviews` verdict/findings
are inputs with `(review_id, prompt_hash, observed_model)` provenance.

## 3. Completion semantics

`Outcome.complete` iff every mandatory requirement is `complete`/`na` with kind-appropriate gates:

- Code: observed + tested + verified + integrated ( + demonstrated if user-facing).
- Research/doc: observed (artifact present) + reviewed/accepted as applicable; `integrated` only if deployment required.
- States `not_started/in_progress/partial/implemented/verified/integrated/complete/blocked/unknown`
  are lifecycle labels on the episode; requirement states above are the gate inputs.

The brief's Worker example maps to `implemented, reportedly merged; integrated acceptance pending`
— exactly the honesty this rubric enforces. The Harness Repo-Scout rules hold:
manifest ≠ correctness, inventory ≠ passing, correction ≠ elimination, open gate ⇒ not complete.

## 4. Evaluator policy

Deterministic first (census, extraction, overlap, staleness). Intelligence only where needed:

- Cheap: requirement extraction, ambiguous tie-break assist.
- Standard: requirement satisfaction + gaps with cited evidence.
- Strong: contested/critical findings (`gpt-6-luna` independent review; Muse primary bulk).

Routing: `deepseek-v4.1-flash-free` → fallback `deepseek-v4.1-flash` →
Muse bulk → Codex `gpt-6-luna` strong → `claude-haiku-5-5` if needed.
Discover actual availability via existing model-routing (`research/inference.py`,
Worker `models/*`) in W1; track cost/tokens/latency/failures/escalations per evaluation.
Opening Mission Control or the tab never triggers model calls (same invariant as
`/api/git-activity`: reads are index-only; model catalogue loads on modal open).

Cache: `(source_digest, evaluator_identity, rubric_version)`; re-evaluate only affected
episodes/requirements when new messages/commits/reviews/evidence arrive.
