# ALIVE-RESEARCH-02 — Independent Mission Control Purpose and Capability Investigation

**Date:** 2026-11-22
**Repo:** `C:\Projects\mission` (README describes MC09/MC10/MC11/MC-WRITER-01/MC-LIVING-BOOK-01 as implemented)
**Mode:** Research only. No code, schema, manuscript, or integration changes. No commits/pushes. No paid model calls.
**Method:** Source, docs, architecture, API routes, persistence models, frontend pages, tests, and acceptance reports inspected directly. Significant claims cite exact paths. This report was written without using ALIVE-RESEARCH-01 as an input.

---

## 1. Executive summary

Mission Control is a **local-first coordination and presentation layer** for an existing ecosystem of AI applications, books, research programmes, and commercial projects. Its own README states the boundary in one sentence: "It does not replace those systems. It coordinates them: what matters today, where work stopped, which evidence exists, what can be launched safely, and what should happen next." (README.md:3) and "Mission Control decides what should be presented and coordinated; the existing systems keep doing their own work." (docs/MC01-ARCHITECTURE.md:28).

Concretely it is: **registry + read-only adapters + bounded process control + human-owned continuity (projects, books, checkpoints, tasks, decisions, activity) + hardened experiment workflows + reading/governance surfaces (Living Book gateway, Writer evidence, Praxis proposal import)** — all served as one FastAPI + SQLite backend (loopback `127.0.0.1:8790`) and one React/Vite frontend, with deterministic defaults and optional, explicitly-consented local AI.

**What it is not:** not a project-management SaaS, not a general orchestrator that absorbs Next/Work/CoCoder/Writer/ALIVE, not a model-training or self-improving harness. The architecture docs explicitly disclaim a "global knowledge graph, autonomous planner, universal workflow language or chatbot controlling all tools" and "no cross-repository write operations / publishing action / paid model call" (docs/MC01-ARCHITECTURE.md:270-276). Every engine remains independent and owns its domain data (docs/MC09-ARCHITECTURE.md:3-20).

**Strongest demonstrated capabilities (evidence-backed):** application registry with safe Windows process launch/stop/reattach; read-only Next/Work/CoCoder/Writer adapters with failure isolation; unified inbox + federated SQL search; book manuscript detection + project workspaces with checkpoints/resume; MC10 TraceLite → Worker → deterministic tests → CoCoder review → human decision loop with hash-bound approval; MC11 Docker-sandboxed generated-code execution with truthful lifecycle, cancellation, and `language.observation.v1`; Living Book reading-room gateway to ALIVE with quality-context discipline (no composite score, `NOT_RUN`≠0); Writer editing evidence + decision queue as read-only presentation; Praxis governed proposal import/approve/execute with digest binding and human-only authorization.

**Where the adaptive-execution question stands:** Mission Control has real orchestration *machinery* (templates, approvals, sandboxes, observations, evidence timelines) and one complete cross-application workflow family (MC10/MC11) with measured outcomes (TraceLite 21→3 events, 85.7% reduction). What it does **not** demonstrate is a closed learning loop in which previous execution outcomes automatically improve subsequent decisions — observations are explicitly read-only ("never rewrite the intention… do not control execution; do not trigger corrections" — docs/MC11-TEMPLATES-AND-LANGUAGE.md:149-155). No ECK (Executive/Executable Cognitive Kernel) implementation was found in this repo; "Praxis" here is an external proposer whose advisories Mission imports under governance, not an in-repo kernel. Any claim that the harness improves outcomes beyond the underlying models is **unproven by the retained evidence** (see §5, §8).

**Independence answers:** Without ALIVE, Mission Control remains a working control centre for books, projects, applications, experiments, Writer evidence, and daily continuity (§8). The evidence required to show harness-level improvement would be controlled comparisons with pre-frozen tasks, blinded judging, and retained receipts — none present for the harness itself (§8).

No integrations are proposed in this report.

---

## 2. Purpose and historical development

| Question | Finding (grounded) |
|----------|--------------------|
| 1. Why created? | Fragmented ecosystem (Next, CoCoder, Work, Writer, Improve, BookBuilder, Worker, Stephanie, Workbench, books, research) with no shared view of priority, stopped work, evidence, safe launch, or next step. "What matters today, where work stopped, which evidence exists, what can be launched safely, and what should happen next." (README.md:3) |
| 2. Problems solved? | (a) Priority/focus drift → Today + focus + resume card; (b) lost continuity → checkpoints/tasks/decisions/activity per project; (c) unsafe or ad-hoc launches → registry with verified launch definitions, `shell=False`, allowlisted env, ownership-verified stop; (d) unverifiable engine claims → read-only adapters with source identity, timestamps, staleness, diagnostics; (e) ungoverned codegen → hash-bound approval + Docker sandbox + deterministic tests + independent review (MC10/MC11); (f) manuscript Q&A without provenance → reading room with exact chapter reads + receipts + quality discipline. |
| 3. Fundamental responsibility? | **Coordination + presentation + governance of launches and experiments.** It owns the registry, the read models, the continuity records, the approval/execution records, and the presentation. It explicitly does not own engine domain logic, manuscript bytes, quality scores, or model inference. |
| 4. What kind of system? | Primarily a **coordination layer with a dashboard**, secondarily a **capability-discovery surface** (adapters declare capabilities/actions; registry declares launch/monitoring), and tertiarily a **bounded experiment harness** (MC10/MC11 templates + sandbox). It is not a PMS (no scheduling/resource allocation), not a workflow engine that absorbs engines, not an agent framework. |
| 5. How purpose evolved? | Traceable in docs: MC01 (registry, projects, books, discovery, briefing, adapters) → MC09 (unified Next/Work/CoCoder workspaces + inbox + federated search + controlled CoCoder review) → MC10 (first complete Next→Worker→CoCoder→human workflow) → MC11 (hardened reusable mechanism: Docker, 2 templates, cancellation, Language observations, evidence timeline) → MC-WRITER-01/02 (read-only editing evidence + decision queue) → MC-LIVING-BOOK-01 (reading room gateway) → MC-NEXT-CHAT-01 (research export + local chat) → MC-PRAXIS-07/09/10/11/15 (governed external-proposal import, preflight advisories, scoped Writer audit, bounded arithmetic verification) → MC-PROJECTS-QUALITY-01 Phase 02 (software-project cutover, 40 workspaces, quality workspace without scoring — "No quality scoring — that is the next dedicated milestone" — docs/MC-PROJECTS-QUALITY-01-PHASE-02-REPORT.md:7). Direction: more engines surfaced, stronger execution guarantees, stricter evidence discipline — without absorbing engines. |
| 6. Valuable without ALIVE? | Yes: book/project continuity, application launch/control, Next/Work/CoCoder/Writer read models, inbox/search, MC10/MC11 experiments, Writer review queues, checkpoints/resume, deterministic briefing. The Living Book card degrades to `unavailable` with project evidence intact (docs/MC-LIVING-BOOK-01.md:135-144). See §8. |
| 7. Belongs to others? | Research candidacy (Next), job opportunities (Work), code findings (CoCoder), readability/editing evidence (Writer), manuscript bytes (books repos), generated-code authorship (Worker + local model), book intelligence (Writer/BookBuilder), publication destinations (external). Mission stores associations, decisions, and execution records — never source truth. |
| 8. Long-term goals not implemented? | Quality scoring (QUALITY-02), publishing actions, paid-model operations, cross-repository writes, full conversation capture, Work/Improve/Stephanie adapters ("no verified read-only contract was available"), explicit cancellation/streaming/idempotency in MC09 (added later in MC11 for workflows only), autonomous planning. All listed as omissions/future, never faked (MC01-ARCHITECTURE:270-276; MC09-ARCHITECTURE:150). |

