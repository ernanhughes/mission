# PUB-08 evaluation — final machine readout (v0.2 repaired instrument + 19-item rerun)

Date: 2026-11-25. Spend to date $0.0703 / $1.00 (all metered_zero since A1/B1).
Worker stopped. No human results. Do NOT close PUB-08 on this record alone.

## What ran
- 134 blinded judge calls ($0.00, 2.05M tokens) + 19-item rerun ($0.00).
- v0.2 type-aware scorer + calibration 86/86 + recovery-procedure 6/6.
- Replay of all 134 through v0.2; rerun of the 19 unassessable-by-v0.1 items
  (held-out F10/F11 items excluded permanently — budget consumed).

## Probe dimension (repaired)
- v0.1 strict containment: 8 scored-incorrect on rerun — ALL 8 adjudicated
  CORRECT by v0.2 (punctuation/case/format artefacts, e.g. F4 comma,
  E2 case, F1 parenthetical). The v0.1 verdicts are superseded, preserved.
- v0.2 final: every assessable probe correct on every text it applies to,
  EXCEPT one genuine finding: T2:F5 — A1 drops the negated-correctness half
  (missing-concept guard, FINAL, carried as A1's known loss alongside the
  dropped 13-word framing sentence).
- 3 items still malformed (T2:F3, T4:F1/F3 — judge fenced JSON with truncated
  previews, unrecoverable) + 3 abstentions stand (T3:C1/C2, T4:C3/C7 rerun
  abstains) + 3 held-out malformed permanently unassessed.
- Consequence: the instrument now discriminates (calibration proves incorrect
  answers still fail), but its coverage is incomplete — reader recovery is
  PARTIALLY assessed (model-reader proxy only), not established.

## Checklist dimension
- C6 honest-record PASS on all four texts (holds).
- C1/C3/C7 flags on T1/T2/T3 ALL quote inherited source prose (verified
  byte- and reflow-insensitively, incl. A1's line-break-joined hedge).
  Per D-PUB-84: INHERITED, not transformation defects. Zero standing
  introduced-claim flags.
- C2/C4/C5 mostly abstain (judge would not produce verbatim quotes) —
  recorded as abstentions, not passes.

## Assists (weak, 1 judge, 5 questions per pair)
- H>O 4/5, H>B1 4/5, A1≈O ties, B1≈A1 ties (run 1); rerun adds
  T1vT4 Q4/Q5 tie, T2vT3:Q2 H-over-A1. Suggestive only: full engineered
  chapter reads best; partial-B does not lift above direct edit.

## Controls
- Deterministic 12/12 + NC7a mapping 10/12 (recorded judge variance on the
  gloss class: introduced vs strengthened — class-boundary noise, deterministic
  mapping stands). NC7b calibration reference holds.

## Dominance (§3.7, no composite)
TRADE-OFF on every pair. No editorial preference is defensible on machine
evidence: integrity favours neither arm cleanly (A1 complete-but-reflowed
with 2 known losses; B1 verify-clean but 2/5 coverage with 3 recorded
failures), readability unmeasured by any qualified instrument, assists
exploratory.

## What this means for the experiment question
- Direct edit (A1, $0.023, one shot): complete chapter, 0 introduced claims,
  2 known losses (dropped sentence + negated-correctness half).
- Engineered pipeline (B, $0.048, 5 packages + reviews + corrections):
  2/5 regions improved and verified, 3/5 failed on quote/byte-true discipline
  with every failure caught by gates.
- The pipeline's demonstrated value-add to date is VERIFICATION (attribution
  + gates caught everything, incl. the judges' own misattributions), not
  generation. This matches the author's simplified-strategy hypothesis
  (direct generation + PUBLICATION verification) and keeps it live.
- Replicate-2: AGAINST (halts fired; allow only after quote-discipline fix +
  estimator recalibration + full 5/5 B).

## Remaining for PUB-08
1. Human blind read (package ready: pub08/human-review/, W/X/Y/Z + form).
2. Replicate-2 decision (against, conditional as above).
3. Evaluator calibration maintenance (v0.2 frozen; held-out discipline holds).
4. Final independent review prompts (Codex/DeepSeek + editorial read as needed).
