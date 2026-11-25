# W6-ASSURANCE-RECONCILIATION — Outstanding obligations, collection status

Source: W5A-INDEPENDENT-REVIEW-STATUS + W4/W5/W5A finals, re-checked 2026-11-24.
No new review artifacts found in docs/programmes/WORK-OUTCOME-01 since W5A.

## 1. Cross-family independent review (W1–W4, extended W1–W5)

- Status: OUTSTANDING. No cross-family reviewer has examined the
  implementation. External commission (W2-INDEPENDENT-REVIEW, extended
  W3/W4) stands. This W6 stage does not substitute: all W6 positive
  completion judgments remain conditional on this obligation.
- Collection attempt: none available in-repo; recorded as carried into
  W6-FINAL-REPORT. No indefinite postponement: W6E will re-check once.

## 2. Separate-agent re-verification — 8 W4 fixes

- Status at W5A close: commissioned and running, result pending.
- Collection attempt this stage: no result artifact present in
  docs/programmes/WORK-OUTCOME-01 (searched W4-* and W5A-*).
  Recorded as still pending; W6 implementation preserves the fixed code
  paths and adds regression tests rather than re-arguing the fixes.
- Critical-defect screen (own verification, §2): ran focused suites
  `test_work_evaluate` + `test_work_extract` (53 passed) and frontend
  `WorkEvaluation.test.tsx` (9 passed) — no false-completion, security,
  data-integrity or privacy defects observed. Full-suite environmental
  failures (if any) will be reported, not hidden.

## 3. Separate-agent re-verification — 4 W5 fixes

- Status: pending with same agent (1 consistency gap + 3 lows, all fixed
  in code and covered by the 9-test frontend suite).
- Collection: no artifact in-repo; carried. The 9 UI tests (incl.
  zero-POST assertion) were re-run green in W6 entry.

## 4. Model policy for any W6 semantic work

- DeepSeek `deepseek-v4.1-flash-free` (fallback `deepseek-v4.1-flash`),
  Codex `gpt-6-luna`, Claude `claude-haiku-5-5` where justified, Muse
  primary implementation. No paid calls authorized for automatic
  evaluation (default budget $0). Loopback Ollama `mistral-small:latest`
  is the bounded pilot route; qwen2.5:0.5b barred from judgements.
- An independent agent of the same model family does not satisfy
  cross-family review (§2 acknowledged).

## 5. Conditional-acceptance preservation

Every evaluation the UI presents that depends on unreconciled reviews is
either deterministic (mechanical, tested) or explicitly marked
conditional/unevaluated. W6B severity reform and W6A positive-completion
work must not upgrade any verdict beyond what evidence supports, and must
not present machine output as independently verified.
