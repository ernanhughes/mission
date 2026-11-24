# PUBLICATION State

**Updated:** 2026-11-24 (PUB-02 ACCEPTED by author direction — §8. Next: PUB-03.)

## 1. Current position

PUB-00 ACCEPTED. PUB-01 ACCEPTED 2026-11-24 on independent verdicts:
Codex (architecture/integration) CONDITIONAL — validation-invocation
reproducibility + D-PUB-08 schema/retry wording, both fixed docs-only in
CAPABILITIES/DECISIONS/ACCEPTANCE (no code touched); DeepSeek
(regression/verification) ACCEPT — 86+1 / 114 / 30 suites reproduced, sole
quality failure proven pre-existing and catalog-independent, registry 167
with scoped validation holding, source safety + read-only holds confirmed.
Production code changed in exactly one file for scoped registry
reconciliation: `C:\Projects\writer\…\capabilities\catalog.py` (+2 manifests).
Programme docs changed only in `docs/programmes/publication/` (7 canonical
files, this file included). No manuscript changes, no paid model runs, no
migrations, no deploys, no commits/pushes, no unrelated refactoring, no
deletion of unrelated files. Docs created (canonical set only):

- `docs/programmes/publication/` — README, ARCHITECTURE, CAPABILITIES,
  ROADMAP, STATE (this file), ACCEPTANCE, DECISIONS.

## 2. Accepted into the programme

- Objectives, scope, end-state workflow (§10 twelve-step flow adopted as the
  design target), lifecycle, agent defaults, calibration direction, ~950/1000
  with critical-defect override.
- Architecture grounded in live source with cited paths; ownership table;
  U1–U5 explicitly open.
- Capability inventory: reusable-now vs extend vs missing, with entry points,
  determinism/mutation behaviour, and three live verifications (catalog build,
  editing scorer on Jev Ch1, legibility analyzer on Jev Ch1).
- Taxonomies: CR01–CR12 cruft; complexity signal list; representation ladder;
  twelve-step editorial workflow; Mission section requirements — all adopted as
  calibration/design inputs, none treated as established measures.
- Stage IDs PUB-00…PUB-11 with dependencies and per-stage gates.
- PUB-01 additions: 14-step repeatable stage contract (README §5);
  CR01–CR12 one-line decision rules (CAPABILITIES §6); AI primitives inventory
  with PUB-02/03/04 reuse verdicts (§7); registry reconciliation with
  classifications (§8, catalog 167); quality-surface decision D-PUB-07
  (CLI-only + unblock plan); model-routing contract D-PUB-08 (no new gateway);
  reconciliation principle D-PUB-09; provenance/label conventions
  (ACCEPTANCE §2.1); Jev decision table for PUB-03 (ROADMAP PUB-03);
  working Writer test invocation + focused/regression results (§4.3).

## 3. Active work