---

## 3. Architecture

### 3.1 Runtime

```text
Browser / local client
  -> FastAPI (origin guard + X-Mission-Control-Request on mutations, loopback-only)
  -> Routers (backend/mission_control/api/*.py, typed Pydantic contracts)
  -> Services: registry | projects/books | processes | discovery | adapters |
                briefing | workflows | living_book | writer | praxis_proposals |
                quality/publication/technical/cultivation/websites/research
  -> SQLite (data/mission_control.db, numbered migrations, FK on) + per-process logs
  -> Managed detached Windows children / Docker sandbox / external CLIs / ALIVE HTTP
  -> React SPA (frontend/src, served by backend :8790; Vite :5173 dev only)
```

Stack: Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, SQLite, PyYAML, httpx, psutil; React 19, TS, Vite, React Router, custom CSS, Lucide. No Docker/hosted DB/cloud/broker required for core; Docker Desktop required only for generated-code execution (README:239-257; MC01-ARCHITECTURE:30-37).

Key design points (docs/MC01-ARCHITECTURE.md): shipped YAML defaults inserted only when ID absent; discovery updates observation fields only; **user SQLite edits always win** (134-144). Request flow: origin guard → routers → registry/project/process/discovery/adapter/briefing services → SQLAlchemy/SQLite + FS logs; browser never supplies executables (100). Loops are background (discovery/adapter refresh); dashboard stays up on adapter failure; timeouts everywhere; states reconciled on read/startup (259-268).

### 3.2 Persistence (docs/MC01-ARCHITECTURE.md:102-133; models.py; migrations/)

Core tables: `applications, launch_definitions, process_instances, health_observations, projects, books, outcomes, repositories, project_repositories, project_relationships, activity_events, work_checkpoints, tasks, recommendations, decisions, adapter_statuses, settings, discovery_roots, briefings`. MC09 adds `integration_records, integration_decisions, integration_executions` (migration 002). Praxis adds `praxis_proposals` (033) + preflight columns (034). Identity cutover adds `repo_uid/origin/project_identity_decisions` (036). Language adds `language_observations`. Numbered SQL migrations applied once, recorded in `schema_migrations`; explicit repeatability tests.

Identity rule: stable IDs; **paths are not primary keys**; `repo_uid` (Git) or normalized path; book-legacy IDs preserved with suffixing on collision (QUALITY-01-P2 §2).

### 3.3 Execution and safety boundaries

- **Launch:** stored definition only (native exe + arg array + cwd + allowlisted env + optional health); `.cmd/.bat/.ps1` rejected; port conflicts refused, never seized; detached `CREATE_NEW_GROUP|DETACHED_PROCESS`, per-process log, stdin DEVNULL; stop requires PID+creation-time match, children terminated via psutil; restart reattaches or marks lost, never kills guessed PIDs (158-176).
- **Actions:** browser sends action ID + typed params; must be registered + enabled; schema + adapter validation before queue; `confirm=true` for approval-required; single queued/running per app; context limited to registered repos + data dir + allowlisted env (MC09:137-151).
- **Workflows (MC10/MC11):** approval bound to hash(objective, exact file scope, repo, baseline commit, file hash, Worker config, prompt); stale/baseline/file/sandbox dirtiness rejected; exactly one approved path; AST/import/dunder/dangerous-call checks; `git diff --name-only` must equal scope; Docker read-only mount, no net, non-root, no caps, 512MB/0.5CPU/64PIDs/64MB tmpfs, host timeout, forced removal; no host fallback; duplicate-execute rejected; cooperative cancellation at safe boundaries, never adopting uncommitted patches (MC11 doc:58-110).
- **AI:** disabled by default; needs `ai.enabled + ai.consent + loopback OpenAI-compatible base URL + model`; key by env name only, never stored/returned/logged; deterministic briefing always retained on provider failure; AI advisory only — no launches, writes, publishes, or spend (README:535-547).
- **Research chat (MC-NEXT-CHAT-01):** local-only, loopback endpoint, models discovered from endpoint, remote refused; per-conversation evidence snapshot; Next never written.
- **Living Book gateway:** Mission→ALIVE server-side; base URL from registered `alive` app `adapter_config.base_url` or `MISSION_CONTROL_ALIVE_URL`, must be loopback; browser URL never becomes outbound target; 30-day read-only live approval; revocation supported (MC-LIVING-BOOK-01:85-100).

