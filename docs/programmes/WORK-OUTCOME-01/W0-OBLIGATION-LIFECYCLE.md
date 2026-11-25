# W0-OBLIGATION-LIFECYCLE — Gaps that survive until closed by evidence

## 1. What creates an obligation

Requested-but-unimplemented · partially implemented · missing verification ·
reported-but-unexecuted tests · unmerged/undeployed where merge/deploy required ·
unsupported completion claims · known defects · deferred work · unresolved architecture ·
repeated failures · exists-but-unusable-through-intended-interface.

Each obligation: `(episode_id, requirement_id?, text, kind {mandatory, recommended},
state, provenance {observed, claimed-gap, inferred, verified}, evidence_refs,
created_by {rule, evaluator/rubric}, created_at)`.

Distinguish mandatory (blocks `complete`) from recommended (does not block, still listed).
Preserve legitimate exclusions: `waived` requires human reason + identity, never auto-waived.

## 2. States

`open → in_progress → resolved | waived | obsolete`.
`resolved` requires `resolved_by_ref` (commit/test/review/demo digest), not a new claim.
`obsolete` requires superseding requirement/revocation proof.
All transitions append-only with actor + timestamp (precedent: `WorkflowEvent(sequence)`,
`quality_reviews` author verdicts, `GitReviewFeedback` ratings).

## 3. Reconciliation (no duplicates)

Stable obligation identity: `sha1(episode_id | requirement_seq | normalised_text | kind)`.
Later work addressing the same gap links to the existing obligation and flips state;
it never creates a duplicate recommendation. New scan matching open obligation ⇒
attach evidence + re-evaluate that requirement only. Changed requirement text ⇒
new revision supersedes, old marked `obsolete` with link.

## 4. Detection rules (W2/W4, deterministic + evidence-bound AI)

Deterministic: requirement without `observed` ⇒ open; `reported` without `tested/verified` ⇒
missing-verification; `observed` without required merge/deploy ⇒ unintegrated;
claim of merge without `git_commits` proof ⇒ unsupported-claim; repeated identical
failures across sessions ⇒ repeated-failure obligation.
AI-with-evidence: partial implementations, missing edge coverage, architecture drift,
usability gaps — each with cited excerpts + digests, abstaining when evidence absent.

## 5. Relationship to follow-ups

`FollowUp(obligation_id, action, status, created_episode_id?)` proposes; evaluator never executes.
Execution reuses Mission ActionSpec/confirmation + Worker/Docker boundaries.
Closing the loop is itself an episode eligible for evaluation.