PUB-02 scope-complete, pending the review gate (Codex architecture/integration
+ DeepSeek regression — prompts in the handover report §9). Criterion for
acceptance: scope-done (below) vs verified-done (reviewers' verdict).

PUB-02 scope-done 2026-11-24 (Muse implementation), fix batch 2026-11-24:
- Entry re-baseline confirmed: `test_direct_rejects_invented_citations` still
  the sole quality failure (86+1 identical to PUB-01; catalog-independent,
  pre-existing); mediated_read/evaluation_fabric/capability 114 passed;
  catalog CLI suites 30 passed; `tests/core/test_reader_legibility.py`
  15+2 (2 failures pre-existing in the untouched reproduction_readiness
  evaluator path — PUB-01 never ran this file).
- CR01–CR12 deterministic classifier (`publication_cruft.py` v0.1,
  profile `cruft-v0.1` UNCALIBRATED) + `writer cruft review` CLI; no catalog
  change (library+CLI, D-PUB-10); zero model dispatches.
- 27 unit + 40 calibration tests pass (29 dev + 10 held-out + split-discipline;
  held-out evaluated once against the frozen profile, never tuned).
- Live read-only demonstration: Jev Ch1 → 1 CR04-LOW finding (CAPSTONE-02B
  scaffolding; fact preserved), 11 preserved, 7 needs-evidence;
  Jev Ch2 → 0 findings, 6 preserved, 7 needs-evidence.
- No manuscript/result/ledger changes, no paid model runs, no migrations,
  no deploys, no commits/pushes, no unrelated refactoring, no unrelated
  deletions. Temp artifacts removed (`C:/Temp/pub02-*.json` deleted at handover).

PUB-02 fix batch 2026-11-24 (Muse implementation; addresses the Codex
CONDITIONAL blockers + DeepSeek ACCEPT observations, re-verified below):
- CR01 silent pass closed: a status claim with no identifiable backticked
  arm now reports NEEDS_EVIDENCE even when result rows exist (binding
  required, never silent pass). Regression test: unrelated rows +
  unquoted arm → NEEDS_EVIDENCE, never silent pass.
- CR05 bound-evidence comparison now extracts the claim's own
  version/hardware facts (e.g. "requires CUDA 11.8" vs `{"cuda":"11.8"}`,
  numeric comparison with operator support) instead of tokenizing the
  regex pattern; uncomparable claims report NEEDS_EVIDENCE. Tests:
  matching facts pass silently (no false fire on unrelated pattern
  tokens), mismatched version is a finding, unbound package is
  indeterminate.
- Hygiene: `CruftAdjudicationResponse.verdict` is now an
  `AdjudicationVerdict` enum (keep_finding/preserve/unclear),
  rationale/quote_used non-empty, `quote_supported_by(passage)`
  enforces quote-drawn-from-passage; contract-tested, zero dispatches
  stay zero. Unused `get_runtime` import removed from the cruft CLI.
  CR09 dedupes by block before the minimum-blocks threshold (two copies
  in one block no longer satisfy it). CR07/CR08 `confirmed_stale`
  fixture entries relabelled `candidate_positive` (screen outcome
  separated from ground truth; calibration harness asserts
  model_candidate on those entries).
- Suites: `tests/core/test_publication_cruft.py` 35 passed (27 + 8 new),
  calibration 40 passed (split discipline intact; 4 CR07/CR08 entries
  relabelled, expectations unchanged) — 75 total.
- Live re-demonstration: Jev Ch1 with revision-only index
  (`{"evidence_revision":"jev@c7aaad7"}`) → 1 finding (CR04-LOW,
  CAPSTONE-02B scaffolding), 11 preserved, 9 needs-evidence; with
  chapter inventory 1–36 bound → 1/11/7, identical to the PUB-02
  baseline (fingerprint `435974701050…` unchanged). The 9-vs-7 delta is
  the two CR06 needs-evidence entries from the unbound chapter
  inventory, NOT the CR01/CR05 fixes (no rows/facts bound in either
  run, so those paths behave as before by design).
- Regression unchanged: editing+quality 86+1 (sole failure still
  `test_direct_rejects_invented_citations`, byte-identical);
  mediated_read/evaluation_fabric/capability_resolution 114 passed;
  catalog CLI suites 30 passed; `tests/core/test_reader_legibility.py`
  15+2 (identical pre-existing `EnvironmentIdentityStatus.BLOCKED`
  failures). Catalog still 167; zero model dispatches; Jev tree
  unmodified (only pre-existing untracked `scripts/`).

PUB-02 fix batch 2 (2026-11-24; Muse implementation, addresses the Codex
delta re-review BLOCKED points; pending Codex + DeepSeek delta re-review):
- CR01 arm-field binding (`publication_cruft.py` `_detect_cr01`): the claim
  arm is now bound against the actual `arm` field of each result row, never
  the serialized whole row. Rows without a parseable `arm` field, or a
  claimed arm matching no row's `arm` field, report NEEDS_EVIDENCE (never a
  stale finding on a mere miss, never a silent pass). Regression tests: arm
  string in an unrelated row field only, and claimed arm matching no row
  `arm` field, both → NEEDS_EVIDENCE.
