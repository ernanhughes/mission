# PUB-08 evaluation recovery track 1 — probe-scoring repair (v0.2)

Instrument: `probe-scoring-v0.2`. Spend: **$0.00** (0 live dispatches; deterministic replay + synthetic calibration only). No commits/pushes. Frozen inputs unmodified (read-only).

## 1. Reuse-first instrument investigation

- Old rule (`run_eval_judges.score_probe`): casefolded whole-expected-substring containment. Defective on correct paraphrases: F2 morphological variant (matched/match), F4 presentation comma (tokens,/tokens), F5 inserted content words, F11/F12 clause reorder + backticks, E1–E3 marker-free negation — all recorded `incorrect` though semantically correct (development incidents F1/F2/F4 on the public set).
- Reused (read-only): `quantity_units.normalize_quantity_unit` (case-sensitive MB vs mb, plural/hyphen forms) with frozen fallback + equivalence assert; number/number-word inventory, negation-modality markers, case-sensitive identifier inventory spirits from `semantic_loss`; transport-framing-only recovery per `typed_task` laws 2/3/6/7 (fences stripped, content never edited); quote-verbatim discipline from `publication_automation`; disposition mapping from `publication_attribution`.
- Indiscriminate normalization rejected: calibration proves correct variants pass AND wrong-number/unit, lost-negation, altered-modality, case-mismatch, misordered-sequence, missing-concept variants still fail.

## 2. Calibration (synthetic; development set only + synthetic held-out-type cases)

- Probe calibration: **86/86** expected outcomes (incl. 6/6 §9 discrimination fixtures: missing concept / changed number / unsupported conclusion / removed limitation must fail; correct paraphrase / equivalent reformatting must pass).
- Recovery calibration: **6/6** (fenced-valid + bare-valid recover; truncated/invalid/missing-keys refuse).
- Writer equivalence (unit case-sensitivity): MB='MB' vs mb='mb' distinct=True.
- Held-out separation: F7–F12 rules frozen from key types; recorded held-out answers replayed once below with no tuning (any miss recorded as limitation, never tuned).

## 3. Deterministic replay — all 134 recorded responses

- Buckets (disjoint, sum 134): parsed-original **116** / recovered-deterministic **0** / still-malformed **18**.
- Verdicts: exact **21** (old rule also passed) / normalized-equivalent **24** (old failed, v0.2 passes — the repair effect) / genuine-incorrect **1** (v0.2 still fails) / abstentions **19** (checklist deliberate + coerced; never converted) / needs-adjudication **8** / unassessed **0** (nothing converted to pass).
- Per-arm probe coverage+accuracy (v0.2; malformed stay in denominator for coverage):
  - T1 (B1): scored 14/15, malformed 1, v0.2 correct 14/14 (acc 1.0), coverage 0.933
  - T2 (A1): scored 11/15, malformed 4, v0.2 correct 10/11 (acc 0.909), coverage 0.733
  - T3 (H): scored 13/15, malformed 2, v0.2 correct 13/13 (acc 1.0), coverage 0.867
  - T4 (O): scored 8/15, malformed 7, v0.2 correct 8/8 (acc 1.0), coverage 0.533
- Flipped incorrect→correct under v0.2 (repair effect, 24): T1:E1, T1:E2, T1:E3, T1:F11, T1:F12, T1:F2, T1:F4, T1:F5, T2:E2, T2:E3, T2:F12, T2:F2, T2:F4, T3:E1, T3:E2, T3:F1, T3:F11, T3:F12, T3:F4, T3:F5, T4:E1, T4:E3, T4:F12, T4:F2
- Still incorrect under v0.2 (genuine, 1): T2:F5 — T2:F5 answers with the structure half only ("...which enables reliable interfaces") and drops the negated-correctness concept; the instrument correctly still fails an incomplete answer (missing-concept guard against over-permissiveness).

## 4. Structured-response recovery (18 malformed)

- All 18 records carry only pydantic-truncated `input_value` previews (`...` elision) — no unambiguous valid payload survives in the recorded bytes. Recovery correctly REFUSES all 18 (0 recovered-deterministic, 18 still-malformed): 14 probes + T4:C1 + 3 assists (T1vT4:Q4/Q5, T2vT3:Q2). Recovery procedure itself is calibrated (fenced-valid recovers, truncated refuses). No fields invented, no abstentions converted.

## 5. Controls re-run

- Live-judge controls (NC2/NC3/NC7a × 4 labels): recorded dispositions match design **10/12**; deterministic halves re-verified **12/12** (no fixture drift in O; constructed setups confirmed by frozen-file absence); verdict→disposition mapping **12/12** per attribution builder. Judge verdicts reused as recorded — zero re-dispatch.
- Preserved judge variance (NOT a scorer defect; coordinator adjudication, not live rerun): T1:NC7a: live strengthened→strengthened vs design introduced; T4:NC7a: live strengthened→strengthened vs design introduced.
- Deterministic controls (NC1/NC4/NC5/NC6 + NC7b × 4 arms, batch-6): **20/20** dispositions as expected (NC7b introduced/redundant_synthesis subclass on all arms).

## 6. Instrument verdict

**REPAIRED_AND_QUALIFIED** — calibration 86/86, recovery-cal 6/6, controls deterministic 12/12 + mapping 12/12 + deterministic batch-6 20/20, replay 134/134 with no invented fields. Two live-judge NC7a variances (T1/T4 strengthened vs design introduced) are preserved as coordinator adjudication items — they reflect semantic judge variance on a redundant-synthesis fixture, not probe-scorer behavior, and do not change the instrument verdict.

## 7. MINIMAL live rerun set (NOT executed; coordinator runs live)

- Total live items: **22** = 18 still-malformed (14 probes: T1:F1, T2:E1, T2:F1, T2:F11, T2:F3, T3:E3, T3:F2, T4:E2, T4:F1, T4:F10, T4:F11, T4:F3, T4:F4, T4:F5; 1 checklist: T4:C1; 3 assists: T1vT4:assist:Q4, T1vT4:assist:Q5, T2vT3:assist:Q2) + 4 coerced-abstain checklist (verdict without quotable evidence: T3:C1, T3:C2, T4:C3, T4:C7).
- Controls: deterministic halves 12/12 verified, verdict→disposition mapping 12/12, design-match 10/12 with 2 NC7a judge variances (T1/T4) pending coordinator adjudication (no dispatch — re-dispatch cannot resolve semantic judge variance); any future text rerun needs FRESH live control judges (never reuse verdicts). Held-out budget is consumed (1/1) — no further held-out model run is permitted.
- Adjudication total: 8 replay needs-adjudication (4 coerced-abstain + 1 malformed checklist + 3 malformed assists, all inside the 22 live items) + 2 control judge-variance items (no dispatch) = 10 items for the coordinator; unassessed stays 0, nothing converted to pass.
- Genuine-incorrect probe verdicts are final deterministic verdicts, not reruns.

## 8. $0 confirmation + uncertainties

- Live model dispatches in this batch: 0. Metered spend: $0.00. Fakes: none needed (no judge seam re-executed; recorded verdicts reused). Frozen inputs SHA-unchanged (never written).
- Uncertainties preserved: held-out rules validated once on recorded answers only (F7–F12: 6 probes × 4 arms); E-probe affirmation check is sentence-local (cross-sentence scope not modeled); F8 hedge-dropping passes by design (reader probe, not certainty gate); unassessed bucket is 0 and nothing was converted to pass; H identity CONFLICTED carried; blinding partial per blind-pack limitations.
