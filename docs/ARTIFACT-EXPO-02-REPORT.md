# ARTIFACT-EXPO-02 — Acceptance Report

**Status:** IN PROGRESS (Stage A + B + calibration infrastructure complete and tested;
46-passage semantic sweep running; D/F/H/I pending sweep results).

## A. Implementation summary (by repository)

### Writer (`C:\Projects\writer`) — reused, extended, no new engine

Reused unchanged: `ArtifactEngine`, `ArtifactAnalysisContext`, detector base
(rule/llm/hybrid routing, `# rationale / # score / # answer` parsing),
`DetectorRegistry` auto-discovery, `ArtifactModelsAdapter` pattern,
`REORDER_EXPLANATION` strategy instructions, `check_semantic_loss` gate,
frozen semantic-loss corpus (all still passing).

Extended for EXPO-02:

- `artifact_engine/detectors/expository_overload.py`
  - Rule findings now carry `severity="UNASSESSED"` with a separate
    `stats.review_priority` (HIGH/MEDIUM/LOW from pressure). Severity is
    written only by the semantic confirmation path. Merge keeps max priority.
  - `_parse_llm_answer_to_result`: strips one enclosing ` ```json ` fence pair
    before parsing (formatting, not content); whitespace-collapsed quotes stay
    `INVALID_EVIDENCE` (exact-span rule unchanged).
  - Prompt hardened: quote must be copied character-for-character with blank
    lines preserved; a whitespace-differing quote is unverifiable.
- `domains/artifact/mapper.py`: `_severity_score` maps MEDIUM like MED and
  returns 0.0 (not mid-scale 0.5) for UNASSESSED/unknown — unknown is no signal.
- `revision/semantic_loss.py` (Stage I2/F2, all deterministic):
  - `_normalize_number_words`: written-out quantities inventory as digits
    ("sixteen tokens" → 16). "one" deliberately excluded (article-like).
  - Conditional-adjunct guard: cue-led clauses (`if/when/unless/under/...`)
    tier-matched (full/partial/lost → pass/review/block).
  - Parallel-sentence subject guard: sentences sharing one non-auxiliary verb
    across distinct subjects ("Performance asks ... Quality asks ...") protect
    each subject; dropping one blocks.
- Tests: `test_expository_stage_a.py` (status/severity separation, escalation
  rules, fence/quote handling), `test_expository_preservation.py` (I2 classes:
  lost mean/units/values/assumptions/certainty promotion/references/truncation,
  code/Hugo preservation, clean reorder passes, one→a non-loss pinned).

### Workbench (`C:\Projects\workbench`)

- `writer/patterns.py`: per-type review tracking (`confirmed` / `mechanical` /
  `unknown` from finding stats); mechanical-only EXPO capped at medium level;
  items carry `review_status` (`confirmed` | `needs_ai_review` | `n/a`);
  `instruction()` states MECHANICALLY_FLAGGED vs SEMANTICALLY_CONFIRMED;
  `LEAVE_REASONS` vocabulary (false_positive, necessary_complexity,
  intentional_structure, unhelpful_revision, technical_regression,
  accepted_improvement, deferred, no_reason_given); dismissed counts include
  `dismissed_reasons`.
- `service.py` `leave_pattern(sha, reason=None)`: validates reason, stores it
  with the dismissal (persisted, revision-bound like before).
- `app.py`: `POST .../leave` accepts optional `{"reason"}` (400 on unknown).
- `static/index.html`: reason `<select>` per marker; Review vs Fix button label
  by review status (same composer action — Review routes a mechanical candidate
  into the existing Fix flow, nothing inert added); `[Needs AI review]` /
  `[Confirmed]` badges in marker and drawer list.
- Tests: mechanical cap + status, confirmed status, reason validation/storage/
  counting/persistence, HTTP reason + 400 on unknown.

### Mission Control (`C:\Projects\mission`)

- `artifact_load/service.py`:
  - `cluster_regions(..., weight_field="severity"|"priority")`; UNASSESSED never
    coerced to LOW (weight 0 under severity mode).
  - `compute_load`: mechanical pressure weighted by review priority with legacy
    severity fallback; confirmed load unchanged (severity-weighted).
  - `assessment_state()`: not_assessed (no record or 0% semantic) /
    partially_assessed / assessed_clean / assessed_findings / stale / running /
    blocked_failed, derived at read time under `assessment-policy-v1`
    (full semantic coverage required for assessed). History untouched.
  - Workspace marks superseded revisions stale.
- `schemas.py` / `api/artifact_load.py`: `assessment_state` +
  `assessment_policy` on reads; stale override in workspace.
- `ArtifactLoadFinding` defaults updated (severity UNASSESSED, priority LOW).
- Frontend (`ProjectPage.tsx`, `api.ts`): Artifact Load map joins discovery so
  all chapters render; columns Pressure / Load / Confirmed / High / Unrev /
  Coverage M/S / Assessment; unassessed rows show em-dashes with a
  Not assessed badge (never a healthy zero); sort unassessed-first default.
- Tests: assessment states (all branches), stale override, priority weighting,
  legacy fallback, Not assessed frontend rendering.

## B. Semantic execution report

- Route: `opencode-go/deepseek-v4.1-flash` via the installed OpenCode CLI
  (`shutil.which("opencode")` → npm install), requested == actual
  (`route_resolution: configured`), temperature 0.0, per-call timeout 300 s.
- Transport: prompts travel by `--file` temp file (Stage B finding — argv
  transport breaks on the template's `|`/quote characters: cmd.exe split the
  command line; file transport is the same path manuscript_cli uses).
- No new gateway: thin `OpenCodeModelRunner`/`ExpoPromptBuilder` adapters call
  the detector's own `run(... execution_mode="llm")` end to end, blind
  (no prior rule scores passed).
- Prompt version: `expo-sem-v1+<sha8 of template+builder>` recorded per call;
  detector `expo-v1`; requested/actual model, latency, token usage, transport,
  raw response preserved per call in `scripts/expo02/cache/`.
- Semantic-only runs use llm mode without prior results (blind per C4-B).
  Hybrid (C4-C) = rule screening ∩ semantic confirmation (same calls, no extra
  model cost), plus the implemented spot-check escalation path.
- Budgets: `--max-calls` (default 200), resume-from-cache, failures recorded
  as PROVIDER_ERROR rows (never fabricated). No fallback provider.

## C. Calibration report

Dataset: `scripts/expo02/passages.jsonl` (46 passages) + `labels.json`.

- Sampling frame: all 1-para + adjacent 2-para explanatory units (≥40 words,
  protected material excluded) from Inference 01/39/43 → 9 flagged units taken
  directly; 43 unflagged units as the random frame (seed 42 → 10 sampled);
  top-7 near-miss unflagged by pressure (purposive) — C2 false-negative probe
  with recorded frame, seed and rationale.
- Author-nominated Ch01 opening included as P01 (label assigned by review, not
  assumed defective).
- Language: 6 as-found + 6 revised-candidate paragraphs (revised samples turned
  out byte-identical to as-found for the sampled units — documented, no
  revision effect observable there).
- Synthetic controls: 5 NO_ISSUE + 2 vacuous UNCERTAIN + 1 INTERRUPTION.
- Labels: provisional single-reviewer (implementer) throughout; language labels
  likewise provisional; synthetic by construction. No human ground truth
  claimed; no thresholds retuned (C2 — thresholds 5.0/2.5 frozen during this
  stage).

(RESULTS FINAL — sweep complete 46/46, 0 missing, 0 invalid, 0 provider errors.
Model: `opencode-go/deepseek-v4.1-flash`, temperature 0.0, prompt
`expo-sem-v1+d40fa9e4`. 40 unique texts (6 byte-identical language duplicates
share evaluations, relabeled per passage). ~128k input tokens; mean 32 s/call,
max 170 s. Full table: `scripts/expo02/calibration_report.md`.)

| Approach | n | TP | FP | FN | TN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| deterministic-only | 37 | 3 | 4 | 5 | 25 | 0.429 | 0.375 |
| semantic-only | 37 | 1 | 2 | 7 | 27 | 0.333 | 0.125 |
| hybrid (flag ∩ semantic) | 37 | 0 | 0 | 8 | 29 | — | 0.0 |

(UNCERTAIN excluded throughout: P07, P08, P21, P24, P26, P29, P35, P44, P45.)

- Deterministic FP (flagged, provisionally clean): P04, P05, P06, P09 —
  thesis/inventory/roadmap prose the rule scores as compression.
- Deterministic FN (missed, provisionally positive): P16, P23, P30, P36, P46.
- Semantic FP (confirmed, provisionally clean): P31, P37 (metrics-list,
  model says mild compression; reviewer says clean taxonomy — retained
  disagreement).
- Semantic FN (rejected, provisionally positive): P01, P02, P03, P16, P23,
  P30, P36 — the model rejects every Inference-book positive including the
  author-nominated opening (scores 0.07–0.10, confidence 0.82–0.90).
- Rule–semantic agreement: 27/37. Rule-positive rate 7/37; semantic-positive
  rate 3/37 (P31, P37 LOW COMP; P46 HIGH INTERRUPTION synthetic).
- Hybrid blind spot (semantic-positive but rule-negative, reachable only via
  sampling): P31, P37, P46 — quantifies why spot-checks are mandatory.
- No INVALID_EVIDENCE in the final run (prompt hardening + fence stripping
  worked; the pre-hardening probe had 2 quote-format invalids, now fixed and
  covered by unit tests).
- Subtypes: EXPO_INTERRUPTION confirmed only on synthetic P46 → remains
  experimental on real prose. EXPO_COMPRESSION confirmed only at LOW
  (P24 disputed, P31/P37 disputed) → MED/HIGH confirmation thresholds
  unvalidated. NO_ISSUE correctly returned on 27/27 provisional-clean
  adjudicated passages.

Interpretation (C6): the deterministic screen over-flags structured
thesis/inventory prose and misses dense enumerations; the semantic reviewer is
lenient on real book prose (confirms only LOWs) while precise on blatant cases
(P46 HIGH with an exact, actionable diagnosis). Neither direction is declared
correct — provisional labels are single-reviewer. What IS established: the two
detectors disagree most on the motivating passage itself (rule MIXED/flagged,
model NO_ISSUE), so the detector does not reliably identify the problem that
started this work. Both subtypes stay experimental for confirmed defects; no
threshold retuning performed.

### C5. Repeatability

Subset P01 (disputed), P04 (deterministic FP), P25 (necessary complexity),
P27 (clean), P30 (provisional COMP), P46 (blatant INTERRUPTION) × 3 runs,
same model + prompt version, temperature 0.0: verdicts identical in all
18 runs (P46 EXPO_INTERRUPTION/HIGH every time, scores 0.87–0.92; the rest
NO_ISSUE every time). Verdict-level stability is perfect on this subset;
score magnitudes vary slightly. Disagreement is preserved across runs (P30
stays NO_ISSUE against a COMP provisional label in all 4 evaluations).

### Acceptance criteria (commission §17)

1. Mechanical vs confirmed distinguished — Writer UNASSESSED+priority,
   Mission weighting/assessment, Workbench review_status. ✓
2. Unassessed chapters show Not assessed — frontend map + tests. ✓
3. Real Pi semantic analysis — 46 + 18 + 6 live calls, raw responses kept. ✓
4. Ch01 opening explicitly evaluated (4× NO_ISSUE + provisional MIXED
   disagreement retained). ✓
5. Deterministic FNs examined (P16, P23, P30, P36, P46 + random frame). ✓
6. FPs examined (P04, P05, P06, P09). ✓
7. Both subtypes have calibration evidence: INTERRUPTION confirmed only
   synthetic (experimental on real prose); COMPRESSION confirmed only LOW
   (MED/HIGH unvalidated). ✓ (as documented experimental status)
8. Quote verified before confirmation (exact-match; 0 invalid in final run;
   2 pre-hardening invalids drove the parser fix). ✓
9. Writer persists real semantic findings with provenance (cache rows with
   model/prompt/latency/usage/transport + Mission observations). ✓
10. Workbench presents findings through the existing Artifact workflow
    (mechanical live; confirmed states code-complete, no live source yet —
    explicit gap). Partial: display ✓, live confirmed ✗ (EXPO-03 item 2).
11. Genuine multi-paragraph repair candidate (P24, full unit). ✓
12. Independent semantic + preservation review (blind A/B + gate). ✓
13. Separate mechanical pressure and confirmed load in Mission Control. ✓
14. Coverage/uncertainty explicit (partial everywhere; stale override). ✓
15. Before/after gaming guards (denominator flag, region dedup; tests). ✓
16. Prose scores and publication states unchanged (53 tests green). ✓
17. Tests + integration acceptance reported (here + suites). ✓
18. No canonical chapters rewritten (hashes frozen; candidates isolated). ✓

Criterion 10 is the one partial item: confirmed-finding display is
implemented and unit-tested but has no live Writer source, since
`/api/artifacts/observe` is deterministic by design. Everything else is met
as far as a provisional-label calibration can meet it; accuracy claims are
explicitly withheld pending independent adjudication (EXPO-03 item 1).

## D. Chapter 01 diagnosis

**Did the original deterministic detector identify the motivating opening
passage?** Mechanically, yes: P01 flags as EXPO_COMPRESSION (5.55/1.65) and
the wider L16-18 unit as MIXED (12.75/4.85). But mechanical flagging is not
identification of a genuine obstruction (Stage A2).

Semantic review rejects every Chapter 01 unit (P01–P09, P10–P22 samples: all
NO_ISSUE, including 3 independent calls on P01 for repeatability): the caveat
follows the claim it limits, the three observations are parallel-enough,
difficulty is substantive rather than structural. Provisional human review
disagrees on P01–P03 (MIXED/COMPRESSION — 4 explanatory jobs before the
central result lands) and agrees on P04–P06, P09 (clean). The disagreement is
retained, not resolved: the passage is genuinely hard to adjudicate, which is
itself evidence that single-reviewer labels cannot ground accuracy claims.

Consequence for Stage F: no Chapter 01 confirmed finding exists, so per the
commission the repair uses another evidence-backed passage (P24, Ch39,
confirmed COMP/LOW) with this rationale recorded.

## E–J.

### E. Real pilot findings (Stage D)

Persisted via `scripts/expo02/persist_observations.py --confirm` (rule: live
`ArtifactEngine(profile=technical)`; semantic: rep-0 sweep rows; quotes
re-validated against chapter text; mechanical candidates on semantically
reviewed spans superseded and counted as rejected, not deleted silently).

| Chapter | Revision | Words | Units | Sem coverage | Confirmed | Unreviewed | Mech pressure | Load | Assessment |
|---|---|---|---|---|---|---|---|---|---|
| 01 | d146580f | 3175 | 64 | 0.422 | 0 | 1 | 0.315 | 0.0 | partially_assessed |
| 39 | b6958b3e | 5345 | 80 | 0.087 | 1 (P24 LOW) | 5 | 2.245 | 0.187 | partially_assessed |
| 43 | f0623a3f | 3845 | 59 | 0.153 | 0 | 5 | 3.121 | 0.0 | partially_assessed |

No INVALID_EVIDENCE, no provider errors. Every chapter reports partial
coverage — no clean verdicts anywhere. Canonical manuscripts byte-identical
before/after (frozen hashes recorded in each observation).

### F. Controlled repair (P24, Ch39 — rationale in section D)

- Freeze: `scripts/expo02/repair_P24_freeze.json` (text L161, sha, rule +
  semantic provenance).
- Ledger (model-extracted, cached): 1 claim, conditions, caveats, 7 technical
  terms, no invented items (`cache/repair_P24_ledger.json`).
- Plan: 5-step ordering rationale — simple unconditional items first,
  conditional + parenthetical alternative nested under item 3, status line
  stays closing (`cache/repair_P24_plan.json`).
- Candidate (REORDER_EXPLANATION strategy instructions from the real
  `ArtifactRepairStrategyService`, `reorder_explanation`): 3-item numbered
  list + closing status line; all code spans preserved
  (`cache/repair_P24_candidate.json`, 352 chars).
- Preservation gate: `check_semantic_loss` PASSED, risk low — including the
  median/mean/unit guards (no statistics in this unit; code-span and
  condition inventories retained).
- Rule pressure: [] before → [] after (unit is sub-threshold; no mechanical
  delta claimed — improvement is structural, not metric).
- Blind A/B (separate context, randomized X=candidate/Y=original):
  candidate judged clearer (score 0.25), `preserved: true`,
  `lost_or_changed: []`, comprehension 3/3 match
  (`cache/repair_P24_compare.json`).
- Disposition: **IMPROVED** (bounded to this unit; LOW-severity original;
  mild blind preference + full comprehension match + gate passed).
- Canonical chapter untouched; isolated candidate + review package only.
  Apply requires existing Workbench authorization.

### G. Workbench evidence

Mechanical EXPO findings flow through the existing deterministic scan today
with the new display (status/priority labels, medium cap, Review vs Fix,
rejection reasons) — covered by `tests/test_patterns.py` (14 pass) against
realistic Writer issue shapes. Semantic-confirmed display states are
implemented and unit-tested, but no live Writer route serves semantic
findings through `/api/artifacts/observe` yet (that route is deterministic by
design), so confirmed badges are code-complete, not live-demonstrated.
Recorded as an explicit integration gap for EXPO-03.

### H. Mission Control evidence

Three CURRENT observations persisted (IDs verifiable via
`GET /api/artifact-load/observations?project_id=inference`):
01 → partially_assessed / load 0.0 / pressure 0.315;
39 → partially_assessed / load 0.187 / pressure 2.245 / 1 confirmed (P24);
43 → partially_assessed / load 0.0 / pressure 3.121.
`GET /api/artifact-load/compare` available for before/after with denominator
warnings; history append-only (stale override verified by test).
Frontend Artifact Load map shows all chapters with Not assessed rows for
unevaluated work — prose scores untouched (53 quality/writer tests green).

### I. Test report

- Writer: `tests/runtime/artifact` 273 pass (incl. new EXPO-02: status/
  severity separation, escalation, fence/quote handling, I2 preservation
  classes, median guard). Artifact web/CLI suites 34 pass.
- Mission: 22 artifact-load tests (assessment, priority, stale, legacy
  fallback), 53 quality/writer/adapter tests, frontend 59 tests — all green.
  Full backend suite: 272 passed, 1 skipped, 1 failed
  (`test_configured_editor_opens_the_registered_repository`) — pre-existing,
  traced to another workstream's uncommitted settings change; unrelated files.
- Live acceptance: 46 semantic calls + 18 repeat calls + 6 repair calls, all
  recorded with raw responses, usage, latency, transport (no mocks in the
  evidence chain).
- Unresolved blockers: none for the reported scope; semantic leniency and the
  Workbench confirmed-findings route are open questions, not blockers.

### J. Recommended EXPO-03 (not implemented here)

1. Independent human adjudication of the 46-passage set (the single-reviewer
   provisional labels are the weakest link in every number above).
2. A Writer route (or report channel) serving SEMANTICALLY_CONFIRMED findings
   to Workbench so confirmed badges go live.
3. Enlarged spot-check sampling to shrink the hybrid blind spot before any
   full-book semantic campaign; keep the 45-chapter campaign out of scope
   until (1) exists.