- CR05 hardware agreement (`_affirmative_hardware` + `_is_affirmative_fact`):
  minimal bound-fact format with explicit polarity (negation cues: not/no/
  without/never/unavailable/absent/missing/false/disabled/denied/n't...;
  empty/unknown values are not affirmative). Agreement needs the claimed
  token in an affirmative container (a key names hardware only if its value
  does not negate it); negation, unknown polarity or no comparable fact →
  indeterminate NEEDS_EVIDENCE; affirmative-different-hardware still
  contradicts. Version numeric comparison unchanged. Tests: "not A100" bound
  vs A100 claim → indeterminate; `{"a100": "not available"}` → indeterminate;
  affirmative `{"hardware": "A100"}` → silent pass (positive control).
- Quote support enforcement (`ensure_verdict_quote_supported` +
  `dispatch_typed_task`): a verdict whose non-empty `quote_used` is not drawn
  verbatim from the adjudicated passage is returned as failed
  (`INVALID_TYPED_OUTPUT`) -- reported, never repaired/redispatched (D-PUB-08
  law 6/7). Pure-DTO enforcement is impossible (the passage lives in the
  request, not the response contract), so enforcement sits at the dispatch
  seam plus a reusable validation helper. Tests: fabricated quote rejected
  at dispatch with fake models (offline, zero live calls); genuine quote
  accepted.
- Suites: `tests/core/test_publication_cruft.py` 42 passed (35 + 7 new),
  calibration 40 passed (unchanged) -- 82 total. Editing+quality 86+1 (sole
  failure still `test_direct_rejects_invented_citations`, pre-existing);
  mediated/evaluation_fabric/capability 114; catalog CLI 30; legibility 15+2
  (identical pre-existing `BLOCKED` failures). Live Jev Ch1: revision-only
  index → 1/11/9; inventory 1-36 → 1/11/7 (fingerprint `435974701050…`,
  identical to baseline). Catalog 167; Jev unmodified; zero dispatches.

PUB-02 fix batch 3 (2026-11-24; Muse implementation, addresses the Codex
delta re-review's single remaining demand -- CR05 affirmative-mismatch
contradiction): a different affirmative hardware token contradicts ONLY
with exclusivity evidence (`publication_cruft.py` hardware-exclusivity
rule + `_exclusive_hardware` / `_hardware_contradicts` helpers; version
numeric path untouched). Contradiction needs (a) an explicit sole-hardware
scope on another affirmed value token (only/exclusively/exclusive/solely/
single/sole, e.g. `{"hardware": "H100 only"}`) or (b) a known-incompatible
accelerator-family pairing (TPU vs the NVIDIA-GPU stack
GPU/CUDA/A100/H100/V100 -- disjoint vendor stacks; CPU exempt as
co-present; same-family pairs overlap, never exclude). Default (no
exclusivity evidence) is indeterminate NEEDS_EVIDENCE. Negation/unknown
handling unchanged. Regression tests: GPU bound vs A100 claim and H100
bound vs A100 claim → NEEDS_EVIDENCE (overlapping/same-family);
`{"hardware": "H100 only"}` vs A100 claim → contradiction finding;
`{"hardware": "TPU"}` vs A100 claim → contradiction finding;
affirmative `{"hardware": "A100"}` match still passes silently.
- Suites: `tests/core/test_publication_cruft.py` 46 passed (42 + 4 new),
  calibration 40 passed (unchanged) -- 86 total. Editing+quality 86+1 (sole
  failure still `test_direct_rejects_invented_citations`, pre-existing);
  mediated/evaluation_fabric/capability_resolution 114; catalog CLI 30;
  legibility 15+2 (identical pre-existing `BLOCKED` failures). Live Jev
  Ch1: revision-only index → 1/11/9; inventory 1-36 → 1/11/7
  (fingerprint `435974701050…`, baseline-identical). Catalog 167; Jev
  unmodified (`scripts/` pre-existing untracked only, HEAD `c7aaad7`);
  zero model dispatches; zero paid runs; temp evidence JSONs removed.

