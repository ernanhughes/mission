# W0-IMPLEMENTATION-PLAN — Staged, gated, no second systems

## W0 exit → W1 entry (must all hold)

- [ ] This directory reviewed; GO or CONDITIONAL GO recorded with pre-W1 actions closed.
- [ ] No app-code edits, migrations, UI builds, commits, pushes, or bulk AI analysis performed in W0 (assert: `git status` clean of W0 artefacts except `docs/programmes/WORK-OUTCOME-01/`).
- [ ] Model-routing availability re-confirmed (`research/inference.py`, Worker `models/*`); costs/tracking design signed off.
- [ ] `.workbench` allow-list decision + retention policy for episode tables recorded.

## Stages

**W1 — Read-only observation.** OpenCode HWM poller (`mode=ro`, body-free, sidecar HWM,
`locked`-retry, re-census deletes) + `ai`-project git-index join. No new IDs invented.
Acceptance: HWM advances without writes; WAL-consistent reads proven; seven-case census recorded.

**W2 — Reconstruction + correlation.** `041_*.pg.sql` episode/association tables (ORM-first per conventions);
SHA/tool/ID/repo/file-overlap extractor; patch-id/trailer + `old→new` map; cross-repo manifests;
confidence scorer with abstention. Acceptance: many-to-many links with provenance; weak-only ⇒ `unknown`.

**W3 — Requirements + evidence.** Cheap-AI requirement draft (human-checked in pilot) + evidence attacher
(commit/test/review/demo digests). Acceptance: every requirement has locator + state; claims labelled.

**W4 — Evaluation engine.** Rubric scorer (deterministic + cached AI), dimension reasons + refs,
no composite score. Contested/critical → strong model. Acceptance: `reported` never completes;
stale derived at read; cost/latency tracked.

**W5 — Activity tab.** `evaluation` tab + drill-down + filters + explicit re-evaluate/waive (confirm-gated).
Reads index-only. Acceptance: unfinished work default view; 83-frontend-test pattern extended.

**W6 — Incremental + reconciliation.** New-message/commit/review/evidence watcher; affected-only re-eval;
obligation dedupe by stable hash; retention policy enforced. Acceptance: closing work resolves
existing obligation, no duplicates; interrupted replay idempotent.

**W7 — Follow-ups.** Propose-only `FollowUp` → ActionSpec/confirmation → new episode linkage.
Acceptance: evaluator never auto-executes; execution boundaries (Docker/Worker) preserved.

**W8 — Instrumentation.** Emit explicit episode/task IDs (session metadata, Workbench invocation,
review commission, commit trailers, `ExperimentWorkflow` link). Acceptance: new work needs no inference.

**W9 — Calibration + rollout.** Rubric calibration corpus (NOT the ~2-min Writer corpus as routine gate;
record as deliberately-deferred `long` per test policy); portfolio rollout beyond `ai` pilot.
Acceptance: portfolio view with known limits; per-short-suite verification named, long suites deferred explicitly.

## Ownership

`mission`: episodes, evaluation state, Activity UI, follow-up management.
`workbench`: governed invocation surfaces + decision JSONL (read). `worker`: execution/observation.
`ai`: retrieval/memory/inference/scoring primitives (depend, don't fork).
`inspect`: capability baseline (consume). `writer`: editing contracts (consume).
`praxis`: effectiveness-record pattern (adopt). `opencode-remembering`: retrieval mechanisms (reuse).
New tables in Mission PG only; OpenCode DB stays read-only source.

## Cost / risk

Deterministic-first keeps marginal cost near zero; AI spend only on комнате requirement drafts,
ambiguous links, and evaluations — all cached by `(source_digest, rubric_version, evaluator_identity)`.
Top risks: OpenCode deletes (no tombstones) → re-census; rebase/squash aliasing → patch-id map;
unlinked test evidence → W2 join; `.workbench` blindness → allow-list; seed `ai.enabled` discrepancy → re-confirm gate.
