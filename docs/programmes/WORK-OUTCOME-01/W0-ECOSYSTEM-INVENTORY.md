# W0-ECOSYSTEM-INVENTORY — Reuse before rebuild

Verified 2026-11-24 by listing `C:\Projects` + README/AGENTS, file globs, targeted grep
(`evaluat*|review|evidence|capability|workbench invocation`). Read-only, no modifications.

## Existence

| Requested | Path | Exists |
| --------- | ---- | ------ |
| mission | `C:\Projects\mission` | YES |
| workbench | `C:\Projects\workbench` | YES |
| worker | `C:\Projects\worker` | YES |
| ai | `C:\Projects\ai` | YES |
| inspect | `C:\Projects\inspect` | YES |
| writer | `C:\Projects\writer` | YES |
| praxis | `C:\Projects\praxis` | YES |
| next | `C:\Projects\next` | YES (canonical doc `next/docs/README.md`) |
| work | `C:\Projects\work` | YES |
| opencode-remembering (standalone) | `C:\Projects\opencode-remembering` | NO — vendored as `worker/packages/opencode-remembering` |

Others seen (not inventoried, do not reuse without verification):
`cocoder`, `steward`, `verity`, `evidence-repair`, `alive`, `sidecar`, `improve`, `bookbuilder`.

## Reuse map

### mission — coordinator / governance surface (primary build site)

Owns workflows, approvals, evidence timeline. Reuse: `quality*/cultivation/research-inference/publication`
evaluation; `workflows/service|templates|sandbox` + `api/workflows|benchmark*` review;
`tests/test_*.py` evidence; read-only `adapters/*`; `activity_git/service` + `inspect_snapshots`;
`research/*` history; `processes/manager` + `workflows/service (HttpWorkerClient, direct|opencode|opencode-work)`
+ Docker sandbox; `api/applications|writer|workflows` + `integrations/runner (run_tool)` + `adapters/base (ActionSpec)`.
Interfaces: `mission.cmd`, `scripts/*.ps1`, FastAPI `/api/*` (loopback + `X-Mission-Control-Request`),
PostgreSQL `mc` via `MC_DSN`, `data/integrations|experiments|backups|logs`, `config/defaults`.
**WORK-OUTCOME builds here as a workflow/template + adapter, not a parallel evaluator.**

### workbench — human-in-loop paragraph review + owned decisions

Chat workbench; author owns context, model proposes, deterministic checks gate, accepts become commits.
Reuse: `score.py/checks.py/quality_bridge.py` evaluation; `proposals/chapter_apply/gitops/editorial/receipts`
review; `doctor/runs/runrecords/ledger (JSONL)` evidence; `knowledge/*` semantics;
`capabilities/* + workflows/*` discovery; `history*` retrieval; `pi_manager` observation;
`service.py (editorial-decisions.jsonl)` + `app.py install(wb)` invocation.
Persistence: `WORKBENCH_HOME (.workbench/)`: `preferences.json`, `editorial-decisions.jsonl`,
`editorial-candidates.jsonl`, `runs/`, sessions/ledgers/scores.
**Reuse review UX + decision store.** Mission already reads `editorial-decisions.jsonl`
read-only + deep-links. Do not copy proposal/check/commit logic.

### worker — thin gateway to OpenCode runtime

Thin HTTP gateway; `POST /v1/work` canonical; stays thin, no silent fallback, no invented verdicts.
Evaluation **none owned** — delegated to `packages/opencode-{work,verify,proof,evidence,relate,authority,vfs,expertise,remembering,observability,runtime}`;
`opencode-remembering/HANDOFF.md` stages 3–9 real, Stage 10 matched evaluation planned not built.
Reuse: `executors/{opencode-work,opencode,direct,pi,model,opencode-docker}`; `translator` structured checks;
`tests/opencode*.test.ts` + `docs/V02-INTEGRATION.md`; `models/*` + `context-viewer`; `server/core/factory/config` + CLI/TUI.
Persistence: in-memory jobs; `worker.*.json`, `worker.models.yaml`, `MEMORY_BASELINE_DSN`.
**Reuse as execution/observation layer.** MC10/11 already call `POST /v1/work`
(`direct` = `AWAITING_ACCEPTANCE` vs `opencode-work` = genuine Acceptance). Do not reimplement routing/cost/viewer.

### ai — shared intelligence runtime

Writer-independent embeddings/retrieval/memory/inference/scoring.
Reuse: `scoring/*` + `experience/*` + `consolidation/*` evaluation;
`consolidation/chat/books` review; `retrieval/ranking/embed` semantics (deterministic/ollama/hnet);
`agents` Pi adapter + `books/git_adapter`; `memory/*` (episodes/events/evidence, namespaced) +
`events/bus` + `experiments` + `chat/importer` history; `inference/* + providers/{opencode,ollama,fake}` observation.
Interfaces: Python library only (`EmbeddingService/RetrievalService/MemoryRuntime/InferenceService/ConsolidationService`);
PostgreSQL+pgvector via `AI_DSN`; `alembic 0001/0002`; `pytest` (deterministic default, `integration` needs `AI_DSN`).
**Reuse semantic primitives via `ai.*`; do not fork.** Note AI-CORE-06 conditionally qualified, AI-CORE-07 not production-qualified.

### inspect — Pi-powered read-only capability inspector

