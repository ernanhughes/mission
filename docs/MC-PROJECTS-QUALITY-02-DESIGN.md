# MC-PROJECTS-QUALITY-02 — Evidence-Based Software Quality Evaluation: Design

## Reuse (no new gateways, no competing registries)

| Need | Reused implementation |
|---|---|
| Model resolution + execution | `research/inference.py::resolve_model` (Pi-first, explicit IDs) + `complete_chat` (consent-gated, usage/latency recorded) |
| Async review lifecycle | `activity_git/service.py::execute_review` pattern: queued→running→completed/failed, `_active_*` guard, prompt[:100k] cap, observed model/route/usage persisted |
| Structured JSON validation | `research/chat_service` + websites/scripts precedent: brace-extract, required-keys, range checks, `InferenceProblem`-style rejection, never invent |
| Second-opinion reviews | One row per review with a different model; disagreements recorded, never silently overwritten (git-review precedent) |
| Append-only history + derived freshness | `quality/service.py` (`previous_evaluation_id`, read-time `current/stale/historical`, NULL-overall unscoreable states) — pattern only, separate tables |
| Finding lifecycle vocab | Technical domain (`ACCEPT/REJECT/DEFER/INVESTIGATE`, verification methods/statuses, waive-with-reason, searched-scope) |
| Newest evaluation-domain shape | `website_post_evaluations` (own tables/ids, hash freshness, NULL overall, `previous_evaluation_id` chain) |
| Secret handling | `activity_git/service.py::redact_secrets` + SECRET_PATTERNS; paths never in prompts (project name only) |
| Cultivation reporting | `record_measurement/add_evidence/_record_event` for verified evidence; owner-only `set_stage/set_qualified/classify_repo/release_application` never called by the evaluator |
| Budgets | `prompt_max_chars` ∩ 95k hard cap, per-commit diff caps, `max_tokens 2048` local / 50k Pi output, 45–180s local / 120s Pi timeouts |

## New (separate `software_quality` domain)

- Tables (migration 038): `software_charters`, `software_evaluations` (`sqeval:`), `software_eval_reviews` (`sqrev:`), `software_findings` (`sqfind:`, deduped by `project_id+fingerprint`), `software_finding_reviews`, `software_prompts`. Cultivation untouched.
- `quality_software/rubric.py`: `software-quality-v1`, 10 dims/1000 pts, aggregation policy (overall only with ≥8/10 dims assessed incl. purpose+correctness; NA dims excluded from denominator with `max_attainable` reported; coverage% always shown).
- `quality_software/evidence.py`: bounded read-only collector → fingerprinted manifest (never executes repo scripts; test execution is separate/explicit).
- `quality_software/service.py`: charter CRUD + deterministic propose; request/execute evaluation; request/execute independent review; finding extract/dedupe/review/resolve; prompt save; cultivation report (evidence only).
- `api/software_quality.py`: charter/evidence/evaluate/review/findings/prompts/history/compare/cultivation-report endpoints.
- UI: Quality tab (overview/detail/history/actions), charter editor, Improvements wiring, cultivation-report action.

## Scoring rule (binding)

Missing evidence is neither failure nor success. Per-dimension: score | abstain | NA (with reason). Overall published only under the aggregation policy; otherwise overall NULL + coverage + unknowns. Comparability requires same rubric version; NA-set/head/charter diffs flagged, never silently compared.

## Pilots

Scratch backend + loopback Ollama (local only, no remote exfiltration) on Writer, Mission Control, and one small project; independent review on at least one pilot. Production AI enablement stays an explicit owner action (Settings → AI + consent); without it the Quality tab reports blocked, never fakes.