---

## 4. Complete capability inventory

Status: **IV** = Implemented + independently verified (acceptance/tests/browser evidence) · **INV** = Implemented, not independently verified here · **P** = Partial · **D** = Designed, not implemented · **E** = Experimental.

| ID | Capability | Purpose | Owning module | Entry / API / UI | Inputs → Outputs | State | Deps | Tests | Status | Limits / evidence |
|----|------------|---------|---------------|------------------|------------------|-------|------|-------|--------|-------------------|
| M-01 | Application registry | CRUD + launch/monitoring definitions, relationships | `registry/`, `api/applications.py` | `/applications`, `GET/PATCH /api/integrations*` | identity+paths+launch → status/actions | `applications, launch_definitions` | — | `test_registry_and_projects.py`, `ApplicationsPage.test.tsx` | **IV** | No invented commands; unverified disabled by default (README:452) |
| M-02 | Windows process control | Safe launch/log/stop/reattach | `processes/`, `api/processes.py` | Applications page Launch/Logs/Stop | definition ID + confirm → owned process | `process_instances, health_observations` | psutil, native exes | `test_processes.py` (real launch/stop/reattach incl. restart) | **IV** | Grandchild-of-wrapper may read lost; external listeners never stopped/seized |
| M-03 | Project/book workspaces + continuity | Focus, checkpoints, tasks, decisions, resume | `projects/`, `api/projects.py` | `/projects`, `/projects/:id`, Today resume | human text → checkpoint/focus/next | `projects, books, work_checkpoints, tasks, decisions` | — | `test_continuity_and_briefing.py`, `test_registry_and_projects.py` | **IV** | All user-maintained; Git never treated as completion (README:467) |
| M-04 | Book + manuscript detection | Find `content/books` manuscript trees, dedupe aggregators | `discovery/`, `projects/registration.py`, `api/discovery.py` | Settings roots, scan, candidates | roots → candidates + evidence | `repositories, discovery_roots` | Git (read-only) | `test_discovery.py`, `test_book_detection.py`, `test_software_classification.py` | **IV** | Bounded depth/count/time; symlinks skipped; advisory only, never auto-creates apps/launches |
| M-05 | Software project cutover (QUALITY-01 P2) | Deterministic auto-registration + engineering workspaces | `projects/registration.py`, `api/projects.py` identity/software routes | Projects Software default, ReconcilePanel, SoftwareWorkspace | scan → preview → confirmed apply → 40 workspaces | `repo_uid, origin, project_identity_decisions` (mig 036) + backup | Git index | `test_project_identity_cutover.py`, `test_projects_reconciliation.py`, `SoftwareWorkspace.test.tsx` | **IV** | 39 eligible/47 review/5 skipped on real data 2026-11-22; full backend 667+1 skip; quality scoring explicitly deferred |
| M-06 | Next adapter (read-only) | Live candidates, runs, gaps, experiments | `adapters/` (next), `api/integrations.py` | `/next` workspace + `/inbox`, `/search` | `NEXT_DSN` → resources | `integration_records/decisions` | Next PG/SQLite | `test_adapters.py`, `test_integration_api.py` | **IV** | SELECT-only + `read_only=on`; SQLite fallback `mode=ro`; bounded (200/20/50/500); discovery launch blocked; labelled compatibility, not stable API |
| M-07 | Work adapter (read-only) | Opportunities + qualification | `adapters/` (work CLI) | `/work` workspace | `work opportunities --json` → resources; 130 live in acceptance | `integration_records` | Work CLI | adapter + integration suites | **IV** | No `work decide`/DB writes; sync blocked; decisions `local_only` |
| M-08 | CoCoder adapter + review action | Findings + bounded repo review | `adapters/` (cocoder), `api/integrations.py` actions | `/cocoder`, Operations review (confirm) | registered repo + refs → review artifact | `review-*.json` + sidecars under `data/integrations/cocoder` | CoCoder CLI | adapter/integration/execution tests | **IV** | State redirected under Mission data; no `.cocoder` in reviewed repo; no tracked-file modification; ack ≠ verification |
| M-09 | Unified inbox + federated search | One attention queue + one search surface | `api/` inbox/search, `research/` | `/inbox`, `/search`, `Ctrl+K` | query → attributed results + deep links | read model over `integration_records` + tasks/checkpoints/decisions | adapters | `test_integration_api.py`, Inbox/Search tests | **IV** | SQL text only, no vectors; per-source caps; decided items leave queue; titles never merged |
| M-10 | Controlled action execution | Registered validated ops with durable history | `adapters/base.py`, `integrations/`, `api/integrations.py` | Operations tabs; `POST …/actions/{id}/execute` | action ID + typed params + confirm → execution | `integration_executions` | adapters | execution/validation tests | **IV** | Next/Work writes blocked; only CoCoder review + Writer audit + technical verify + Worker-via-workflow implemented |
| M-11 | Cross-app experiments MC10 | Next→proposal→Worker→tests→CoCoder→human | `workflows/`, `api/workflows.py` | `/workflows`, TraceLite propose/approve/execute/review/decide | Next export v1 → patch → measurements → review → decision | workflows + events + tags (`mc10-baseline`) | Worker `:7317` + local Ollama + Next export | `test_workflow_service.py`, `test_sandbox.py`, MC10 acceptance | **IV** | One template; `direct` executor lower-parity (`AWAITING_ACCEPTANCE`, never presented as verified); deterministic tests gate; CoCoder high/medium blocks auto-accept |
| M-12 | Hardened templates + Docker MC11 | Reusable bounded codegen with truthful lifecycle | `workflows/templates.py`, `api/workflows.py` cancel/project/events | `/workflows`, brightness fixture | template ID → executed→reviewed→decided + `language.observation.v1` | workflows + `language_observations` + timeline | Docker image `mission-control/sandbox-python:3.13` | sandbox/cancel/dup-guard/template tests + MC11 acceptance | **IV** | 2 templates (TraceLite next_export; brightness fixture, no prod media); host fallback refused; observations read-only, never control execution |
| M-13 | Living Book gateway + reading room | Open manuscript with ALIVE companion + quality | `living_book/`, `api/living_book.py`, `frontend LivingBook*` | Book card → `/projects/:id/read`; `/api/living-book/…` | project → candidates → approval → book/chapters/notes/ask | **No new Mission table**; ALIVE ledger owns state | ALIVE loopback `:8000` + Pi/Meta | `test_living_book.py`, `test_living_book_{improvement,represent}.py`, `LivingBookPage.test.tsx`, mc-living-book-01 acceptance | **IV** | Distillation 42 chapters + Language 39 chapters verified live 2026-11-19; images contained; 409 on changed chapter; quality deterministic Mission data, ALIVE only explains |
| M-14 | Writer editing evidence (MC-WRITER-01) | Read-only readability reports + six subdimensions | `adapters/writer.py`, `writer/service.py`, `api/writer.py` | `/writer`, cross-book queue, chapter drill | Writer CLI JSON → queue + findings + staleness | `writer_editing_book` resources | Writer exe | `test_writer_adapter.py`, `test_writer_api.py`, `test_quality_writer.py`, MC-WRITER-01 acceptance (+real Chrome) | **IV** | Never parses/scores manuscripts; `NOT_RUN/STALE/PARTIAL/ERROR` preserved, never zeroed; audit writes only Writer-owned artifacts |
| M-15 | Writer decision queue (MC-WRITER-02) | Prioritized findings + Confirm/Dismiss/Defer | `writer/{queue,decisions}.py` | Writer queue + deep link to Workbench passage | findings → ordered queue + local dispositions | Mission decisions (Workbench-owned state read back read-only) | Writer + Workbench | `test_writer_decisions.py`, `test_writer_campaigns.py` | **IV** | Reading order, not score; no composite invented |
| M-16 | Quality + publication assessment | Prose evals, technical claims, readiness, artifact load | `quality/`, `publication/`, `technical/`, `artifact_load/`, `api/quality.py|publication.py|technical.py|artifact_load.py` | Project Quality tabs, readiness gates | chapters/claims → dimensions + coverage + gaps | `quality_evaluations`, technical claims (1245), verifications | Mission DB + Writer reports | `test_quality*.py`, `test_publication.py`, `test_technical*.py`, `test_artifact_load*.py` | **IV (presentation + provenance)** / **P (verification: bounded arithmetic only; 1245 claims fail freshness — honest, not executed)** | No averaging, no verdict-from-score; technical verify = rational arithmetic, allowlisted props, no claim-status mutation, 0 live executions (PRAXIS-15:31-46) |
| M-17 | Praxis governed proposals | Import external advisories; human authorizes; existing machinery executes | `praxis_proposals/`, `api/praxis_proposals.py` | `/api/praxis/proposals[/{key}/approve|reject|execute|evidence|withdraw]` | proposal v1 → digest → approval → execution → evidence | `praxis_proposals` (033/034) | IntegrationService + ActionSpecs | `test_praxis_proposals.py`, `test_writer_scoped_audit.py` (30 passed) | **IV** | Single executable step (pilot); typed bindings not yet; import inert; `pi/praxis/agent/system` cannot approve; preflight advisory (`blocking=false` always); test-owned withdraw only |
| M-18 | Inspect + capability discovery | Snapshot engine/other-repo capabilities and opportunities | `inspect_snapshots.py`, `api/inspect.py`, `research/`, `frontend Inspect*` | Project Inspect tabs, SoftwareWorkspace Capabilities | repo → snapshot + opportunities | snapshots + `integration_records` | target repos | `test_inspect.py`, `InspectPage.test.tsx` | **IV** | Discovery maps to snapshots; launch-by-discovery blocked |
| M-19 | Activity + Git evidence | Normalised timeline + read-only repo observation | `activity/`, `activity_git/`, `git/`, `api/git_activity.py|activity.py` | Activity page, project Activity tabs | repos → commits + events | `activity_events` + Git index | Git CLI | `test_git_activity.py`, `test_git_daily.py`, `test_activity*` | **IV** | Read-only, timeouts; no fetch/heavy scans; backfill pending honestly flagged |
| M-20 | Briefing (deterministic + optional AI) | Grounded daily items, optional advisory interpretation | `briefing/`, `api/briefing.py` | Today briefing | priorities/checkpoints/tasks/recs → ranked items | `briefings` | optional loopback OpenAI-compatible | `test_continuity_and_briefing.py` | **IV** | AI needs enabled+consent+endpoint; failures retain deterministic + report |
| M-21 | Research export + local chat | Copyable critical-review package + persisted snapshot-grounded chat | `research/`, `api/research.py`, `ResearchChatPanel.tsx` | Next opportunity Copy/Discuss | opportunity → frozen package → chat | conversation + snapshot | loopback model only | `test_research_chat.py` | **IV** | Never writes Next; freshness notice on later refresh; remote refused |
| M-22 | Publishing / cultivation / websites / scripts | Evidence, posts, site cultivation, script library | `publication/`, `cultivation/`, `websites/`, `scripts/`, APIs | Publishing/Workflows/Scripts/Websites pages | repos → evidence/posts/checks | misc tables + files | various CLIs | `test_publication.py`, `test_publishing_*.py`, `test_cultivation*.py`, `test_scripts_*.py`, `test_mc_website*.py` | **IV (read/evidence)** / **P (publishing actions — architecture, no autonomous publish)** | No publishing/spend automation |
| M-23 | Settings, health, security posture | Validated config, diagnostics, loopback enforcement | `settings/`, `core/`, `api/settings.py|health.py` | Settings, Integrations diagnostics | config → validated state | `settings, adapter_statuses` | — | `test_security.py`, `test_budget_enforcement.py`, `test_evidence_safety.py` | **IV** | Secrets by env name only; logs redacted; traversal/device/relative rejected |