PUB-02 fix batch 4 (2026-11-24; coordinator-executed, single Codex residual --
no new files): the CR05 family-incompatibility rule is removed.
Affirmative-hardware mismatch now contradicts ONLY on an explicit
sole-hardware scope cue (only/exclusively/exclusive/solely/single/sole
on another affirmed value token, e.g. `{"hardware": "H100 only"}`);
every other mismatch (GPU vs A100, H100 vs A100, TPU vs A100, CUDA vs
A100) is indeterminate NEEDS_EVIDENCE, since the bound facts never
establish a single-device or exhaustive inventory. `_CR05_HARDWARE_FAMILIES`
deleted; `_hardware_contradicts` is exclusivity-cue-only. Test
`test_cr05_known_incompatible_hardware_contradicts` rewritten as
`test_cr05_cross_stack_hardware_is_indeterminate` (TPU bound vs A100
claim → NEEDS_EVIDENCE); explicit-exclusivity contradiction test
unchanged and green.
- Suites: cruft 86 passed (46 unit + 40 calibration); ruff clean both
  files. Fast neighbours re-run in-session: editing+quality+
  legibility+catalog-CLI = 134 passed, 0 failed (the two pre-existing
  failures are gone because the owning teams' fixes landed concurrently
  -- see §4.3 -- not because of PUB-02). Mediated/eval set untouched
  by batch 4 (DeepSeek: 114 on batch-3 tree). Live Jev Ch1:
  revision-only → 1/11/9; inventory 1-36 → 1/11/7 (fingerprint
  `435974701050…`, baseline-identical). Catalog 167; Jev unmodified;
  zero dispatches; $0.

## 4. Blockers / risks

1. **Catalog↔registry: PUBLICATION-scoped agreement achieved; full green
   documented-open.** `editing` + `mediated_read` manifests added (catalog
   165→167). Remainder: 1 missing (`metadata_generation`, unrelated owner),
   46 orphaned (unrelated owners; `council` is forward-relevant to PUB-08),
   1 adapter problem (`analysis_state` EVALUATE). → Writer owning-team backlog
   (CAPABILITIES.md §8); nothing here blocks PUB-02 gates.
2. **`runtime.quality` deliberately CLI-only (D-PUB-07).** Working seam is the
   `writer quality evaluate` subprocess contract. Facade design → PUB-02
   (done for cruft: `EvidenceIndex` bindings + NEEDS_EVIDENCE is the reusable
   pattern; quality facade itself still deferred), surface + bridge → PUB-07,
   migration → PUB-09. U2/U3/U4 open with owners.
3. **Writer test invocation fixed; pre-existing failures recorded.**
   Use `C:\Projects\writer\venv\Scripts\python -m pytest` (3.11.4, CWD
   `C:\Projects\writer`). Editing+quality 86 passed + 1 failed
   (`test_direct_rejects_invented_citations` — post-Stage0 quality change,
   predates PUB-01, owner Writer quality; reproduced identically in PUB-02);
   mediated_read + evaluation_fabric + capability_resolution 114 passed;
   catalog CLI suites 30 passed. PUB-02 addition:
   `tests/core/test_reader_legibility.py` 15 passed + 2 failed
   (`test_evaluator_reports_not_built_without_fabricating`,
   `test_evaluator_does_not_convert_failure_to_pass` —
   `AttributeError: EnvironmentIdentityStatus.BLOCKED` in the untouched
   reproduction_readiness evaluator path; PUB-01 never ran this file).
   Update 2026-11-24: the owning teams fixed all three concurrently
   during the gate (outside PUB-02 scope; PUB-02 file set untouched):
   BLOCKED member added, vertical-slice assertion aligned to the
   committed RETRIEVAL_FAILED code, mri IndentationError fixed, plus
   conftest per-PID DB hygiene and a `long` marker (gate (c) default
   now 113 + 1 deselected; documented 114 needs explicit `-m`
   override). New baselines: editing+quality 87/0, mediated 114
   (override), catalog CLI 30, legibility 17/0, cruft 86 (46+40).
   None was a PUB-02 regression.
