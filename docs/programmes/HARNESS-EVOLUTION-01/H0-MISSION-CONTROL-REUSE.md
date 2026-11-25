# H0 — Mission Control reuse

## Existing control-plane capabilities

Mission already has project/application registration, adapters and ActionSpec contracts, confirmed action execution, workflow lifecycle/approval, immutable approval scope hashes, CoCoder review gates, Docker-isolated experiment execution, process supervision, activity/repository observation, model/research interaction, and evidence-oriented project records. Worker is registered as a local service and called from Mission's experiment workflow client. These are direct reuse candidates for governance and orchestration.

The active Work Outcome programme extends this with work observation, episode reconstruction, intent (objectives, requirements, claims), and outcome evaluation. Its current programme records conditionally accept W0–W5 and state W8 prospective harness instrumentation is not started. Several Mission source and test paths for Work Outcome are currently untracked/modified; their presence is discovery evidence, not a claim of clean release qualification. No tests were run during H0/H1.

## What Mission should own in the candidate architecture

- workflow admission, human approval, and scope/version binding;
- cross-system goal/episode correlation and operational observation;
- evaluator/version registry and protected acceptance-set governance;
- action registry, safe launch and isolation policy;
- truthful display of unknown, stale, not-run, blocked, or insufficient-evidence states.

Mission should not become a second model/agent loop. It can initiate Worker executions and join evidence without copying full OpenCode conversations or taking ownership of Writer's evaluators.

## Evidence and limits

- Current source: `backend/mission_control/integrations/`, `workflows/`, `processes/`, `discovery/`, `api/`, `config/defaults/applications.yaml`.
- Work Outcome: `docs/programmes/WORK-OUTCOME-01/WORK-OUTCOME-01-PROGRAMME.md`, W0–W5 reports, and current uncommitted `backend/mission_control/{work_observation,api/work_episodes.py,api/work_intent.py,api/work_evaluation.py}`.
- Earlier MC inventory documents static/read-only capabilities and disabled launches; current evidence must be distinguished from that older snapshot.
- `PROJECT-INTELLIGENCE.md` says STALE. It was not used as sole evidence.

## H2 boundary question

Work Outcome and Praxis both represent outcome/effectiveness. Preserve their distinctions: Mission records intent, operational execution, requirement/evidence status and governance; Praxis records cross-domain effectiveness comparisons and advisory strategy decisions. A shared reference or adapter may connect these; an overlapping duplicate evaluator is not justified by current evidence.
