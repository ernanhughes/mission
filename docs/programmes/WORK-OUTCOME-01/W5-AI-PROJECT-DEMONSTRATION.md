# W5-AI-PROJECT-DEMONSTRATION — Real pilot records in the interface

Backend: scratch `w4_pilot3` (31 episodes, 26 task objectives, 51 verified
claims, 2 findings, 5 assessments) served by an unmodified backend pointed
at it via `MC_DSN`. No production data touched; no synthetic records —
every number below comes from the W1–W4 pipeline over real ai history.

Demonstrated (screenshots on file: w5-overview/ episodes/outstanding/
coverage.png):

- Overview: 31 episodes, 0 complete-verified, 2 need attention
  (AI-CORE-08C, AI-CORE-05 — each with 1 mandatory open finding), 27
  unevaluated. The brief's target table shape, with honest unknowns.
- Work Episodes: filterable list incl. the 126-session unresolved bucket
  shown as Unresolved + Conditionally accepted (not hidden, not failed).
- Episode detail: 6 tabs (Summary/Requirements/Changes/Evidence/Evaluation/
  History) verified rendering; requirements show authority + verdict;
  claims show verification state; evaluation shows three perspectives.
- Outstanding Work: 2 verification gaps with next actions
  ("supply verification evidence"), mandatory-first ordering.
- Quality: per-episode execution/outcome tags, no composite scores.
- Coverage: 31/4/27 episodes, 5 requirements assessed, 51 claims verified,
  triage mix (23/90/10/26), consistent denominators.

Limitations (explicit, not hidden): no `complete` exemplar exists in the
pilot (none was independently verified end-to-end); semantic evaluations
are conditional (small local model); independent review is pending; the
demonstration database is a scratch copy, not operational `mc`.