**Not implemented (D):** ECK as an in-repo kernel (no module found; see §5); autonomous planner/policy learner; Work/Improve/Stephanie adapters; publishing/monetization actions; vector search; cross-repo writes; paid-model operations; quality scoring (QUALITY-02); full conversation capture.

---

## 5. Execution and cognitive architecture (Praxis / ECK / harness)

### What exists (with paths)

- **Adapter protocol `mc09.1`** (`adapters/base.py`): capabilities, ActionSpecs (id, schema, risk, side effect, approval, enabled reason), `refresh/validate_action/execute_action`, resource envelope with `source_version/source_timestamp/observed_at/stale_after_seconds/evidence/data`, `current`-flagged snapshots. Controlled, cancellable-safe, failure-isolated.
- **Workflow engine** (`workflows/`, `api/workflows.py`): template registry (`templates.py` — code, not browser input), hash-bound approval, Docker execution, AST/patch/scope gates, deterministic measurement, CoCoder review gate, human accept/reject/investigate, idempotent replay, cooperative cancellation, project evidence timeline (`GET /projects/{id}/evidence-timeline`), durable event polling (`GET /workflows/{id}/events`).
- **Language records** (`language.observation.v1` + `language.intention.v0`): intention stored per workflow; observations emitted after measurement with expected/observed/difference/method/evidence/provenance/uncertainty/constraint_result; stored in `language_observations`; explicitly **do not rewrite intention, control execution, or trigger corrections** (MC11:149-155).
- **Praxis interface** (`praxis_proposals/` + `api/praxis_proposals.py` + docs MC-PRAXIS-07/09/10/11/15): import (idempotent, 409 on digest mismatch) → advisory preflight (runtime stats, timeout risk, book resolution; `blocking=false`) → human approve (identified human, digest match, `confirm:true`) → execute via existing IntegrationService + ActionSpec confirmation → evidence (correlation/goal/recipe/content/approval/execution ids + `evaluation_boundary`). Scoped Writer audit + bounded arithmetic verification are the first governed actions. Pilot proposal `prop-1795219304-3110bda8@1` sits at `awaiting_approval` — imported, validated (21 checks), **not approved, not executed** (PRAXIS-11:33-39).
- **Inspect/research/briefing**: snapshot + opportunity surfacing, frozen-package export, snapshot-grounded chat, deterministic briefing with optional advisory AI.