4. **Jev evidence correspondence unresolved — carried to PUB-03, not modified.**
   See §4.6.
5. **Naive complexity counts lie** (tables/code inflate sentence metrics;
   ch6/ch7); all PUB-04 work must measure through Writer's parser exclusions.
   Standing PUB-04 watch item.
6. **Review-observation backlog (recorded, no action this stage).**
   DeepSeek observations carried forward: (a) full-suite collection is
   blocked by `tests/runtime/domains/test_mri_semantic_adjudication.py:493`
   `IndentationError` — Writer MRI owner; (b) no automated CLI test for
   `writer cruft review` — later-stage gap, not a PUB-02 gate item;
   (c) `reader_legibility` teardown flake (final-cleanup notice during
   the legibility run) — cosmetic, unrelated to PUB-02.

### 4.6 Jev evidence question (unresolved; binding framing for PUB-03)

`results/ch01.jsonl` holds 27 rows: 20 `provider="predicate"` rows (zero
tokens, empty model, `agrees_with_predicate`) + 7 aggregates. That establishes
the *file* contains predicate-only rows; it does NOT establish experiments
were never completed elsewhere. The author reports a wider Jev programme as
completed — treated as a claim requiring reconciliation, neither verified nor
disproved. Correspondence classes: original vs subsequent artifacts vs
capstones vs equivalent-differently-scoped vs validated replacements vs
unresolved. PUB-03 applies the decision table in ROADMAP.md (pending+match →
update; pending+equivalent → investigate transfer; pending+partial → preserve
limitation; pending+none → unresolved; completed+contradictory → block).
Nothing in `C:\books\jev` (manuscript, results, ledger) was read beyond
characterization or modified in PUB-01.

## 5. Repo revisions observed (PUB-01 execution; read-only except noted change)

| Repo | HEAD | Tree vs HEAD |
|---|---|---|
| `C:\Projects\mission` | `97edb77` | Modified (pre-existing workstream): `backend/mission_control/api/health.py`, `models.py`, `persistence/db.py`, `backend/tests/conftest.py`, `test_postgres_integration.py`, `scripts/migrate_sqlite_to_postgres.py`; untracked (pre-existing): `test_db_isolation.py`, `test_persistence_conventions.py`, `docs/MC-POSTGRES-02-REPORT.md`, `scripts/pg_backup.py`; untracked (this programme): `docs/programmes/`; 3 extra worktrees |
| `C:\Projects\writer` | `bb8dc3f` | Pre-existing: deleted `.cocoder/config.toml`, `.opencode/opencode.json`, `.pi/model-transports/opencode/agents/pi-model.md`, `.pi/skills/writer-metadata/*`; modified `.vscode/settings.json`. **PUB-01 change: modified `packages/writer-runtime/writer_runtime/capabilities/catalog.py` (+77, two manifests). PUB-02 changes: new `packages/writer-core/writer_core/analysis/publication_cruft.py`, new `packages/writer-cli/writer_cli/commands/cruft.py`, modified `packages/writer-cli/writer_cli/main.py` (+5, `cruft` registration), new `tests/core/test_publication_cruft.py`, new `tests/core/test_publication_cruft_calibration.py`, new `tests/core/fixtures/publication_cruft_calibration.jsonl`. Fix batch (same files, no new files): unit tests 27→35, 4 CR07/CR08 fixture entries relabelled `candidate_positive`. Nothing else touched; no stray files (verified).** |
| `C:\books\jev` | `c7aaad7` | Untracked: `scripts/` (pre-existing). Nothing modified. |
| `C:\Projects\workbench` | `dd0c440` | Clean (+2 extra worktrees) |
| `C:\Projects\worker` | `2bb8a8d` | Clean |
| `C:\Projects\work` | `8533143` | Clean |
| `C:\Projects\next` | `d8208b0` | Clean |
| `C:\Projects\inspect` | `af12318` | Clean |
| `C:\Projects\praxis` | `9cbc590` | Clean |
| `C:\Projects\ai` | `a8c4199` | Clean |

