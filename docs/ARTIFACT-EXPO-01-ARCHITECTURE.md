# ARTIFACT-EXPO-01 — Architecture Audit (Stage 00)

Status: MVP implemented (deterministic + contracts + load scoring + UI shell).
Semantic confirmation and whole-book repair campaign are explicitly pending.

## 1. What already existed (reused unchanged)

### Writer (`C:\Projects\writer`)
- `ArtifactEngine.analyze` (read-only) / `clean` (safe-fix only) orchestration.
- `ArtifactAnalysisContext` (paragraph/sentence parse, strips HTML comments and
  code fences, preserves line numbers).
- `ArtifactDetector` base with `rule | llm | hybrid` routing, `supports_llm_execution`,
  `prompt_template`, `# rationale / # score / # answer` parsing, `_should_escalate_to_llm`.
- `DetectorRegistry.build_default_registry` auto-discovery — no registry edit needed.
- `ProfileLoader` with YAML inheritance; `technical.yaml` (per-chapter) and
  `technical_book.yaml` (narrow book-tic pass, deliberately not extended).
- `ArtifactIssue` / `DetectorResult` / `ArtifactAnalysisResult` contracts.
- `ArtifactRepairEngine` (candidate-only, SHA-guarded apply), `ArtifactRepairEvaluator`
  (deterministic quality/voice gates), `ArtifactRevisionAcceptanceDecision`,
  `check_semantic_loss` (deterministic deletion guard), `book_repair_check`,
  `ArtifactDamageRanker`, `ArtifactRepairPacketBuilder`, `ArtifactStatusStore`.
- `BookTextMap` (`map_full_line_to_source` is the canonical virtual-line resolver).
- `ArtifactModelsAdapter` over `runtime.models` (Pi-default infrastructure).

### Workbench (`C:\Projects\workbench`)
- `writer/patterns.py`: deterministic scan display, revision-bound records
  (`revision_of`), paragraph placement, `SHOW_CAP` triage, `dismissed` memory,
  `instruction()` composer prompts, candidate-only Fix (no auto-apply).
- `chapter.py` lossless parse (only plain prose editable; headings, fences,
  tables, lists, quotes, shortcodes, front matter verbatim).
- `proposals` Apply/Undo (one chapter, one commit, journaled), `strengthen`
  author-decision (`leave_original` vs undecided).
- `writer/client.py` thin HTTP client (only place that knows Writer URL shapes).

### Mission Control (`C:\Projects\mission`)
- `quality/service.py`: append-only `quality_evaluations` with six-dimension
  rubric (`manuscript-prose-v1`), mean-equal-weights overall, staleness derived
  at read time, campaigns with fingerprints.
- `adapters/writer.py`: consumes Writer `editing summary --json`, never imports
  Writer parser/scoring code, never edits manuscripts.
- `api/quality.py`, `api/writer.py`, `ProjectPage QualityPanel`, `WriterPage`.

## 2. What was extended (this commission)

| Area | Change | File |
|---|---|---|
| Writer detector | New hybrid detector `expository_overload`, family `EXPOSITORY_OVERLOAD`, subtypes `EXPO_COMPRESSION` / `EXPO_INTERRUPTION` / `MIXED`, version `expo-v1` | `packages/writer-runtime/.../detectors/expository_overload.py` |
| Writer profile | Enabled in `technical.yaml` (rule mode, weight 0.9) | `profiles/technical.yaml` |
| Writer repair | `REORDER_EXPLANATION` strategy for `EXPOSITORY_OVERLOAD` / `EXPO_*` + mapping | `revision/artifact_repair_strategy_service.py` |
| Writer preservation | Statistical-qualifier guard (median/mean/variance/percentile/...) | `revision/semantic_loss.py` + `test_semantic_loss_median_guard.py` |
| Workbench display | `EXPOSITORY_OVERLOAD` labels/hints, multi-para scope wording | `src/workbench/writer/patterns.py` |
| Mission Control | New independent `artifact_load_observations` store + service + API | `backend/mission_control/artifact_load/`, `api/artifact_load.py`, `migrations/017_*`, `models.ArtifactLoadObservation`, `schemas.ArtifactLoad*` |
| Mission Control UI | `ArtifactLoadMap` alongside prose scores, independent layers | `frontend/src/pages/ProjectPage.tsx`, `types/api.ts` |

