# W5A-USER-GUIDE — Work Evaluation in plain language

**Application**: your running Mission Control (default
`http://127.0.0.1:8790`; this pilot ran against the operational instance).

**Finding it**: Activity (left nav) → **Work Evaluation** tab →
Overview | Work Episodes | Outstanding Work | Quality | Coverage.

**What you see first (Overview)**: how many coherent pieces of work were
reconstructed (episodes), how many are verified complete (expect 0 until
something is independently verified — that is honesty, not failure), what
needs attention (unfinished or unverified work with open findings, mandatory
first), and how much remains unevaluated.

**Inspecting an episode**: Work Episodes → filter or search → Inspect
episode. Tabs: Summary (objective + most important actions), Requirements
(each with authority, verdict and evidence state), Changes (repos + commits;
"no commits" on legitimate non-code work is normal), Evidence (participant
claims kept visibly distinct from verified results), Evaluation (execution /
outcome / completion + rationale + limitations), History (evaluations are
never overwritten).

**Finding unfinished work**: Outstanding Work lists every open finding with
what is wrong, why it matters, what evidence exists, what to do next, and
what would close it. Filter by type (missing requirement, defect,
verification gap, unsupported claim) and status. Suspected ≠ confirmed.

**Verifying evidence**: open the episode, check the Evidence tab for claim
vs verification state, follow source references (session locators, commit
SHAs) into the Changes tab or the existing Git views.

**Evaluating additional work deliberately**: there is no automatic
scheduler yet. Trigger paths that exist today:
- `POST /api/work-observation/runs {"project_contains":"<dir>"}` — observe.
- `POST /api/work-episodes/runs {"project_contains":"<dir>"}` — reconstruct.
- `POST /api/work-intent/triage/runs`, `POST /api/work-intent/extractions/runs
  {"episode_id":"…","backend":"deterministic"}` — triage + extract.
- `POST /api/work-evaluation/runs {"episode_id":"…","semantic":false}` —
  deterministic evaluation (no model calls). With `"semantic":true` and an
  enabled governed backend, one bounded model pass runs (budget-enforced).
A scripted sequence of the above is the manual mechanism until W6.

**What happens automatically**: nothing, by design. Opening pages never
triggers observation, reconstruction, extraction or evaluation. Freshness
comes from explicitly running the pipeline; staleness is shown, not hidden.

**What does not happen yet**: continuous monitoring, automatic follow-ups,
cross-project rollout, verified-complete verdicts at scale (no exemplar yet).