### The 10 execution questions

| # | Question | Answer |
|---|----------|--------|
| 1 | How is work represented? | Projects, books, tasks, integration resources (typed envelopes), workflows (template + lifecycle + events), proposals (versioned digests), checkpoints/decisions, language intentions/observations. No universal task ontology. |
| 2 | How are goals selected? | **Human-selected.** Focus, priorities, ordering, scope acknowledgement are human. No goal-proposing policy found. |
| 3 | How are actions chosen? | **Human- or template-chosen from registered ActionSpecs.** Browser sends ID + params; validation + confirmation gate. No action-policy model. |
| 4 | How are prompts/models selected? | Worker `direct` executor configured to a local Ollama endpoint (acceptance: `qwen2.5.2-coder`); research chat discovers loopback models; briefing AI needs explicit config + consent. No prompt-optimization loop. |
| 5 | Do previous outcomes influence subsequent decisions? | **Only via humans reading evidence.** Observations, timelines, review queues, and decisions inform the next human/template choice. No automatic policy update, weight change, or retrieval-into-prompt based on past outcomes exists in this repo. |
| 6 | Are skills/successful policies retained? | Templates are versioned code; decisions/observations are retained. But **no skill-abstraction or success-policy induction** (no ECK skill compiler, no lesson object) was found. |
| 7 | Are traces persisted? | Yes — executions, workflow events, language observations, decisions, activity, receipts. Durable and queryable. |
| 8 | Does capability discovery lead to executable actions? | Discovery → candidate (advisory) → explicit registration → registered ActionSpec → confirmed execution. Discovery never auto-enables. |
| 9 | Do verification/evaluation influence future behaviour? | Deterministic tests + CoCoder review gate the **current** workflow's acceptance (with human override + reason). They do not retrain or reweight future workflows. |
| 10 | Closed learning/improvement loop demonstrated? | **No.** The loop present is *governed execution with human learning*, not *machine learning from execution*. No controlled harness-vs-baseline comparison exists. |

### ECK specifically

A repo-wide search for `ECK|CognitiveKernel|executive|harness` (outside browser-harness/DOM and test-harness mentions) finds **no ECK module, no kernel service, no executive API**. "Praxis" in this repo is the *external proposer* of advisories (imported under MC-PRAXIS-07), not an in-repo cognitive kernel. "Harness" mentions refer to browser/DOM inspection, Playwright absence, or fake-Pi test fixtures — not an adaptive execution harness. **Do not treat MC10/MC11 workflows + Praxis import as an ECK.** They are valuable governance machinery, but the kernel hypothesis (if it lives elsewhere — e.g., Praxis/ECK repos) has no implementation here to evaluate.

### Reported experiments and negatives

- MC10 TraceLite: 21→3 events (85.7%), tests pass, review gate passed, human decision recorded — demonstrates a *workflow can complete safely*, not that the harness improves models.
- MC11 brightness: synthetic fixture, expected/observed means `[0,128,255]` — structural coverage, not capability proof.
- PRAXIS-15: 1,245 technical claims all fail freshness; 0 live executions — reported, not hidden.
- MC-LIVING-BOOK-02D pilot: Phase B outcome `inconclusive` (Arm B no proposal); documented as research pilot, not learning claim.
- Environment-dependent failures disclosed in README (5 + 1 outside Living Book path) and flaky-frontend note in QUALITY-01-P2 (worker-load flakiness, 102/102 on final run).