## 3. Ownership

- Writer owns detection, classification, metrics, repair planning, preservation checks.
- Workbench owns findings display, editor navigation, candidate review, authorized apply.
- Mission Control owns aggregate reporting, history, orchestration (read-only).
- AI/ Pi owns model execution via existing authorized paths only.
- Book repository stays the canonical manuscript source. Detection never writes to it.

## 4. Finding flow (Writer → Workbench)

1. Author presses Scan. Workbench calls Writer `artifact.patterns` (deterministic).
2. Writer runs `ArtifactEngine(profile=technical)` including `expository_overload`
   in rule mode; returns issues with `type=EXPOSITORY_OVERLOAD`,
   `stats={subtype, status=MECHANICALLY_FLAGGED, fingerprint, para_ids,
   features, compression_pressure, interruption_pressure, proposed_strategy}`.
3. Workbench `make_record` validates schema/line numbers, binds to `revision_of(text)`.
4. `triage` places occurrences in editable prose paragraphs only; protected
   material (tables, lists with code identifiers, quotes, code) counted separately.
5. Author sees "N paragraphs worth a look · M weaker not marked" with diagnosis,
   strategy, confidence/review state. Fix puts a `REORDER_EXPLANATION` instruction
   in the composer; Apply remains explicit and journaled.

## 5. Aggregate flow (Writer → Mission Control)

1. A bounded job (future: `editing audit --all` extension or book-scan script) runs
   Writer detection per chapter and emits `(chapter_id, revision, eligible_words,
   evaluated_units, findings[], coverage_mech, coverage_sem)`.
2. `POST /api/artifact-load/observations` persists via `record_observation`.
   `compute_load` clusters overlapping findings into regions (max severity wins),
   computes `weighted_load = sum(region weights)/(eligible_words/1000)` from
   **confirmed** findings only, plus `mechanical_pressure` from candidates.
3. `GET /api/artifact-load/workspace` returns per-chapter current observations.
   `GET /api/artifact-load/compare` reports before/after with denominator-stability
   warnings (word-count growth without region reduction is flagged, never rewarded).
4. Mission Control never merges load into the six prose scores. Both are shown
   side by side; disagreement is preserved as evidence.

## 6. Model execution

- Semantic review uses `ArtifactDetectionExecutionContext` with
  `model_runner=ArtifactModelsAdapter(runtime.models)` and the detector's
  `prompt_template` (10-question evaluation, `NO_ISSUE` allowed, exact-quote
  requirement, invalid-evidence on quote mismatch).
- Preferred route `opencode-go/deepseek-v4.1-flash` is recorded as
  `requested_model`; the actual runner reports `actual_model`. Never silently
  substituted. Bounded requests; file/stdin-compatible paths for large inputs.
- MVP status: rule path live; hybrid escalation implemented
  (`_should_escalate_to_llm`: flagged units plus low-pressure spot-checks, never
  an absolute gate) but no production semantic campaign has run. All pilot
  observations are `MECHANICALLY_FLAGGED` with `coverage_semantic=0.0` and
  `weighted_load=0.0` — mechanical pressure only, not confirmed defects.

## 7. Fingerprints and locators

- Per-finding `fingerprint = sha256(source:lines:quote)[:16]`; per-scan
  `revision_of(text)` (Workbench) and `chapter_revision=sha256` (Mission).
- Writer `BookTextMap.map_full_line_to_source` is canonical for virtual-book
  lines. No finding targets code fences, Hugo shortcodes, tables, equations,
  front matter, or non-editable blocks. Stale findings (revision mismatch) are
  shown as stale, never applied. History is append-only in both Writer
  (`ArtifactStatusStore`, report stores) and Mission Control.