Deterministic discovery + Pi evidence-backed `capabilities.json`, never modifies targets.
Reuse: `inspect.py (aggregate/validate/profile/daily-report)` + `prompts/inspect-repository.md` + versioned `schemas/`;
`inspect_cli.py correct` review; fixture+fake-pi tests; Pi read-only invocation;
`discover/inspect/inspect-all/aggregate/validate/status/snapshot/changes/daily-report/profile` CLI;
`output/{projects,status,repositories/<id>/{capabilities,dependencies,inspection},snapshots,profiles}` + `corrections/` + `config.json`.
**Reuse capability baseline.** `capabilities.json` designed for Mission; `inspect_snapshots.py` already ingests it. Do not build a second crawler.

### writer — long-form context engineering (largest duplication risk)

48 top-level commands; compiles manuscripts, tracks state, retrieves evidence, scores/repairs.
Reuse **via contracts only**: `writer editing {audit [--all|--chapter] [--profile technical-nonfiction-v1] [--json],summary,reports,show,status,compare}`,
`writer eval/capabilities/info` CLIs; `writer-web` FastAPI (editing/evidence/reviews/improve/gate/research);
Writer-owned `.writer/{editing,generation,metadata,eval}/` + `runs/reports/reviews`; Postgres via `--db`.
Mission already consumes `editing summary --json` + `editing audit --all --json` + `writer-editing-report-v1`
fingerprints, never parses manuscripts.
**Do not duplicate readability/scoring/repair code.**

### praxis — cross-domain effectiveness engine (closest analogue)

Read-only consumer of Mission goals/evidence; baseline-vs-candidate, independent acceptance, bounded proposals; never executes/approves.
Reuse pattern: `praxis/{effectiveness,experiment,evaluation,verdicts,adjudication,economics,contracts,protocol}.py`
(`praxis.effectiveness-record.v1`: goal, strategy versions, MC refs, acceptance, unknowns `None`, `retain|reject|insufficient_evidence`);
`{review_desk,diagnosis,readiness,selection_signals,governed_audit,technical_verification}`;
`tests/` offline deterministic; frozen `*-MANIFEST.json` + `docs/reviews/PRAXIS-*-REPORT.md`;
MCP stdio adapter (propose only, `confirm_proposal` required).
**Adopt `effectiveness-record.v1` + frozen manifest + independent acceptance + `insufficient_evidence` default. Do not fork a second effectiveness engine.**

### next — discovery engine (opportunity + gap source)

Rule-based discovery of better AI applications; falsifiable experiments.
Reuse as evidence source: `{evaluator,evaluation_metrics,...}` scoring; claim/scope/lineage audits;
`{dense,lexical,passage}_retrieval + embeddings` semantics; `next.db`/`data/` + `config.yaml` history;
`next {scan,report,show,explore,history,analyse,review,investigate,compose,frontier,validate,gaps,research,reassess,export --output --limit}` CLI;
`export.py (EXPORT_SCHEMA=next-research-export-v1)` versioned export; optional Postgres `NEXT_DSN`.
Mission reads Next read-only (PG SELECT-only / SQLite snapshot / `next-research-export-v1.json`); `run_discovery` disabled.
**Consume `export-v1` + gaps; do not reimplement discovery/scoring.**

### work — commercial opportunity→outcome engine (direct neighbour, highest duplication risk)

Demand → hypotheses → shortlist ≤3 → human decision → outcome → learning.
Already implements `opportunities --json`, `decide/outcome/yield/attribution/baseline/compare`,
`qualification/qual_audit/baseline/recommendations/intelligence/experiments`,
PostgreSQL-only (`WORK_DATABASE_URL`), CLI `work {... outcome,report,worker doctor,analyze,intelligence,yield,buyers,clusters,demand,evidence dossier,qualification audit,experiments plan,baseline capture,compare,attribution,web,dashboard}`.
Mission uses `work opportunities --json` read-only, never `work decide`.
**Coordinate, don't clone. Cross-cutting evaluation lives in Mission/Praxis, not a second `work` engine.**

### cocoder / steward / verity (provisional — verify before wiring)

- **cocoder**: evidence-backed cold reviewer (`review --base/--head/--working-tree --coverage-file --fail-on`, `dead-code scan`, `history/research/projections`); `.cocoder/{reviews,cocoder.db,...}` + SQLite events. **Reuse for change review** (Mission `run_review` already does; MC10/11 gate on high/medium). Do not reimplement detectors.
- **steward**: deterministic control plane (sync→worktree→contract→invoke→validate→report); `steward {init,status,sync,watch,report}`; SQLite ledger + `.steward/runs/<id>/report.md`. **Reuse pattern** if worktrees/isolation needed.
- **verity**: capsule→target→gates reliability (`capsule new|prep`, `ingest chats`, `export patch`, `replay run`); SQLite `verity.db` + `verity.toml`. **Reuse concept** (provenance + replayable gates); prove overlap with workflows/Praxis before adopting code.

## Wiring preference (to avoid second systems)

Prefer Mission adapters + `ActionSpec` + `run_tool`; Mission workflows; `POST /v1/work`
(preserve `direct` vs `opencode-work` semantics); Writer JSON contracts; Next `export-v1`/PG-readonly;
Work `opportunities --json`; CoCoder JSON review; Workbench JSONL + deep links;
Inspect `capabilities.json`; `ai.*` library; Praxis `effectiveness-record.v1` + frozen manifests;
Steward worktrees/ledger if isolation proven; Verity capsules/gates if provenance gap proven.