---

## 6. External application relationships

| App | Mission owns | App owns | Contract / interface | Data exchanged | Actions | Evidence returned | Identity / provenance | Failure / permission boundary |
|-----|--------------|----------|----------------------|----------------|---------|-------------------|------------------------|-------------------------------|
| Next | Read model, decisions (`local_only`), project links, export package, chat snapshot | Candidates, runs, gaps, scores, research store | Read-only PG (`NEXT_DSN`, `read_only=on`) or SQLite `mode=ro`; v1 JSON export | Opportunities/runs/gaps (bounded) | None (discovery launch blocked) | Source id, timestamps, staleness, diagnostics | `external_id` + `source_version/timestamp` + `observed_at`; never rewritten | Adapter fails → unavailable, dashboard survives |
| Work | Same read-model pattern | Opportunities, qualifications | `work opportunities --json` (native exe, allowlisted env, UTF-8 forced) | 130 live opps in acceptance | None (`decide` never invoked) | Typed payload + evidence | Same envelope | Malformed → unavailable, not fabricated |
| CoCoder | Redirected engine dir, review artifacts, dispositions, execution history | Assessments, findings, review logic | JSON artifacts + `cocoder review` CLI with `--config` redirect | Findings/severity/paths | One bounded `run_review` (confirmed, repo-allowlisted, ref-validated) | `review-*.json` + sidecar (repo/base/head/intent) | Source identity preserved; ack ≠ verification | Invalid repo/ref → 422 pre-queue; single-flight |
| Worker | Proposal, approval hash, sandbox, measurement, review request, decision | Health, `direct` local execution | `GET /health`; `POST /v1/work` (local Ollama) | Objective/scope/prompt → code patch | Via workflow only, exact approved path | Patch + tests + measurement + CoCoder review | Tags (`mc10-baseline`), digests, correlation | Stale/dirty/scope-violation → reject + restore; Docker missing → block, no host fallback |
| Writer | Queue, dispositions, audit launch, presentation | Editing intelligence, reports, audit logic | `editing summary/audit/reports/show/status/compare --json`; `writer-editing-report-v1` | Reports, six subdimensions, findings, locators, fingerprints | `audit_registered_books` + `writer.audit_registered_book` (confirmed, bounded) | Report IDs, paths, partial/stale/error preserved | `project_root` authoritative; `book_id` format + version checks | Unknown/stale/malformed → typed rejection; writes only Writer-owned artifacts |
| ALIVE | Project/book mapping, connection UI, quality-context assembly, image serving, presentation | Source custody, chapter reads, reading state, notes, sessions, receipts | Mission `/api/living-book/*` → ALIVE `/api/v1/living-books/*` (loopback only) | Chapters, state, notes, conversations, `book-quality-context.v1` | Ask/note/refresh/revoke via gateway | Citations, receipts, usage, coverage/freshness/limits | Manuscript root inside source root; 30-day approval; chapter hash verified, 409 on change | ALIVE down → `unavailable` (project evidence intact); model down → companion reports, rest works |
| BookBuilder/Hugo | Paths, quality maps, readiness display | Builds, manuscripts | Filesystem observation | Status claims, chapter files | None | File reads | User-maintained until verified integration | No launch until verified |
| Proof/research | Evidence timeline entries | Proofs, research outputs | Filesystem/versioned exports | Reports, observations | None autonomous | Artifacts + provenance | Source attribution | Read-only |
| Git/GitHub | Activity index, daily review | Repos, commits | Read-only Git CLI, timeouts | Commits/authors/dates | None (no fetch) | Commit evidence + backfill badges | `repo_uid`/path identity | Inaccessible → recorded, not fatal |

**Duplication avoided by design:** no manuscript parsing/scoring (Writer), no research-store logic (Next), no review logic (CoCoder), no manuscript writes (books), no inference (ALIVE/Worker models). **Weaknesses:** compatibility (not stable) Next PG contract; Work CLI surface only; CoCoder config redirect diverges from repo-local config; Writer staleness depends on report freshness; ALIVE base URL is operator-configured loopback (single-backend assumption).

---

## 7. Current ALIVE integration (MC-LIVING-BOOK-01 + 02A–02D)

