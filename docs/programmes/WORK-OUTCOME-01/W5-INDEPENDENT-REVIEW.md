# W5-INDEPENDENT-REVIEW — Conditional, fixes applied in code

Separate-agent review (same model family, not cross-family): CONDITIONAL
with 1 consistency gap + 3 lows, all addressed:

1. Conditional tag missing in Overview needs-attention rows and Quality
   rows → FIXED: both now render `Conditionally accepted` for candidate
   episodes (verified in code + covered by render paths).
2. Bare "No open findings recorded" → FIXED: now reads "No open findings
   recorded … (recorded findings only; absence of a record is not proof of
   completeness)."
3. OutstandingView project filter ignored (backend has no project param) →
   FIXED: client-side scoping via episode project_key map; empty filter =
   all projects (honest default).
4. `mandatory_open` overclaim (any requirement-linked finding counted) →
   FIXED: relabeled "requirement-linked" in the UI; counting semantics
   documented here (mandatory-ness is a requirement property, not visible
   at the finding level without a join).

No blockers. No false-completion, laundering, zero-state, density,
duplication, unbounded-query, or model-invocation issues found; tab
coexistence and read-only navigation reproduced green (9/9 feature tests).
Cross-family review remains outstanding (standing obligation, not waived).