`C:\Projects\programmer.ie` does not exist as a checkout (programmer_ie is a
book id in the Writer registry). Review format `Current Text / Recommended
Change` verified in `C:\books\jev\scripts\apply_edits.py`.

## 6. Exact next action

**PUB-02 ACCEPTED 2026-11-24 by author direction (§8). PUB-03 is next
(proposed scope below -- awaiting author go-ahead, not started).**

**After the gate, PUB-03 scope (propose, do not start):** bind manuscript
claims to authoritative repo evidence for ≥3 Jev chapters incl. one
genuinely-stale case (`evidence/ledger.md`, `results/*.jsonl`,
`examples/*/run_*.py`); stale-result and evidence-missing findings live via
the PUB-02 `EvidenceIndex`/NEEDS_EVIDENCE pattern; apply the ROADMAP PUB-03
decision table (pending+match → update; pending+equivalent → investigate
transfer; pending+partial → preserve; pending+none → unresolved; completed+
contradictory → block). Owner: Muse (design), Codex (integration review),
DeepSeek (regression). Manuscript, experiments, migrations, deployment all
out of scope until PUB-06/PUB-10.

## 7. PUB-00 review verdict (recorded PUB-01)

PUB-00 **ACCEPTED** 2026-11-24 as the programme foundation (research and
documentation only; no implementation authorized or executed). Basis: objectives
and end-state workflow adopted; architecture grounded in live implementation
with cited paths; ownership resolved-or-explicitly-open (U1–U5); capability
inventory with callable-vs-role separation and live verifications; CR01–CR12
names + complexity signals adopted as calibration inputs; stable IDs PUB-00…11
with dependencies and per-stage gates; acceptance criteria and next stage
specified. Carried into PUB-01 as issued: catalog reconciliation, quality-surface
decision, model-routing settlement, provenance conventions, test-env repair,
AI-primitives inventory, Jev evidence framing — all executed above.

## 8. PUB-02 review verdict (closed 2026-11-24, author direction)

PUB-02 **ACCEPTED**. Evidence: deterministic CR01–CR12 classifier
(`publication_cruft.py`, profile `cruft-v0.1`, `calibrated:false`) + `writer
cruft review` CLI (library+CLI surface, no catalog change per D-PUB-10);
86 cruft tests (46 unit + 40 calibration, dev/held-out split, frozen
profile, held-out run once); fast neighbours 134/134 green in-session;
mediated/eval 114 (DeepSeek, batch-3 tree; batch 4 untouched those
paths); catalog 167; live Jev Ch1 1 CR04-LOW / 11 preserved / 7
needs-evidence (inventory-bound) with stable fingerprint
`435974701050…`; zero model dispatches; $0 verification spend; Jev and
all repo trees clean of strays, no commits.
Review history: Codex CONDITIONAL → BLOCKED (2 silent-pass risks) →
CONDITIONAL (CR05 exclusivity) → final residual (TPU-vs-NVIDIA
auto-contradiction) applied literally as specified (exclusivity-cue-only
contradiction; cross-stack mismatch → NEEDS_EVIDENCE). DeepSeek ACCEPT
×3 (batch 1 free tier; batch 2 + batch 3 on `opencode-go` fallback, all
$0 metered). The author closed the gate on the applied residual without
a fifth review cycle to bound stage cost (fast-gate policy, README §6);
the change is covered by 4 pinning tests (3 indeterminate + 1
contradiction positive) plus the untouched 82-test base, all green
in-session. Carried into PUB-03: the 7 needs-evidence items and the
EvidenceIndex/NEEDS_EVIDENCE pattern.