- **Discovery:** Mission previews eligible source roots (manuscript always; whole repo iff capped scan under preview limits). Distillation whole-repo recommended for `planning/editorial/research/experiments` evidence (MC-LIVING-BOOK-01:102-108).
- **Approval:** UI checkbox + `approve:true`; Mission calls ALIVE preview → register folder → owner read-only `live` approval (30 days) → register book. No manuscript bytes copied to Mission; revocable in ALIVE (89-100).
- **Session:** Bounded revocable session per ask/note; usage shown; `POST …/sessions/{consent}/revoke` supported. Model calls only on ask/note — never on page open.
- **Endpoints used:** `GET /projects/{id}` (truthful state), `/candidates`, `POST …/connect/preview|connect`, `GET …/book`, `GET …/chapters/{id}`, `PUT …/reading`, `GET/POST/DELETE …/annotations`, `GET/POST …/notes/{chapter}`, `POST …/ask` (+`quality_context`), `GET …/conversations/{id}`, `GET …/quality`, `POST …/refresh`, `POST …/sessions/{ref}/revoke`, `GET …/assets` (Mission-contained image serving).
- **Exposed in UI:** chapter index + word counts + changed state; rendered chapter (front-matter stripped, tables/code/images/`bookfig`/KaTeX/Mermaid); companion (chapter/book scope, citations, receipts, revocation); notes tab (living note + annotations + selection actions); quality tab (coverage, prose dimensions, weakest chapters, limitations, "Ask ALIVE about quality"); continue-state across restart (110-122).
- **Not exposed:** ALIVE's Ask/research loops, chapter-improvement/doc/code workflows, Bespoke, runbooks, history/episodes/experience, tour/help, model gateway config — none surfaced in the reading room. **The room is a deliberately narrow slice** (engine + ask + notes over one approved source).
- **State reuse:** reading position, annotations, notes (bound to chapter SHA), conversations persist in ALIVE ledger; reopening resumes. Changed files → 409, no stale bytes.
- **Revocation/access:** 30-day live approval; explicit refresh; session revoke; `unavailable/not_connected/needs_source/model_unavailable` states with actions (135-144).
- **Interpretation of evidence:** Mission assembles `book-quality-context.v1` (prose evals, Writer readability, technical claims, publication readiness, Artifact Load) with CURRENT/STALE/NOT_RUN/PARTIAL/ERROR + coverage/limits; ALIVE treats it as untrusted owner context, quote-verified (`owner-context:quality|reader`); **no composite score, no averaging, no verdict-from-score** (35-61). Quality panel is deterministic Mission data; ALIVE only explains on request.
- **Live proof (2026-11-19 acceptance):** Distillation 42/42 current (ch14 "Synthetic Data Generation", 4,067 words, SVG 200 3,940B via contained route); Language 39/39 current (ch01 two `bookfig`, served); prose means (clarity 3.74 … economy 2.90 …); ch14 context (overall 3.0, limits: single-run judgment, repeatability unestablished); real-model companion via Pi/`muse-spark-1.3-contributor`; 7 ALIVE + 6 Mission backend + 83 frontend tests pass; full backend 499+1 skip with 5 env-dependent + 1 Pi-critique failures disclosed (README:572).
- **02-series (research pilots, not product):** 02A/02B/02C (semantic mediation obligations), 02D evaluated-experience/transfer pilot — Phase A read-only chapter-evaluation route in ALIVE now exists; Phase B freeze rev3; pilot `inconclusive` (Arm B no proposal); Phase D comparison view. Documented as pilot, not learning.

---

## 8. Operational evidence and experimental results

| Milestone | Demonstrated live | Fixture / offline | Result | Limits / negatives |
|-----------|-------------------|-------------------|--------|--------------------|
| MC01 core | Real process launch/stop/reattach + restart; real editor launch; discovery exclusions; migrations; checkpoints; adapter isolation | Vitest component suites | Working control centre on real data | Port-ownership refusal; wrapper-grandchild `lost`; no auto-fixes |
| MC09 engines | Live Next PG/SQLite, Work CLI (130 opps), CoCoder artifacts + review action; decisions/search/inbox on real data | Bounded adapter timeouts; unavailable-as-unavailable | Unified surface without absorbing engines | Next = compatibility; Work writes blocked; CoCoder redirect divergence |
| MC10 TraceLite | Worker `direct` + Ollama `qwen2.5.2-coder`, deterministic tests, CoCoder review of result commit, human decision; replay idempotency | — | 21→3 events (85.7%); complete safe loop | Single template; lower-parity executor labelled; no harness-learning claim |
| MC11 hardening | Docker sandbox isolation, cancellation, dup-guards, 2 templates, timeline | Brightness fixture (synthetic `[0,128,255]`) | Truthful lifecycle + read-only observations | Observations never control execution by design |
| MC-WRITER-01/02 | Real Chrome acceptance; Writer CLI reads; scoped audit execution; queue + deep links | Mocked-runner parsing tests | Read-only evidence done right | Metadata/MRI/Strengthen `NOT_TRACKED`; staleness depends on Writer |
| MC-LIVING-BOOK-01 | Distillation + Language live room, real-model Q&A, receipts, images, quality discipline (2026-11-19) | 83 frontend + 13 backend tests | Reading room works end-to-end | Model on ask/note only; changed-chapter 409; no ALIVE workflows exposed |
| MC-NEXT-CHAT-01 | Local chat vs loopback models; snapshot + freshness notice | Export package tests | Grounded discussion without Next writes | Remote refused; no Next mutation path |
| PRAXIS-07/09/11 | Validation/preflight/approval/digest tests (30 passed); pilot import `awaiting_approval` | Scoped-audit mocked runs | Governance machinery works | **No approval simulated, no Work executed** (pilot inert by design) |
| PRAXIS-15 | 7 + 7 tests (51-suite green) | Engineering fixtures | Bounded verifier correct | 0 live executions; 1,245 claims stale |
| QUALITY-01-P2 | Real-data cutover 39 created, 40 workspaces, browser zero-errors | 8 + 5 new tests; 667+1 backend; 102/102 frontend final | Scale + honesty (Writer `stale:true` shown) | Scoring deferred; frontend flake under worker load |

**Outcome-improvement status:** No milestone demonstrates that Mission Control's coordination/harness improves model or engine outcomes versus the engines/models alone. MC10/MC11 measure *their own* executions (event reduction, expected/observed match) with deterministic tests as gates — the correct integrity claim, not a learning claim. The question in §5.10 remains open by design.

---

## 9. Limitations and unresolved questions

