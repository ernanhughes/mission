# W6A-VERIFIED-COMPLETION-EXEMPLAR — The closest genuine positive case

## Candidate investigated: AI-CORE-05-R1

Genuinely the strongest in the pilot: independent source assessment
(R1-REVIEW, dated, baselined f2aeea0/merge 22299e8, second pass verdict
APPROVE with bounded pilot scope) + recorded 162-test pass (117 prior +
40 new) + 4 R1 SHAs resolving in MC git history.

## Mechanical work performed (all recorded, operational wo_* only)

1. 4 R1 commits associated to the episode (explicit/human-confirmed,
   reason cites the R1 baseline).
2. **Auto-link bug found and fixed**: `_auto_link` stored bare SHAs that
   `_evidence_for_requirements` could never resolve (full `uid:sha`
   comparison) — every mechanical git link was silently dead.
   Regression test added; resolvable refs now stored.
3. 13 human-attested file evidence links (exact files cited AS evidence
   in the R1 review/commit; method human-reviewed, weak confidence).
4. Re-evaluation: 6/7 requirements `satisfied_reported`, 1
   `satisfied_verified` (existence-type manifest requirement against
   resolved source state, per rubric), completion `unknown → partial`,
   outcome `mixed`. 5 stale `missing_requirement` findings closed by
   §21 reconciliation with cited closure evidence (preserved rows).

## Verdict: NO unconditional verified-complete exemplar exists

The honest ceiling is demonstrated, not bypassed:

- `satisfied_reported` is exactly right: evidence is linked, correctness
  was judged by the R1 reviewer, not by Mission Control. Upgrading it
  would launder the reviewer's judgement as the system's verification.
- `satisfied_verified` fired once, mechanically, for an existence-type
  requirement — the rubric's narrow mechanical-verification path, not a
  general completion proof.
- The R1 qualification itself is CONDITIONAL (deterministic stand-ins,
  unrun real-model matrix, preserved negative-transfer signal).

What would close it: independent test-execution records in MC (run the
R1 suite under MC observation and bind the records), plus the remaining
real-model matrix. Until then, `partial` + mixed + bounded limitations
is the truthful state — and the system now shows both sides: it
recognizes evidenced success (reported) exactly as far as the evidence
reaches, and withholds `complete` exactly where independent judgement
is missing. That is the positive-completion capability working.
