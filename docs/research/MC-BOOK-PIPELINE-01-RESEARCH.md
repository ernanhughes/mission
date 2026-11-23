# MC-BOOK-PIPELINE-01 — Research Report: Book Production & Quality Pipeline

**Status:** Research only. No implementation, no schema change, no manuscript edit, no commit.
**Date:** 2026-11-22. **Author:** local research (Muse Spark, read-only inspection).
**Repos inspected:** `C:\Projects\mission` @ `ab7dc15`; `C:\Projects\writer` @ `aa5be9841`;
`C:\Projects\workbench` @ `62f75e5` (consumer reference only).
**Live services during research:** Mission Control `http://127.0.0.1:8790` reachable
(`schema_version 38`); Writer web `http://127.0.0.1:8010` **not running**
(connection refused); Workbench not running as HTTP (port 7420 answered 404 to
`/health`, i.e. something listens but the route is absent — not relied upon).
**Method:** read real code (routes → services → domains → tests), real artifact
files under `C:\books\memory\.writer\`, real CLI JSON output
(`writer editing summary --json`), real Mission SQLite rows (read-only queries).
Nothing below is inferred from a Workbench tab label or from documentation alone.
Where something was not read, it says **unknown**.

Related prior work: `docs/MC-WRITER-01-WRITER-INTEGRATION.md`,
`docs/MC-PUBLISH-02-ARCHITECTURE.md`, `docs/LIVING-WORK-BOOKS-01-W2-REPORT.md`,
Writer `docs/workbench-capability-inventory.md` (W0, Oct 2026 — still accurate on
the points re-verified here; two of its gaps have since been closed:
`no_write=True` is now passed by the contract route, and
`POST /api/mri/observe` exists).

---

## A. Executive assessment — what can be implemented now

**The smallest reliable enhancement** (answers the mission's final question):

1. **A versioned stage registry + a read-only chapter×stage matrix** computed
   from artifacts Writer already writes, with digests recomputed against the live
   manuscript. No execution, no new orchestration. This alone lets an author open
   Mission Control, see which books/chapters need processing, and trust every
   cell because each traces to an artifact path + digest comparison.
2. **One staged, deterministic, cheap action behind the existing durable
   `integration_executions` lifecycle** — pattern observation
   (`POST /api/artifacts/observe`) and deterministic MRI observation
   (`POST /api/mri/observe`) are the candidates: no model, no embedding, no
   cache, no write, proven in code and tests. Wire one of them as a new Writer
   adapter action (`approval_required=true`, duplicate-run guard already exists),
   store per-chapter results as `integration_records`, and the author can launch,
   close the browser, and return to evidence-backed status.

Everything else — strengthening campaigns, editing audits at scale, validation
runs, graphs, before/after approval flows — is real but heavier (model cost,
Worker dependency, human gates, timeout bounds) and belongs to later milestones.

**What is verified as reusable today (established fact):**

- Evidence vocabulary `passed/failed/pending/unavailable/unknown` +
  freshness `current/stale/unknown` (`backend/mission_control/publication/evidence.py:24-30`).
  Use it; invent nothing.
- Canonical identity: Mission `project_id` is canonical; Writer ids validated
  against the live registry; aliases in `settings.book_identity_aliases`
  (`publication/identity.py`, `MC-PUBLISH-02`).
- Fingerprints: `manuscript-v1` (CRLF→LF `file:sha` manifest) and
  `writer_source_digest` (Writer's frontmatter-strip algorithm replicated
  exactly; mismatch ⇒ `unknown`, never stale-by-default)
  (`publication/fingerprint.py:36-151`).
- Stored-output readers with digest comparison already exist for validation runs
  and finalization events (`publication/publishing.py:52-188, 876-949`).
  Same pattern extends to MRI/editing/graph artifacts.
- Durable single-action execution exists: `integration_executions`
  (`queued/running/succeeded/failed`), duplicate-active guard, bounded
  subprocess runner (60–300 s cap), approval gates, post-action refresh, polling
  endpoints (`integrations/service.py:350-526`, `runner.py:89-117`,
  `api/integrations.py:166-179, 47-59`).
- Writer-side durable multi-chapter execution exists **inside Writer**:
  strengthening campaigns (202 + background thread, 409-if-busy,
  `idempotency_key`, pause/resume/cancel, per-chapter dossier, stage reuse by
  prompt hash) and book campaigns (`run` with `--max-wall-seconds`, resume-safe,
  canonical-JSON atomic store). Mission Control already drives book campaigns
  through adapter actions (`adapters/writer.py:159-323, 695-752`).
- Editing before/after comparison exists (`_comparison` in
  `writer/.../routes/editing.py:224-274`): dimension deltas + `changed` flag +
  explicit "does not prove one edit caused the difference" note. Strengthening
  `results-packet` (`?include_diff=`) + Workbench journaled apply/undo (exact
  bytes restore, gate re-check at the transaction boundary) is the
  proposal→applied trace. Both are read-shaped; neither is yet adapted for
  Mission Control.

**What does NOT exist (explicit gaps):**

- No stage registry, no chapter×stage aggregate endpoint, no chapter-level
  publication/build status (publishing evidence is book-level only).
- No Mission-side multi-chapter fan-out, bounded concurrency pool, per-stage
  progress %, or cancellation of a running CLI action.
- No Mission→Writer HTTP client at all (integration is CLI-only today; Writer
  web was down during research, so the HTTP observe routes are code-verified
  but not live-tested from Mission).
- "Technical graph" as a pipeline stage is **not available**: the chapter
  semantic graph builder exists (deterministic, hash-compared, CLI-only) but its
  path resolution and provider wiring are unverified per book; the cognitive
  graph viewer needs a populated graph DB of unknown state. Mark graph
  `unavailable`/planned until a per-book verification passes.
- "Utterance" as a book-production stage **does not exist**: in Writer,
  `utterance` means writethrough voice-session turns and conversation spans,
  not chapter analysis. Do not put it in the pipeline (see B.4).

---

## B. Capability inventory — verified Writer functions and evidence

Conventions: **Entry point** is copied from code. **Safety** classes:
`R` read-only · `W` writes Writer-owned generated artifacts only ·
`P` produces reviewable proposals/candidates, never manuscript ·
`M` modifies manuscript (must never be called by the pipeline without explicit
author approval). **Cost** is labelled measured vs estimated. Anything not read
is marked unknown rather than guessed.

### B.1 Metadata (implemented; the pipeline's root input)

| Field | Verified fact |
|---|---|
| Stage ID | `metadata` |
| Capability | Chapter metadata contract (beats, constraints, entities, warnings) + generation/repair of `metadata/*.yaml` declarations |
| Owning engine | Writer (`writer_runtime/domains/metadata`, `metadata_generation`) |
| Entry points (HTTP) | `GET /api/metadata/contract?project_id&chapter` (`routes/metadata.py:447`) — now passes `no_write=True` (`:484-490`); `GET /api/metadata/check?project_id&chapter&include_skipped` (`:551`); `GET /api/metadata/identity?project_id&chapter` — file + text hash, "read-only and light" (`:516-548`); `POST /api/metadata/preview` — staged candidate + `candidate_sha256` + `can_apply` + `total_estimated_cost_usd`, writes no metadata (`:257-367`); `POST /api/metadata/apply` — promotes a previewed candidate after hash checks, no model (`:370-399`) |
| Entry points (CLI) | `writer metadata contract|check|check-book|generate|repair|…` (`commands/metadata.py`). `generate`: `--chapter` stem/number/glob, `--replace`, `--no-write`, `--limit`, `--json`; `repair` similar. `check-book` has `--no-write` (`:643`) |
| Scope | Chapter (contract/check/preview/apply/generate per chapter); book (check-book, generation ledger over all chapters) |
| Inputs | Chapter text + project registry entry; generation additionally uses the book-state ledger folded from already-validated earlier chapters (`metadata_generation/state.py`) |
| Outputs | `metadata/*.yaml` declarations in the book repo; generation ledger `<run_id>.json/.md` under `.writer/metadata/generation/`; staging candidates under `.writer/generation/metadata/<run_id>/`; validated in the Sep-2026 memory ledger (`metadata-gen-20260921_134812-9c41a9ee.json`): per-chapter `status generated|skipped_existing`, `valid`, `repairs`, `execution_ids`, `candidate_path`, `source_path`, `written`, plus `deterministic_findings`, `semantic_findings`, `executions[]` with per-call `usage` + `estimated_cost_usd` |
| Prerequisites | Registered project; chapter resolvable inside the project's chapter dir. None on MRI/patterns/graph |
| Cost | **Measured** (memory ledger): 14 generated chapters, `total_estimated_cost_usd 0.141859` (~$0.01/chapter; 10–90k input tokens/chapter, 1–6k output, 10–77 s latency per call through `muse-spark-1.3-contributor` Worker route). Check/contract/identity: zero model, milliseconds. Generation is resumable/incremental (`skipped_existing`, `skipped_already_staged`; commits `3e49a5d69`, `27cac6469`) |
| Idempotency | Safe: existing valid files preserved unless `--replace`; repair backs up + stages + validates before promotion; resume skips completed chapters |
| Freshness | Contract/check recomputed per request (no cache seen); generation ledger rows carry `source_path` + per-run hashes; declaration identity route gives file+hash for exact comparison. Stored-report freshness for *book check* outputs: unknown — needs the same digest-compare treatment as validation runs (M1 work, small) |
| Before/after | Staged candidate vs live file (`candidate_sha256`, `source_sha256`/`target_sha256` triple in preview; `expected_*` hashes enforced in apply) |
| Safety | Contract/check/identity/preview: `R`. Generate/repair/apply: `W` (metadata YAML + `.writer` reports only; manuscript untouched) |
| Availability | Implemented (HTTP + CLI + tests, e.g. `tests/runtime/metadata/`, `tests/web/test_metadata_routes.py`) |
| Evidence | `packages/writer-web/writer_web/routes/metadata.py:236-556`; `packages/writer-runtime/writer_runtime/domains/metadata_generation/engine.py` (run ids, staging, resume); `C:\books\memory\.writer\metadata\generation\*.json`; memory `metadata/*.yaml` (18 files) |

### B.2 MRI (implemented; deterministic path is M1-safe, model path is costly)

| Field | Verified fact |
|---|---|
| Stage ID | `mri` |
| Capability | Chapter observation + technical alignment against the chapter's declaration; book aggregation report |
| Owning engine | Writer (`writer_runtime/domains/mri`, services `book_alignment`, `reports`, `evidence`) |
| Entry points (HTTP) | `POST /api/mri/observe` — **deterministic only** (`mode` anything else ⇒ 422). Guarantees in the module docstring (`services/mri_observe_service.py:1-22`): private engine with no models/embed/cache, chapter read once as bytes, CRLF→LF, verified evidence offsets, `file_sha256` + `text_sha256` + engine `snapshot_hash` all describe the one capture. Response: sections (located true/false), evidence (quote/verified/section/offsets), `stage_status`, observer/prompt versions, engine status, limitations. `POST /api/mri/check-declaration` — deterministic declaration check, needs metadata domain (`routes/mri.py:68-100`) |
| Entry points (CLI) | `writer mri chapter` (observer `AUTO|DETERMINISTIC|PROVIDER`, `--quality-model`, `--semantic-model none|auto`, `--beat-mode`, `--output-dir`); `writer mri project <key> [--chapter] [--limit] [--force] [--observer] [--beat-mode] [--quality-model] [--semantic-model] [--allow-contract-fallback]` (`commands/mri.py:1536-1562`). Project run is content-addressed: `_chapter_outputs_fresh` reuses only when `snapshot_hash` + `metadata_sha256` + `alignment_version` + `observer_prompt_version` + `observer_mode` + `quality_model` + `semantic_model` (+prompt version) + beat-mode all match (`:1111-1157`); legacy outputs without identities are stale (`test_mri_book_cli.py:191`) |
| Scope | Chapter (observe/chapter); book (`project` aggregates `book.mri.json`: `chapters[{chapter_id,status,contract,finding_counts "C:Q:T:R"}]`, `run{generated_at,observer,quality_model,…}`) |
| Inputs | Chapter text (CLI reads the file; HTTP reads it server-side inside the project boundary — caller never supplies text/paths). Optional metadata payload (technical contract). Profile from project declaration |
| Outputs | `.writer/mri/<project>/<stem>.mri.json` (300–800 KB/chapter in memory sample) + `.md`; `book.mri.json/.md`; repair plans under `.writer/mri/<project>/repair/book-repair-*/{manifest,plan,review}.{json,md}` |
| Provenance per report | `observer_mode`, `observer_model`, `embed_runtime_used`, `quality_model`, `snapshot_hash`, `metadata_sha256`, `alignment_version`, `observer_prompt_version`, `section_observer_version`, `section_count`, `stage_status{observer,quality,sections,alignment}`, `embedding_identity{provider hnet, model mxbai-embed-large, dim 1024, fingerprint…}`, warnings. Provenance flags `fallback_used` / `embed_runtime_used` are unreliable when there is no alignment (W0 §3B, still true in code) — display `observer_mode` + `stage_status`, not the flags |
| Prerequisites | Chapter text only for observation-only outcome (`METADATA_UNAVAILABLE` still carries observation + report). Full alignment needs a valid technical contract (fail-closed; `--allow-contract-fallback` only for raw-YAML diagnostic). **Does not require patterns/graph/strengthening** |
| Cost | Deterministic observe: **~zero** (no model/embedding calls; asserted by construction + route tests `tests/web/test_mri_observe_routes.py`). CLI `AUTO`: one model call per section + reducer + quality signal (chapter with 14 sections ≈ 16 calls); fiction deterministic output is generic low-value (W0 §3B). Semantic adjudication adds more. **Recommendation: M1 runs deterministic only; model-assisted MRI stays behind explicit authorization with `--limit` + cost readout from Worker session accounting** |
| Idempotency | Safe: CLI reuses fresh outputs (`Reused fresh MRI outputs`), recomputes stale; HTTP writes nothing |
| Freshness | Strong and mechanical: recompute `snapshot_hash` of chapter text + canonical metadata hash + pinned versions, compare to stored report (`_current_freshness_identities`, `_chapter_outputs_fresh`). Memory sample (2026-09-22 reports vs 2026-11-22 files): all three sampled chapters mismatch ⇒ **stale** — the detector works; the reports are simply old (or the book moved: see §I) |
| Before/after | Per-section finding verdicts (`partial|missing` tallied into `C:Q:T:R` strings by `_chapter_finding_summary`); book report keeps provenance but **no single score** (`test_mri_book_cli.py:253`). No diff view; compare two stored reports field-by-field (M5) |
| Safety | HTTP observe + check-declaration: `R`. CLI chapter/project: `W` (report files + persistent observation cache under `.writer/cache/runtime/mri.observation/` when `project_root` is in context; CLI additionally writes the `.writer/mri` reports a route would not). `mri repair … [--apply]` paths write chapters — **must never be exposed** by the pipeline |
| Availability | Implemented (HTTP deterministic + CLI full + book aggregation + preflight + tests `tests/cli/test_mri_*.py`) |
| Evidence | `routes/mri.py`; `services/mri_observe_service.py:227-411`; `commands/mri.py:1074-1157,1536+`; `C:\books\memory\.writer\mri\memory\*.mri.json + book.mri.json`; `tests/cli/test_mri_book_cli.py` |

### B.3 Patterns / artifact prose patterns (implemented; cheapest stage)

| Field | Verified fact |
|---|---|
| Stage ID | `patterns` |
| Capability | Deterministic prose-pattern detection for one chapter (repeated openers, triplet runs, etc.) — signals for review, explicitly **not verdicts** |
| Owning engine | Writer (`writer_runtime/domains/artifact/artifact_engine`, `ArtifactEngine.analyze`) |
| Entry point (HTTP) | `POST /api/artifacts/observe {project_id, chapter, profile="technical"}` (`routes/artifact_patterns.py:37-55`). Guarantees in `services/artifact_patterns_service.py:1-17`: no model/embedding/cache/write; front matter blanked line-preserving; `text_sha256` of exact analyzed text; occurrences parsed from detector evidence strings `L<line>: <snippet>`; only profile `technical` offered (others ⇒ 422) |
| Entry point (CLI) | `writer artifact …` command group exists (`commands/artifact.py`); book-campaign `intel/*` failure-pattern reports and QC `evaluate-dataset` are adjacent but **not** this stage. (CLI surface for single-chapter patterns not inventoried — HTTP is the verified entry.) |
| Scope | Chapter |
| Inputs | Chapter text only (resolved + captured exactly like MRI: `resolve_chapter`/`capture_source` shared) |
| Outputs | Response object only (no stored file seen): `schema writer.artifact.patterns/1`, `source{file_sha256,text_sha256,…}`, `execution{mode deterministic, model_calls none,…}`, `summary{artifact_score, sentences, issues}`, `issues[{issue_id,type,severity,title,why,start_line,end_line,scope,occurrences[{line,snippet,detail}],recommended_fix,stats}]`, limitations. Persisting responses as `integration_records` is M3 work |
| Prerequisites | None (chapter resolvable). Independent of metadata and MRI |
| Cost | **~zero** (deterministic detectors; `max_examples` raised to 500 per detector for the observe path) |
| Idempotency | Pure function of the captured text; safe to rerun |
| Freshness | `text_sha256` vs current file bytes — exact |
| Before/after | Occurrence lists (line + snippet) are directly comparable across runs; no built-in diff view |
| Safety | `R` |
| Availability | Implemented (route + service + `tests/web/test_artifact_patterns_routes.py`) |
| Evidence | `routes/artifact_patterns.py`; `services/artifact_patterns_service.py:86-158` |

### B.4 Utterance (NOT a pipeline stage — name collision documented here so it stays out)

`grep -ri utterance` over Writer finds **no chapter-analysis capability**:
`POST /api/writethrough/session/{session_id}/utterance` is a voice-session turn
append (`routes/writethrough.py:113-125`, domain `writethrough/engine.py:167+`
with `utterance:stage/diagnose/restore/reject` actions on audio frames);
`hands_free` session/utterance buffering is microphone handling;
`conversation/span_builder.py` "utterances" are dialogue turns. Mission Control
has zero `utterance` references. **Recommendation: drop "Utterance" from the
stage list** (or rename the intended concept — if "utterance-level voice
analysis" was meant, no such book pipeline stage was found).

### B.5 Compiler (implemented; fragile path config — M6, not M1)

- Routes: `GET /compiler/api/compile?project_root&chapters_dir&chapter_path&book_id…&observer=auto&through=COMPRESSION` — explicit compile to a viewer model (`routes/compiler.py:55-80`); review-queue APIs (`/api/review-queue`, `/context`, `/adjudicate`, `:271-438`); page shells only otherwise. Docstring: "no mutations, no analysis: the page shell and one explicit compile call".
- CLI: `writer compiler compile|targets|sentence|packet|graph|report|compile-artifacts [--no-write]|diagnostics` (`commands/compiler.py`).
- Engine: `compile_manuscript_chapter(…, observer="auto", …)` (`domains/compiler/engine.py:331`) — observer param means model involvement is possible; not audited for cost.
- Real artifact (memory): `.writer/book/compile/book_compile.json` — `compile_status "diagnostic"`: validation phase passed 18/18 documents, but `metadata compile` + `check-book` phases errored on paths from a **stale世代**: `C:\Projects\memory\memory.md` (missing) and `C:\Projects\memory\chapters` (missing). Proves the compiler reads configured paths and breaks on registry drift — a freshness/availability check must precede any pipeline use.
- Outputs: `book_compile.json/.md`, `sentence_lens_index.json` (memory's is 2 bytes — empty), review-queue DB rows.
- Freshness: unknown (no digest-compare found in the read portions). Availability: **partial** — implemented but path-sensitive; keep out of M1–M3.

### B.6 Knowledge state (CLI-only aggregator — M6)

- CLI: `writer knowledge_state plan|ingest|review|decide|report` (`commands/knowledge_state.py:38-166`).
- Domain producers (`knowledge_state/producers/`): `argument, evidence, legacy_regex, mri, review, strengthening` — i.e. knowledge-state **ingests MRI + strengthening outputs** (dependency edge for §C).
- No web route (absent from `main.py` router list). Store/ORM exist (`orm.py`, `store.py`, `snapshots.py`). Availability: **partial**; no MC entry point today.

### B.7 Strengthening (implemented; the durable-execution reference design — M5)

- HTTP (project-scoped, chapter-resolved server-side; module guarantees in
  `routes/strengthening_campaigns.py:1-15`): `POST /api/improvement/strengthening/campaigns` (plan),
  `GET /…` (list), `GET /{id}` (snapshot + `server.worker_running/last_error`),
  `GET /{id}/chapters/{ch}/stage-plan` (what a run would reuse/send — pure read),
  `GET /{id}/chapters/{ch}` (dossier), `GET …/apply-dossier` (read),
  `POST /{id}/run {mode next|selected|resume, chapters?, idempotency_key?, fresh?}` →
  **202 + background thread**, 409 `CAMPAIGN_BUSY` if running, preflight refuses
  unknown/finished chapters before any thread starts (`:387-435`);
  `POST …/pause`, `…/chapters/{ch}/review` (retry `review_failed` only),
  `…/new-attempt`, `POST …/apply-check` ("may write validation evidence; never
  a chapter, never a model call"), `POST …/author-approval` (+ `/revoke`) —
  typed, identity-bound, records only; `GET …/results-packet?include_diff=`;
  `POST …/recheck-blocked`, `…/extend-budget`, `…/roles`,
  `POST …/review-candidate`, `POST …/author-decision`;
  readiness: `GET /api/improvement/strengthening/readiness?project_id&chapter`
  + `/readiness/book`, `GET /model-roles`, `POST /model-roles/verify` (one
  bounded access check — a real small model call), `GET /model-calls`
  (durable call-log cursor).
- Readiness semantics (`services/strengthening_readiness.py:52-167`):
  `contract{valid|missing|invalid}` (needs a `strengthening:` section in the
  metadata declaration — most chapters likely lack it ⇒ not runnable, honestly
  reported), `publication_readiness{checked_at_run}` (live validation at
  experiment creation, can write evidence — never pre-run for the view),
  `execution{available|unavailable}` (Worker health only; Workbench chat says
  nothing), `independence` (different-family reviewer available vs proven),
  `runnable = contract valid && execution available`.
- Stage reuse (`services/strengthening_stage_reuse.py`): a stage's identity is
  a SHA-256 over the **rendered prompt** (source/candidate text, contract,
  transfer scenario, upstream answers) + route/policy/model; unchanged prompt ⇒
  verified earlier answer returned, downstream follows via prompt contents;
  per-stage locks (second caller waits, then reuses); records in
  `<experiment>/stages/`; only *accepted* replies reusable; failures/cutoffs
  never reused.
- Context actually consumed (`services/improvement_context_service.py:57-178`):
  `runtime.metadata.contract/check/compile_pack`, `runtime.lexicon.snapshot`,
  voice corpus profile — so **metadata + lexicon are the verified inputs**;
  MRI/patterns are *not* listed as inputs (informative, not prerequisites).
- CLI + stores: `book-campaign create|discover|manifest|plan|run|start|status|
  pause|cancel|resume|decide + intel/*` with last-line JSON envelope
  (`commands/book_campaign.py`); `chapter-improvement snapshots|opportunities|
  plans|runs|decision` (runs via bus 202 or `?sync=true` debug);
  `strategy-evolution run-experiment {baseline|candidate}`; stores
  `.writer/book-campaigns/{campaigns,manifests,plans,runs,reports}/*.json`
  (canonical JSON, atomic write, append-only history) and
  `.writer/improvement/runs/<run_id>/card_*.json`.
- Mission coverage: adapter actions `book_campaign_*` + `book_strategy_experiment_run`
  already drive create/manifest/plan/run-chunk/pause/resume/cancel/status
  (`adapters/writer.py:159-323, 455-503, 695-752`) — the pattern for adding
  stage actions.
- Cost: bounded by `max_model_calls`/budgets; every call logged; independent-review
  family enforced. Real model spend — always behind approval + budgets.
- Safety: everything except Workbench's journaled whole-chapter apply is `R/W/P`;
  **no route here writes a chapter**; applying is Workbench's transaction
  (`workbench/chapter_apply.py`: gate re-check inside the chapter lock
  immediately before write, exact-bytes undo, duplicate answered from journal).
- Availability: implemented + tested; the most durable execution in the
  ecosystem. Gated for M5 by cost + contract coverage, not by readiness of the
  machinery.

### B.8 Editing / readability audit (implemented; read-only audit is M3-safe)

- HTTP: `GET /api/editing/chapter?project_id&chapter` (latest stored report +
  `stale/stale_reason` via source-fingerprint compare + `previous_report` +
  `comparison`); `POST /api/editing/audit {project_id, chapter, whole_book}`
  — whole-book audit recommended (chapter-only would misrepresent the book);
  writes a Writer-owned report artifact, never a manuscript
  (`routes/editing.py:358-419`).
- Engine (`domains/editing/engine.py`): `audit_book` over chapter files;
  `source_files[{path, sha256}]`; report `writer-editing-report-v1` (1.0.0);
  independent subdimensions (paragraph/sentence load, fragmentation, rhythm,
  lexical accessibility, section structure); findings with stable
  `finding_id`, `locator{line_start/end, paragraph_index, excerpt}`, `measured`,
  limitations; `_chapter_source_staleness` (bytes compare);
  **`_pipeline_status`: metadata/mri/strengthen are `NOT_TRACKED` with the
  rule "metadata → MRI → strengthen → editing describes the wider Writer
  pipeline, not a hard prerequisite for a read-only editing audit"**
  (`:817-842`) — the dependency model in code, confirming §C.
- CLI: `writer editing summary|audit|reports|show|status|compare` (`commands/editing.py`);
  `summary --json` verified live 2026-11-22 (all books `NOT_RUN` from the
  `C:\Projects\writer` cwd — store resolution is **cwd-sensitive**, see §I.7).
  Store observed: `C:\Projects\writer\.writer\editing\{index.json (3.6 MB),
  summary.json (10.9 MB), reports/edit-*.json}`.
- Cost: deterministic readability metrics (no model call found on this path;
  confirm once more before quoting zero — treat as *inexpensive, presumed
  deterministic* until the engine's `scoring.py` call sites are audited).
- Freshness: exact (per-file sha256 compare on every read).
- Before/after: `_comparison` — per-dimension before/after score+band+codes,
  `changed` bool, honest non-causality note. Backend improvement: currently
  report-level only, not edit-attributed (correct — do not upgrade it into a
  causal claim in M5).
- Safety: `R` (reads) + `W` (audit writes reports only). Availability:
  implemented; Mission already consumes via `WriterAdapter.refresh` + workspace.

### B.9 Validation & finalization (implemented CLI + stored readers — M3/M5)

- CLI: `writer validate [--project] [PATH] [--profile preflight] [--json]
  [--manuscript] [--write-frontmatter] [--report-dir] [--incremental/--base-run/--full]
  [--with-improvement]` (`commands/validate.py:384-471`); project path via the
  `validation:` contract in `projects.yaml` (every book declares
  `manuscript_integrity, qc, readthrough(HUMAN), usage`);
  `writer finalize <chapter> --project --approved-by` (human sign-off on the
  exact validated version; never inferred — `commands/finalize.py:1-7`).
- Stores: `<repo>/.writer/validation/{chapters/*.json (ChapterValidationStateDTO:
  `machine_status`, `source_digest`), runs/<run_id>/{summary,manifest,snapshot,
  observations/findings/clusters/interventions.jsonl, per-chapter, views/},
  finalization/*.json}` (`project_validation/store.py`).
- Mission readers already digest-compare these (`publishing.py:52-188,
  876-949`): `writer_validation_run` (states tally + current/stale counts),
  `writer_finalization` (digest-bound approvals only; stale/unknown honesty).
  Freshness vocabulary for stored runs is therefore **already solved** — extend
  the same helper shape to MRI/editing/graph in M1.
- Adapters: `validation_profile`, `qc_runtime` (needs compiled sentences),
  `readthrough_human` (needs a person), `usage_runtime`. QC/readthrough
  blocking semantics come from the registry, not from Mission.
- Web: `POST /desk/validation/run` (bus-backed async), process validation
  compare/summary/report routes. No simple single-chapter GET for MC use.
- Safety: validate without `--write-frontmatter` is `R` (+ optional
  `--report-dir` sidecars = `W`); finalize writes events only (`W`).
  Availability: implemented.

### B.10 Graphs (partial / unavailable — excluded from M1–M3)

- **Chapter semantic graph** (`graph` domain): `writer graph chapter-semantic
  --project-id --project-root (--chapter|--chapter-id) [--force] [--max-nodes]
  [--narrative-mode regex|auto|off] …` (`commands/graph.py:671-756`).
  Deterministic extractors (terms, entities, metadata, story-state, sentence
  lens; `narrative-mode regex` default); no model call on the build path read
  (a `model_port` exists for nightly agents, not chapter builds).
  Artifacts `.writer/graph/chapter_semantic/<chapter>.graph.json/.md` with
  `source_status.artifact_hashes{chapter_file_hash, sentence_lens_index_hash,
  metadata_contract_hash}` and `status available|stale` + staleness warnings
  (`chapter_semantic_graph_service.py:640-698, 2259-2270, 2406-2445`) — a good
  freshness design to copy. **Caveats:** resolver defaults to
  `<root>/chapters/` (wrong for `content/books/<book>/` layout — unverified);
  sentence-lens index may be empty (memory's is); no web route; needs per-book
  verification ⇒ **partial, M6**.
- **Cognitive graph** (viewer routes `GET /cognitive-graph/api/graphs|graph|
  nodes|edges|branches|artifacts|snapshots|review-sessions|decisions|
  comparisons|reasonings|events|snapshot verify`, CLI `cognitive_graph
  create|from-intent|validate|…|capture-writing|…`): requires populated graph
  DB + `runtime.graph`; state for books unknown ⇒ **unavailable until verified**.
- `program_graph`, `work_graph`, `workflow_graph`, `scene_graph`, `trace_graph`
  CLIs exist but were not inventoried — out of scope for a book pipeline.

### B.11 Readthrough / reader (human gate — not an auto stage)

- Routes: book-map, section, assessment, chapter-acceptance, annotation,
  passage/chapter repair (+apply/undo/verify/finish), session, cadence
  (`routes/readthrough.py:87-730`, ~30 endpoints). Repair **apply** routes
  modify manuscripts — pipeline must never call them implicitly.
- Mission observes acceptances read-only via `MISSION_CONTROL_WRITER_DSN`
  (`_writer_readthrough_evidence`, currently `unknown` — no DSN set).
- Role in pipeline: terminal human approval gate (like finalize), never a
  "refresh analysis" target.

### B.12 Before/after & evolution substrates (implemented pieces, M5 assembly)

- Editing `_comparison` (report-level before/after, §B.8).
- Strengthening `results-packet?include_diff`, `stage-plan`, dossier,
  `apply-dossier/apply-check`, author-approval identities; Workbench
  `chapter_apply.apply_chapter/undo_chapter` (journaled, exact-bytes,
  duplicate-safe, gate re-checked in-lock).
- Sentence evolution (`/sentence-evolution/api/run|events|approve|reject|
  promote-survived|…`) — sentence scope, DB-backed; partial for book use.
- Delta review (`/qc/delta/*`), process validation compare
  (`POST /api/process/validation/compare`), strategy-evolution paired arms.
- `analysis_state` domain: assertion lifecycle
  (`PROPOSED…APPLIED…STALE`), dependencies, `invalidate_for_revision`,
  benchmark + AB comparison DTOs — the revision-loop substrate, no MC adapter.
- Quality domain `check_staleness(stored, current)` + portable-v1 records.

---

## C. Dependency graph — actual prerequisites and parallelizable stages

Established from engine code (not tab order). The editing engine states the
rule explicitly (`editing/engine.py:838-841`); everything else below is
consistent with it.

```
manuscript snapshot (chapter files + metadata/*.yaml)     [root of all freshness]
 ├── metadata contract/check/identity ............ R views (no deps)
 ├── metadata generate/repair .................... W, consumes chapter text (+ earlier validated chapters)
 ├── patterns observe ............................ R, consumes chapter text ONLY        } parallelizable
 ├── mri deterministic observe ................... R, consumes chapter text ONLY        } parallelizable
 ├── mri aligned/project ......................... W, + valid technical contract (fail-closed)
 ├── editing chapter/audit ....................... R/W-reports, consumes chapter text ONLY (NOT_TRACKED others)
 ├── validate chapter/book ....................... R/W-reports, + validation contract (qc needs sentences, readthrough needs human)
 ├── chapter-semantic graph ...................... W, + sentence lens + metadata contract hashes
 ├── knowledge-state ingest ...................... consumes mri + strengthening outputs (aggregator)
 ├── strengthening campaign ...................... P, + strengthening: declaration + lexicon (+ validation at creation)
 ├── finalize / readthrough acceptance ........... human gates on validated exact versions
 └── comparison / packets / evolution ............ views over stored runs (no new deps)
```

Answers to the mission's questions:

- **Does MRI require Metadata?** Observation: no (returns `METADATA_UNAVAILABLE`
  + observation as a normal outcome). Alignment/book semantics: yes, and it
  fails closed on invalid contracts.
- **Does Patterns require MRI?** No. Shares only the chapter-capture helper.
- **Independently runnable:** metadata views, patterns, deterministic MRI,
  editing audit, stored-run readers. All are chapter-parallel.
- **Concurrent chapters:** yes for all `R` stages (per-file, no shared locks;
  Writer's own campaign runner is sequential-with-resume, so Mission fan-out
  should stay sequential-per-book in M4 or delegate chunking to Writer).
- **Strengthening inputs:** metadata declaration + `strengthening:` spec +
  lexicon (+ validation evidence at experiment creation). MRI/patterns are
  informative context, not hard prerequisites.
- **Editing:** operates on stored reports + proposals; the only manuscript
  writer is Workbench's journaled apply, never Writer.
- **Regenerate after text change:** MRI reports (snapshot mismatch), patterns
  (text hash), editing (source fingerprint), validation runs (source_digest),
  graph artifacts (triple-hash) — all mechanical. Metadata declarations are
  author-owned YAML: a manuscript edit does *not* auto-invalidate them, but
  alignment may then fail-closed (honest, not stale-by-default).
- **Graph feeding upstream:** no automatic feedback exists. Any iteration is an
  explicit versioned re-run (new run/report id, history preserved) — never an
  execution cycle.
- **Book-wide aggregation:** MRI `book.mri.json`, metadata generation ledger,
  validation book runs, editing summary, campaign plans. All exist as files;
  Mission must read + digest-compare, not trust.

**Minimum safe pipeline runnable today** (all verified, no new invention):
`manuscript_discovery → {metadata views, patterns, deterministic MRI, editing
read} → {stored validation/finalization readers}`. Model-backed generation,
aligned MRI, strengthening, and graph join only with explicit authorization,
budgets, and Worker health.

---

## D. Mission Control reuse map — UI, APIs, adapters, persistence

### D.1 Evidence / identity / fingerprint (reuse verbatim)

- `publication/evidence.py`: `EvidenceItem{book_id, evidence_type,
  source_system, source_reference, source_revision, observed_at, executed_at,
  result, freshness, diagnostics, available_actions[], detail{}}`;
  `unknown_evidence()` constructor. Result/freshness vocabularies validated in
  `__post_init__`.
- `publication/identity.py`: canonical `project_id`; alias save/resolve/delete
  with fail-closed conflicts; Writer ids validated against the live registry.
- `publication/fingerprint.py`: `fingerprint_manuscript` (manuscript-v1),
  `writer_source_digest` (exact Writer algorithm), `git_revision` (HEAD +
  dirtiness recorded separately from content identity).
- `publication/publishing.py:get_publishing_summary` — the per-book evidence
  builder to extend (not duplicate): manuscript_discovery, validation
  requirements, stored validation runs, finalization, readthrough, proof,
  bookbuilder, hugo, ALIVE, mission assessment + human approval. Each item
  already carries `available_actions` — the pipeline's per-cell actions extend
  this pattern.
- `publication/service.py`: assessments (snapshot-bound, append-only),
  `refresh_freshness`, approvals, gate results, issues, follow-ups, calibration.
  Human-owned publishing status lives here — the pipeline must link to it, not
  replace it.

### D.2 Writer integration (the execution carrier to extend)

- `adapters/writer.py` — `WriterAdapter`: `refresh()` parses
  `writer.editing.cli.v1 / writer-editing-summary-v1` envelopes strictly
  (schema ids checked, malformed ⇒ unavailable, nothing invented);
  `actions[]` (11 verified): `audit_registered_books`,
  `audit_registered_book{book_id}`, `book_campaign_{create,manifest,plan,
  run_chunk,pause,resume,cancel,status}`, `book_strategy_experiment_run`.
  `validate_action` + `_campaign_args` build exact CLI argv; results parse the
  last-line `{ok, result}` envelope. **New read-only stage actions
  (patterns/mri-observe/editing-audit-scoped) follow this exact shape.**
- `integrations/runner.py:run_tool` — bounded subprocess (native exe only, no
  shell scripts, env allowlist + `env_names`, timeout clamped 60–300 s,
  secrets redacted). The 300 s ceiling is the key bound for M3 chunking.
- `integrations/service.py:start_action/_run_action` — durable
  `integration_executions` row (`queued→running→succeeded/failed`), **refuses
  a second active run of the same app+action (409-style `Conflict`)**,
  `approval_required` + `confirm`, output/error/result/artifact_ref persisted,
  post-success refresh, shutdown marks orphans failed. Poll via
  `GET /api/integrations/executions[/{id}]` (`api/integrations.py:47-59`).
- `writer/service.py` — read model: workspace totals, review queue, decision
  queue (from Workbench's JSONL, read-only), chapter improvement / campaigns /
  intel / evolution summaries from `settings.book_root`. Note: reads
  `C:\Projects\workbench\.writer\editorial-decisions.jsonl` — the file-based
  read pattern M5 reuses for results-packets.
- `writer/evaluations.py` — W1 envelope ingest (`writer.evaluation-envelope.v1`,
  providers `artifact|qc` only, idempotent replay, supersession preserves
  history) + derived freshness `CURRENT/STALE/NOT_RUN/UNAVAILABLE/UNVERIFIED`
  with server-side chapter-hash resolution. The chapter-freshness read path to
  copy for stage cells.
- `writer_registry/` — registry load (book tag + active), chapter-dir
  precedence (`chapters.path` > `content_dir`), `sync_writer_books`
  (Writer owns locations, Mission owns planning state).
- `living_book/quality.py`, `quality/service.py` — chapter measures with
  coverage/freshness/limitations, never-averaged, `NOT_RUN` ≠ zero; quality
  workspace reports `chapters_current/chapters_total` with the explicit
  coverage sentence to reuse.

### D.3 Job/process/workflow infrastructure (honest assessment)

| Requirement (mission §G) | Verdict |
|---|---|
| Persist run id/scope/inputs/stage states/output refs | **Partial.** `integration_executions` persists action-level rows; Writer-side campaign stores persist per-chapter runs. No Mission-side per-chapter *stage* rows yet (M4). |
| Run only verified capabilities | **Yes** — adapter `validate_action` + strict envelope parsing. |
| Prerequisite checks before dispatch | **Yes (pattern)** — service checks registration/freshness preconditions; Writer readiness endpoints exist per stage. |
| No duplicate concurrent jobs | **Yes (per app+action)** — active-row guard. Per book+chapter+stage needs M4 keys. |
| Bounded concurrency + limits | **Partial** — timeout clamp + campaign wall-clocks + model budgets exist; no Mission-side pool. |
| Failures don't complete dependents | **Yes (pattern)** — failed actions return failed; Writer stages fail closed; no auto-advance exists anywhere (good). |
| Polling, cancellation, retry | **Partial** — polling yes; cancellation exists only for Writer campaigns (pause/cancel actions), **not** for generic integration executions; retry = re-invoke (idempotent where the engine supports it). |
| Survive frontend close/refresh | **Yes** — server-side rows + Writer-side files; Workbench run-store adds lease/heartbeat/interrupt recovery (reference only). |
| Independent chapters proceed on failure | **Not in Mission** — Writer's campaign runner continues past chapter failure (`COMPLETE_WITH_FAILURES`); Mission must adopt the same per-chapter isolation in M4. |
| Provenance per result | **Yes** — executions + artifact refs + Writer provenance blocks; evaluations preserve envelopes whole. |
| Respect approval gates | **Yes** — `approval_required` + finalize/readthrough human gates + publication approvals. |

No new agent framework, ECK, or generic orchestrator is justified: the
composition is *existing durable actions + a small stage-run table + the
Writer-side chunk loop*.

### D.4 Frontend (condensed from the completed UI audit)

- Shell: `BooksPage.tsx:330-481` (`BooksCollectionPage`; selection is local
  state, not URL — deep-linking needs `useSearchParams` as in Scripts/Cultivation).
- Closest matrix templates: `WriterPage.tsx:769-845` (book×fixed-stage table:
  Metadata/MRI/Strengthen/Editing/Readability) and `:913-961` (chapter×dimension
  table); `ProjectPage.tsx:717-779` (`QualityMap` sortable chapter×dimension),
  `:939-1026` (`ArtifactLoadMap`), `:812-916` (`WriterEvaluationsMap`).
  All hand-rolled — no shared matrix component (M2 introduces one).
- Cross-book cards: `PublishingWorkbenchPage.tsx:215-245` (`RowCard` with
  `failed/stale/missing` attention counts); stat strip + identity inbox +
  follow-ups sections are the surrounding patterns.
- Per-book evidence: `BookPublishingPage.tsx:36-68` (`EvidenceCard`),
  `:304-326` (gate cards), `:361-410` (blocker→follow-up). Link, don't duplicate.
- Runs/progress: `ProjectPage.tsx:2631-2654` + `:1229-1267` (campaign cards
  with counts + Stop/Resume), `ImprovementPanel.tsx:97-102, 621-633`
  (2.5 s polling + `<ol class="living-improve-stages">`), `WriterPage.tsx:46-69`
  (manual 1 s execution poll loop). Polling via `useApi(..., {pollMs})`
  (`api/useApi.ts`); no sockets anywhere.
- Kit: `components/ui.tsx` (`PageHeader/Section/Stat/Tag/SimpleStatusBadge/
  ActionButton/DisabledReasons/EmptyState/ErrorState/Modal/Toast`); no drawer
  (use `Modal` or `.resource-detail-panel` layout from
  `IntegrationWorkspacePage.tsx:1379-1446`); `Tag` tones beyond
  `accent/danger` have no CSS; status mappers are per-domain duplicated
  (a shared stage-state normalizer is M2 work).
- Routes/nav: `/books`, `/fiction-books`, `/publishing`,
  `/projects/:id/publishing`, `/projects/:id` (`app/App.tsx`); sidebar
  (`components/Layout.tsx:42-58`); command palette (Books only).
- Data gap for UI: **no chapter×stage endpoint** — M1 adds
  `GET /api/pipeline/books/{project_id}` joining registry chapters +
  stored artifacts + digests; until then any UI is N+1 across six endpoints.

---

## E. State/freshness model — aggregation and invalidation

Reuse `evidence.py` + the evaluations/quality read patterns. Four dimensions,
never compressed:

1. **Production (result):** `passed / failed / pending / unavailable / unknown`
   — did the capability run and what did it conclude. A current MRI with
   findings is `passed` (analysis succeeded) with findings listed in `detail`,
   not a health grade. Writer-native `NOT_RUN/BLOCKED/PARTIAL/ERROR/
   NO_MANUSCRIPT` map at the boundary to `unknown/pending/unavailable` with the
   native string preserved in `diagnostics`.
2. **Freshness:** `current / stale / unknown` — exact digest/version comparison
   only (source bytes, metadata canonical hash, engine/matcher/prompt versions
   where material). Missing comparison inputs ⇒ `unknown`, never assumed.
3. **Execution:** `not_started / queued / running / completed / failed /
   cancelled / blocked` — persisted per run + stage (M4 table or extended
   execution rows). `blocked` = source unavailable / provider unhealthy /
   contract missing (with reason, e.g. readiness payload).
4. **Coverage:** `{applicable, with_evidence, current, attention}` per
   book×stage — rendered as **"19/20 current"**, never a bare tick. Copy the
   quality-workspace sentence pattern: "N of M chapters have a current
   evaluation; coverage is explicit, not extrapolated."

**Roll-up rules (chapter → book):** count, don't average. `failed` = any
chapter result failed; `stale` = any current-source mismatch; `missing` =
chapters without evidence (new chapters dilute honestly);
`identity_conflicts` from the identity inbox; `blocked` when the chapter dir
is unavailable; `unavailable` when the stage isn't offered for the profile
(e.g. patterns on non-technical); overall book cell = worst-of with counts
shown. Partial states (`PARTIAL`, `COMPLETE_WITH_FAILURES`,
stale counts) are first-class, matching the existing publishing overview.

**Invalidation:** manuscript byte change ⇒ recompute digests ⇒ affected cells
flip to `stale` on next read (editing already does this inline; MRI/validation/
graph via their hash checks). Manuscript-applying events (only Workbench's
journaled apply) must mark downstream stages stale immediately. Declaration
(YAML) edits re-resolve readiness (contract valid→missing/invalid) without
rewriting history — old reports stay, flagged by comparison.

---

## F. UI proposal — books collection and chapter-level views

Design reuses §D.4 components; all status names below are illustrative copy,
not live data.

### F.1 Books collection view (`/books` → new "Production" tab; route TBD, e.g. `/books/production`)

```
Books — Production Overview                        [Refresh eligible ▾] [Manage stages]
Filter: [All ▾] [x] Stale only  [x] Missing analysis  [x] Blocked  [x] Needs editorial review

BOOK      Meta    MRI      Patterns  Strengthen  Editing   Valid.   Graph
Memory    18/20C  0/20C·STALE  —     not run     NOT_RUN   unknown  n/a
  └ 18 chapters w/ declarations · 20 applicable · 2 new chapters w/o evidence
Inference 39/45C  …           …     …           …         …        n/a
Language  …                                                                   n/a
Math      BLOCKED (chapter dir unavailable — configure Writer registry)

Cell click → detail panel (F.3). Legend: C=current · stale · not run · blocked · n/a.
"Graph" column rendered but fixed to n/a (planned) until §B.10 verifies per book.
```

- Matrix component generalized from `WriterPage` book-table + `QualityMap`
  sorting/filtering; `SimpleStatusBadge` + shared stage-state normalizer (new);
  counts text per cell (never color-only).
- Filters reuse the `PublishingWorkbench` attention pattern
  (`failed+stale+missing+conflicts`).
- Refresh menu: one book / selected / all eligible — disabled with
  `DisabledReasons` when stages lack prerequisites (readiness payloads).
- Existing book selector, workspace form, and human-owned status stay untouched
  (new tab/slot in `BooksCollectionPage`, URL-backed selection).

### F.2 Individual book view (`/books/:id` or `/projects/:id/production`)

```
Memory — Production Pipeline                    [Refresh analysis] [Run eligible pipeline]
Stage filter: [All] Meta MRI Patterns Strengthen Editing Validation · [x] attention only

CHAPTER              Meta      MRI        Patterns   Strengthen  Editing
01 — intro           current   STALE      current    n/a         not run   [evidence ›]
02 — models           current   STALE      current    blocked†    not run   [evidence ›]
03 — retrieval        current   stale…     …          …           …

† blocked: no `strengthening:` section in declaration (readiness detail).
Run panel: queued 2 · running 1 (ch03 patterns 40%) · completed 17 · failed 0 · [Cancel]
```

- Rows from `QualityDiscovery` (canonical chapter list); columns from the
  stage registry (configurable order, §E of the mission).
- Clicking a cell opens the detail panel (F.3); "Run eligible pipeline" runs
  only stages whose readiness is `runnable` (contract valid + provider
  available + approval recorded), chapter-failures isolated.
- Execution progress reuses campaign-card + `ImprovementPanel` stage-list
  patterns with `useApi` polling; survives reload (server rows).

### F.3 Stage detail panel (drawer-or-modal; `Modal wide` or `.resource-detail-panel`)

```
MRI · Memory / 02 — models                                   [Open in Writer ›]
Result: passed (analysis complete; 7 findings)   Freshness: STALE
Source: .writer/mri/memory/02-chapter.mri.json (2026-09-22) · snapshot 91fa… ≠ live 3b0d…
Provenance: observer deterministic · quality_model none · alignment v… · prompt v…
Findings: C:4 Q:1 T:1 R:0 (concepts/questions/transition/reader) — findings are analysis signal, not grades
Diagnostics: chapter edited 2026-11-0x; metadata contract valid (same hash ✓)
Actions: [Re-run deterministic MRI] [Run full MRI (approval + budget)] [Compare with previous]
Before/after: report-level dimension deltas vs 2026-09-15 report (changed: yes; non-causal note)
Limitations: deterministic template wording carries no interpretation; fiction-profile caveat n/a (technical)
```

Content blocks map 1:1 to existing components: `EvidenceCard` (provenance +
diagnostics), `QualityEvaluationCard` (findings + reviews), editing
`_comparison` note, `FollowupRow`/`BlockerRow` (promote to tracked work),
`DisabledReasons` (why full-MRI is disabled: Worker/model/budget/approval).

---

## G. Execution design — jobs, boundaries, permissions, recovery

**Carrier (no new framework):** `integration_executions` + `WriterAdapter`
actions + Writer-side durable stores.

- **M3 (single stage, single book):** add adapter actions, e.g.
  `patterns_observe_book{book_id}`, `mri_observe_book{book_id}`,
  `editing_audit_book{book_id, whole_book=true}`. Each: `approval_required`
  (model or write-adjacent), `risk: bounded_local_computation`,
  `validate_action` (registered book + freshness precondition like the
  existing `SUMMARY_SCHEMA` check in `integrations/service.py:390-405`),
  argv built in `_campaign_args` style, last-line envelope parsed, results
  stored as new `integration_records` (`resource_type writer_stage_evidence`,
  `external_id {stage}:{book}:{chapter}`, whole envelope in `data`,
  `source_version` = stage/schema version). Duplicate active run ⇒ existing
  `Conflict` guard. Poll via existing execution endpoints. Timeout ceiling
  300 s ⇒ chapter-chunk inside the action (Writer's `run_chunk` precedent) or
  one execution per chapter batch in M4.
- **M4 (cross-book, per-chapter):** one narrow table or `integration_records`
  convention: `pipeline_runs{id, profile_id, scope{books,chapters,stages},
  created_by, status, stats}` + `pipeline_stage_states{run_id, book, chapter,
  stage, execution, result, freshness, artifact_ref, attempts, error}`.
  Concurrency 1 per (book, stage) to start (the active-row guard already
  enforces per action; extend keys per stage). Sequential chapter loop with
  resume cursor (Writer campaign precedent); chapter failure ⇒ mark failed,
  continue; cancel ⇒ flag checked between chapters (+ map to Writer
  pause/cancel actions where the engine owns the run); retry ⇒ idempotent
  re-invoke (engines reuse fresh outputs natively).
- **Permissions:** read-only/deterministic stages: confirmation, no approval.
  Model-spending stages (metadata generate, full MRI, strengthening,
  strategy experiments): `approval_required` + Worker health + approved-route
  check + budgets (`max_model_calls`, `--max-wall-seconds`, `--limit`) shown
  before dispatch (readiness + `model-roles` payloads). Manuscript-modifying
  anything: never from the pipeline (only Workbench journaled apply with typed
  author approval + in-lock gate re-check).
- **Recovery:** executions + stage rows are server-side (browser close is
  safe); orphan `running` rows reconciled on startup (existing shutdown-mark
  precedent + Workbench `interrupt_stale` lease pattern as reference);
  history append-only (evaluations precedent: supersede, never rewrite).

---

## H. Before/after integration proposal

Narrow adapters over existing implementations (no new comparison engine):

1. **Editing readability before/after** — reuse `GET /api/editing/chapter`
   `previous_report + comparison` (dimension deltas, `changed`, non-causality
   note). MC adapter: fetch + store refs as stage evidence; render in F.3 with
   the note verbatim. Requires ≥2 audits; with one report show
   `comparable:false` honestly.
2. **Strengthening proposal→applied trace** — reuse `results-packet
   (?include_diff)`, `stage-plan`, dossier, `apply-dossier/apply-check`, and
   Workbench journal reads (`chapter-applies`, `applies()` — same read-only
   file pattern as Mission's Workbench decisions read). Render: original
   passage → candidate → applied bytes (exact) → post-apply measurements →
   newly-stale downstream list. Approval stays typed (`author-approval` with
   identities + rationale); MC never applies.
3. **Validation regression** — reuse stored run manifests + process
   `validation/compare` for run-vs-run deltas; incremental `reuse.jsonl` shows
   what was recomputed vs reused.
4. **Sentence-level history** — defer (sentence-evolution approve/reject,
   delta review, strategy paired arms are sentence/run scope; chapter pipeline
   links out rather than embeds).

Rule enforced in UI copy: a lower warning/finding count is displayed as a
measurement delta with semantic-preservation evidence beside it (transfer
probes, comparison payload, independent review state) — never as "better".

---

## I. Risks, unresolved questions and explicit gaps

1. **Transport gap (biggest):** Mission→Writer is CLI-only; the two cheapest
   M3 stages (patterns, deterministic MRI) are **HTTP-only** in Writer and
   Writer web was down at research time. Either (a) add a loopback HTTP client
   to the adapter (needs Writer launch/health story — `launch_definitions`
   already manages `writer-web.exe`), or (b) add thin CLI wrappers emitting
   the same JSON. Decision required before M3; M1/M2 need neither.
2. **Registry/path drift (observed live):** memory's chapters resolve to
   `C:\books\memory\content\books\memory` (22 files) in Mission/Mission-registry
   reads, but stored MRI ledger paths and the compile report reference
   `C:\Projects\memory\…` (gone) and `memory.md` (missing). Freshness reads
   must resolve through the **live registry chapter dir**, and any
   `unknown`-with-drift must say which root disagreed. Healing belongs to
   Writer (registry edit + author approval), per MC-PUBLISH-02.
3. **Editing store cwd-sensitivity (observed live):** `editing summary --json`
   run from `C:\Projects\writer` reported `store_path
   C:\Projects\mission\.writer\editing` and all-`NOT_RUN`, while a 10.9 MB
   `summary.json` + reports exist under `C:\Projects\writer\.writer\editing`.
   MC must pin `working_directory` per action and treat `store_path` as
   authoritative-per-invocation, or audits will fragment across stores.
4. **Timeout ceiling:** `run_tool` caps at 300 s; whole-book model audits will
   exceed it — chunk (chapter batches / `run_chunk` pattern), never raise the
   cap silently.
5. **Cost unknowns:** full-MRI AUTO cost per book unmeasured here (section
   count × calls); editing-audit model involvement unaudited at the call-site
   level; cognitive-graph cost unknown. No model spend without a bounded
   proposal + authorization (mission constraint §I).
6. **Contract coverage:** strengthening requires a `strengthening:` declaration
   section most chapters likely lack; readiness will honestly report
   `missing/invalid` — the pipeline must present this as author work (add the
   section), not as engine failure.
7. **Genre profiles:** patterns `technical`-only; editing profile
   `technical-nonfiction-v1`; deterministic MRI weak on fiction. Profiles per
   genre are M2 config work with Writer-side verification each.
8. **Migration hygiene:** `035_website_post_evaluations.sql` untracked vs
   `036–038` + count assertion (`LIVING-WORK-BOOKS-01-W2-REPORT §Verification`)
   — coordinate numbering before any M4 table lands; prefer `integration_records`
   conventions / settings-table JSON to defer DDL.
9. **No cancellation primitive** for generic integration executions (only
   Writer campaign pause/cancel) — M4 must add cooperative cancel flags.
10. **Fiction books** (`C:\fiction-books`, `writer_registry` fiction roots vs
    Mission roots drift noted in MC-PUBLISH-02 §5) inherit all of the above
    plus identity reconciliation — keep the framework generic (profiles per
    book kind) but pilot on technical nonfiction only.

---

## J. Proposed implementation milestones with acceptance tests

| Phase | Deliverable | Acceptance (must all pass) |
|---|---|---|
| M0 | This report | File exists; zero code/config/DB/manuscript changes (verify `git status` clean apart from pre-existing `.writer/writer.db` runtime file) |
| M1 | Stage registry + read-only matrix backend | `GET /api/pipeline/stages` returns versioned registry (ids, labels, profiles, required/optional, invalidation edges, UI actions); `GET /api/pipeline/books/{id}` returns chapter×stage cells each with `{result, freshness, artifact_path, digest_compared, observed_at, diagnostics}`; memory pilot: MRI cells `stale` with mismatched hashes shown, patterns `not_run`, editing `not_run`, validation `unknown` (no store), all cells traceable; tests: fixture book with fresh/stale/missing/unreadable artifacts incl. temp-copy staleness test (no manuscript touch) |
| M2 | Configurable matrix UI (F.1–F.3 minus execution) | Books production tab + book chapter matrix + detail panel render M1 data; filters (stale/missing/blocked/review) work; stage enable/disable + order + profile overrides persist (settings-table JSON or narrow table); no invented statuses (test asserts every cell maps to a registry stage + evidence ref); links to publishing/Writer/Workbench work |
| M3 | One-click safe stages | One new adapter action (patterns or deterministic-MRI first) with approval gate, duplicate guard, bounded time; click → execution row → poll → new `integration_records` → matrix cell updates; browser closed mid-run → reopen shows truthful progress; tests: idempotent replay, concurrent-dispatch refusal, failure preserves prior evidence |
| M4 | Durable cross-book jobs + progress | `pipeline_runs` + stage-state rows (or records-convention); sequential resume-safe chapter loop; per-chapter isolation (1 failure ≠ book failure; "19/20 current" rendering test); cancel + retry; startup orphan reconciliation; cross-book queue with concurrency 1/book/stage |
| M5 | Before/after + strengthening + approvals | Editing comparison + strengthening packet adapters read-only in UI; author-approval flow (typed identities + rationale, no auto-apply); apply (Workbench-side only) marks downstream stale; undo path shown; non-causality copy enforced by test (no "improved" wording without semantic evidence) |
| M6 | Graph + iteration loops | Chapter-semantic graph stage verified per book (path resolution fixed, hashes compared) or stays `unavailable` with reason; knowledge-state aggregation read; versioned iteration (run N+1 supersedes, history kept); cognitive graph only if provider verified |

Each milestone ships backend tests (real fixtures, digest compares, envelope
validation), frontend tests (matrix renders, filters, no-invention assertions),
and docs updates. No milestone edits manuscripts, commits, or publishes.

---

## K. Recommended first pilot (read-only; bounded follow-up)

**Book:** `memory` (representative technical book, richest stored evidence:
18 MRI chapter reports + `book.mri.json`, 18 metadata YAML, generation ledger
with costs, compile diagnostic showing drift). **Chapters:** `01`, `02`, `18`
(small→large MRI files). **No manuscript mutation** (including no
manufactured staleness — use temp copies).

1. **Discovery** (verified): `GET /api/books/writer-registry` →
   `memory.chapter_dir`, `chapter_count`; `GET /api/publication/publishing?project_id=memory`
   → `manuscript_discovery passed/current`, 22 files, fingerprint
   `7a49612e…` (both verified live 2026-11-22).
2. **Current-state** (exact, verified commands/APIs):
   - MRI: for each sample chapter compare file bytes to stored report —
     `python -c` sha256 of `C:\books\memory\content\books\memory\NN-chapter.md`
     vs `.writer\mri\memory\NN-chapter.mri.json::snapshot_hash`
     (+ `provenance.metadata_sha256` vs canonical metadata hash when the
     declaration exists). Expect `stale` (mismatch reproduced 2026-11-22).
   - Metadata: `writer metadata check --project memory --chapter 01-chapter.md
     --no-write --json` and `writer metadata contract --project memory
     --chapter 01-chapter.md --json` (flags verified in
     `commands/metadata.py:571-584, 540-548`; `--help` first to confirm
     `--no-write` on this build; read-only by flag).
   - Editing: `writer editing show <report_id> --json` / `status` for the one
     stored lineage if any resolves for memory (commands verified
     `editing.py:247-299`; `summary` already verified live).
   - Validation: list `C:\books\memory\.writer\validation` (absent ⇒
     `unknown`, honestly).
3. **Execution (bounded, needs authorization — NOT run in research):**
   `writer editing audit memory --chapter 01-chapter.md --json` (single-chapter
   scoped audit; writes one Writer-owned report artifact; manuscript untouched;
   approval-gated in MC action design; stay under the 300 s runner cap or
   chunk). Rationale: editing audit is the only full round-trip (execute →
   stored report → digest-compare → comparison object) whose write scope is a
   single `.writer` artifact dir. Deterministic patterns/MRI-observe are
   cheaper but need the M3 transport decision (I.1) first.
4. **Stored outputs:** the new `edit-*.json` report + updated index/summary;
   record `report_id`, `canonical_fingerprint`, per-file sha256.
5. **Staleness:** copy `01-chapter.md` to temp, flip one word, recompute both
   `writer_source_digest` and MRI `snapshot_hash` against the stored report —
   expect mismatch ⇒ `stale`, original untouched.
6. **Aggregation:** 3 sampled chapters roll up to `x/3 current` per stage with
   `missing` for unevidenced chapters; book-level counts unchanged elsewhere.
7. **Progress/failure:** run through the new M3 action; assert execution row
   transitions, pollability after browser restart (simulated by fresh GETs),
   and failure preservation (kill-switch test keeps prior evidence + error).
8. **Before/after:** `writer editing compare <old_report> <new_report> --json`
   (command verified `editing.py:299+`) — expect `comparable:true/false` with
   the non-causal note; display only, no quality claim.

**Cost envelope for the pilot:** deterministic checks ≈ $0; single-chapter
editing audit presumed deterministic/inexpensive (confirm `scoring.py` call
sites pre-authorization); metadata contract/check $0. No full-book model runs.
Abort criteria: any step writes outside `.writer/*`, exceeds 300 s, or requires
Worker spend beyond the stated envelope.

---

## Appendix — source index (where every claim above can be re-checked)

- Mission: `backend/mission_control/publication/{evidence,identity,fingerprint,publishing,service,policy}.py`;
  `backend/mission_control/adapters/writer.py`; `integrations/{runner,service,store}.py`;
  `api/{integrations,projects,publication,writer,quality}.py`;
  `writer/{service,evaluations,queue,decisions,campaign_summary,improvement_summary,evolution_summary,intel_summary}.py`;
  `writer_registry/{adapter,sync}.py`; `living_book/quality.py`;
  `quality/service.py`; `persistence/migrations/{002,003,004,005,029}.sql`;
  `config.py`; `frontend/src/pages/{BooksPage,PublishingWorkbenchPage,BookPublishingPage,WriterPage,ProjectPage,LivingBookPage}.tsx`;
  `frontend/src/{api/client,useApi,components/ui,types/api}.ts*`.
- Writer: `packages/writer-web/writer_web/{main.py,routes/{metadata,mri,artifact_patterns,editing,compiler,cognitive_graph,chapter_improvement,book_campaign,improvement(_via chapter_improvement),strengthening_campaigns,process,gate,evidence,sentence_evolution,readthrough,desk,jobs},services/{mri_observe_service,artifact_patterns_service,web_job_dispatcher,job_display}}`;
  `packages/writer-runtime/writer_runtime/domains/{metadata{,_generation},mri,artifact,improvement{,/services},editing,project_validation,compiler,graph{,/services},knowledge_state,quality,analysis_state,readthrough,process,book,writethrough,conversation,hands_free}`;
  `packages/writer-cli/writer_cli/commands/{metadata,mri,editing,validate,finalize,book_campaign,graph,knowledge_state,compiler}.py`;
  `packages/writer-core/writer_core/{projects/project_loader,config/settings}.py`.
- Live artifacts: `C:\books\memory\.writer\{mri\memory\*.mri.json+book.mri.json,metadata\generation\*.json,book\compile\book_compile.json,cache\runtime\mri.observation\*}`;
  `C:\books\memory\{content\books\memory\*.md,metadata\*.yaml}`;
  `C:\Projects\writer\.writer\editing\{index,summary}.json`;
  `C:\Projects\writer\config\web\projects.yaml`; Mission SQLite
  `data/mission_control.db` (`applications`, `launch_definitions`, `books`,
  `integration_records`, `integration_executions` — read-only selects).
- Prior docs: `docs/MC-WRITER-01-WRITER-INTEGRATION.md`,
  `docs/MC-PUBLISH-02-ARCHITECTURE.md`,
  `docs/LIVING-WORK-BOOKS-01-W2-REPORT.md`, Writer
  `docs/workbench-capability-inventory.md`.

*End of research report. Awaiting approval before any implementation (M1).*

---

## Addendum 2026-11-22 — three-way verification (no code changed)

Three parallel code-reads completed after the draft above and confirm it; deltas only:

- **Mission reuse (Investigation A/D/G):** `BooksPage.tsx:45-104,115-328,330-481` manual, no matrix/polling; `PublishingWorkbenchPage.tsx:80-277` read-only rows + follow-ups; `BookPublishingPage.tsx:36-410` evidence cards + assessment flow; `useApi` polling primitive exists but publishing/books pass no `pollMs`; no websocket/SSE. Evidence/fingerprint/identity/policy/service/followups verified complete; publishing summary + overview reuse one computation path. Durability = server-side `BackgroundTasks`/`asyncio` + `IntegrationExecution(queued→running→succeeded/failed)` with duplicate-active guard + bounded runner (60–300 s) + shutdown-mark-failed; survives browser close, not server restart. No chapter fan-out, no per-stage progress/cancel, no Mission→Writer HTTP client (CLI-only).
- **Execution templates (Investigation G cross-repo):** beyond `integration_executions`, reuse patterns from `experiment_workflows` (`idempotency_key` UNIQUE, approval hash, `cancel_requested`, event log), `quality_campaigns` + `quality_evaluations` + `technical_extraction_runs` (per-chapter isolation, heartbeat `current_chapter`, `resume`/`stop`, `COMPLETE_WITH_FAILURES`-style partial), Writer `book_campaign/book_coordinator.py` sequential resume-safe loop, Writer `workflow_graph/proposal_apply.py` frozen-hash + deterministic apply-ID gate. Do not use Writer `WebJobEventService` (self-declares memory-only), BookBuilder (sync renderer `build.py:41`), or ALIVE chapter workflows (chapter-scoped) as book runners. Hash join still open: Mission `sha256(CRLF→LF)` vs Writer `sha256:` raw vs workflow-graph raw.
- **Writer inventory (Investigation B/C/H):** full domain read confirms draft §§B–C: document/metadata-canonical + metadata-generation, MRI (`metadata=None` degraded path verified — MRI does **not** require metadata), artifact patterns (independent of MRI), compiler + manuscript-IR + knowledge-state + story-state, strengthening (needs `strengthening:` contract + lexicon; re-parses MRI JSON from disk), editing audit (contract `read-only`, `audit_mode=read_only`), validation/project-validation + `writer finalize --approved-by`, graphs (chapter-semantic partial, cognitive unverified per book), readthrough/revise/desk/sentence-evolution before-after substrates. **Utterance:** `writethrough` utterance→stage→advance span loop exists (runtime + web, no CLI) but is a session-span loop, not a chapter production stage — draft recommendation stands (drop "Utterance" from pipeline or rename the intended concept). Stage-ID mapping: this report's `metadata/mri/patterns/strengthening/editing/validation/graph` = inventory `S02/S03/S05/S07/S08/S10/S06+S09` families.

No manuscript edits, commits, or migrations were made for this addendum.