1. **No demonstrated harness lift.** Machinery ≠ improvement. Controlled harness-vs-baseline evidence does not exist here.
2. **No ECK in repo.** If an Executive/Executable Cognitive Kernel exists, it is external (Praxis/ECK systems). This repo has proposal import + workflow execution, not a kernel. Do not conflate.
3. **Narrow write surface by design.** Only CoCoder review, Writer audits, technical verify, and workflow-scoped Worker patches. Everything else (Next/Work decisions, publishing, spending, cross-repo edits) is absent — a safety feature, but also the ceiling on "coordination."
4. **Compatibility integrations.** Next PG is explicitly compatibility; Work is CLI-scraping; CoCoder redirect diverges; Writer freshness is external. Each is honest but brittle.
5. **Single-operator local trust.** Loopback + origin header; no multi-user principals; PID/time ownership; secrets by env name. Correct for local use, untested beyond it.
6. **Staleness everywhere.** Observation/cached/source timestamps distinguished — good — but every surface can be stale (30s adapter timeout, explicit refresh, backfill badges). No background truth daemon.
7. **Quality without scoring — yet.** Prose/technical/readiness/artifact evidence assembled with discipline, but no scoring milestone (QUALITY-02), 0 live technical verifications, and Writer gaps (`NOT_TRACKED`) limit publication claims.
8. **Living Book is a slice.** 02-series pilots (esp. 02D `inconclusive`) show transfer/evaluation research is nascent. The room exposes nothing of ALIVE's workflows/memory/learning — correct per boundary, but integrators must not mistake the room for ALIVE.
9. **Scale honesty.** 40 software workspaces + 110 repos + 12k commits indexed; per-source caps, pagination, and worker-load frontend flake show the practical limits.
10. **Provenance vs truth.** Every surface preserves source identity, quotes, receipts, digests, and limits — but none verifies semantic truth. A cited quote is not a correct claim (same rule as ALIVE's citation checks).

**For RESEARCH-03 (no design here):** the write-path split (Mission governs, engines/ALIVE execute), the observation-vs-control boundary (`language.observation.v1` read-only), the proposal-digest pattern (Praxis-07) vs session-consent pattern, and the missing harness-lift evidence are the load-bearing comparison points.

---

## 10. Full evidence references

| Claim | Path |
|-------|------|
| Purpose, implemented list, modes, safety, tests, security, repo policy | `README.md` (esp. §3-27, §54-63, §104-176, §178-237, §515-629, §632-662) |
| Position, stack, flow, persistence, status computation, processes, discovery, adapters, briefing, frontend, omissions | `docs/MC01-ARCHITECTURE.md` |
| Unified interface, adapter protocol, methods, persistence, guards, API, inbox/search, freshness | `docs/MC09-ARCHITECTURE.md`; `docs/MC09-INTEGRATION-AUDIT.md`; `docs/acceptance/MC09-REPORT.md`; `docs/acceptance/mc09/README.md` |
| Workflow contract, reality audit, acceptance | `docs/MC10-WORKFLOW-CONTRACT.md`; `docs/MC10-REALITY-AUDIT.md`; `docs/acceptance/MC10-REPORT.md`; `docs/acceptance/mc10/README.md` |
| Templates, Docker, lifecycle, cancellation, Language, timeline | `docs/MC11-TEMPLATES-AND-LANGUAGE.md`; `docs/MC11-EXECUTION-INTEGRITY-AUDIT.md`; `docs/acceptance/MC11-REPORT.md`; `docs/acceptance/mc11/README.md` |
| Living Book gateway, quality, routes, states | `docs/MC-LIVING-BOOK-01.md`; `docs/acceptance/mc-living-book-01/README.md`; `docs/MC-LIVING-BOOK-02A.md`; `docs/MC-LIVING-BOOK-02B.md`; `docs/MC-LIVING-BOOK-02B-R1.md`; `docs/MC-LIVING-BOOK-02C-DESIGN.md`; `docs/MC-LIVING-BOOK-02D.md`; `docs/MC-LIVING-BOOK-02D-R1.md` |
| Praxis proposals, preflight, scoped audit, verification | `docs/MC-PRAXIS-07.md`; `docs/MC-PRAXIS-09.md`; `docs/MC-PRAXIS-10.md`; `docs/MC-PRAXIS-11.md`; `docs/MC-PRAXIS-15.md`; `backend/mission_control/praxis_proposals/`; `backend/tests/test_praxis_proposals.py`; `test_writer_scoped_audit.py`; `test_technical_verification.py`; `test_arithmetic_verifier.py` |
| Writer integration + queue | `docs/MC-WRITER-01-WRITER-INTEGRATION.md`; `docs/acceptance/MC-WRITER-01-REPORT.md`; `docs/acceptance/mc-writer-01/README.md`; `backend/mission_control/writer/`; `backend/mission_control/adapters/writer.py` |
| Quality/publication/technical/cultivation | `docs/MC-PROJECTS-QUALITY-01-PHASE-01-REPORT.md`; `docs/MC-PROJECTS-QUALITY-01-PHASE-02-REPORT.md`; `docs/MC-PUBLISH-02-ARCHITECTURE.md`; `docs/MC-CULTIVATION-*.md`; `backend/mission_control/{quality,publication,technical,cultivation,websites}/`; `backend/tests/test_quality*.py test_publication.py test_technical*.py test_cultivation*.py` |
| Next chat/research | `docs/MC-NEXT-CHAT-01.md`; `backend/mission_control/research/`; `backend/tests/test_research_chat.py` |
| Security, activity, cultivation | `docs/SECURITY.md`; `docs/MC-ACTIVITY-01.md`; `docs/MC-ACTIVITY-02.md`; `backend/tests/test_security.py test_activity* test_git_*.py` |
| Modules, routes, persistence | `backend/mission_control/{api,adapters,projects,registry,processes,discovery,briefing,workflows,living_book,writer,quality,publication,technical,research,persistence}/`; `backend/mission_control/models.py schemas.py config.py main.py`; `backend/tests/test_*.py` (70+ files); `frontend/src/**/*.{ts,tsx}`; `config/defaults/` |
| History | `git log --oneline -20` (run in repo; recent: quality-identity cutover, praxis pilots, living-book 02-series, writer scopes) |

*Acceptance check:* a reader unfamiliar with Mission Control can now state why it exists (§2), how it coordinates without absorbing engines (§3–4, §6), what is operational vs partial/designed (§4), why its execution machinery is not a demonstrated learning loop (§5), how the ALIVE room is bounded (§7), and what evidence is missing (§8–9) — all grounded above.
