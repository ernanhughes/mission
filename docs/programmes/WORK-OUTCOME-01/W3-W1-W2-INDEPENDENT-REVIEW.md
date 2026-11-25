# W3-W1-W2-INDEPENDENT-REVIEW — Separate-agent review, conditions applied

## What was obtained

A separate-agent review (different session, same model family `muse-spark` —
explicitly NOT cross-family independent) executed 74/74 focused tests green,
verified read-only guarantees, parser tolerance, migration semantics and
privacy handling by reading code and running probes, and returned
**CONDITIONAL** with 5 majors + 10 minors.

## Disposition (all 5 majors fixed in code, not docs)

- M1 task-id false positives (HTTP-500/CVE → junk episodes): deny-list
  extended + corroboration rule (explicit needs ≥2 sessions or co-occurring
  sha/file/chain; lone mentions → candidate/weak). New tests.
- M2 short-hex coincidence: <40-hex SHAs need session corroboration, else
  `short-sha-uncorroborated` rejection. New tests.
- M3 single-generic-file → moderate: capped at weak; moderate needs ≥2
  distinctive files + temporal support. New test.
- M4 `valid=0` never written: superseded episodes now retire their links.
- M5 rejected markers not persisted: attached to the unresolved bucket;
  audit possible from PG.
- Minors: M6 parts fetch → count query; M7 truncation loss stated in
  coverage docs; M8 tiebreak wording corrected; M9 version bump made
  conditional; M10 slug-collision bound documented; M11 counts reconciled
  (21 distinctly-homed sessions; multi-episode sessions explain episode
  counts); M12 bucket composition independently rescanned (W3 baseline);
  M13 three missing negative controls added (now 90+ tests); M14 carried
  (no live PG to test against — assertion at next start).

## What remains open (carried, not waived)

Cross-family independent review: the external commission in
W2-INDEPENDENT-REVIEW stands. The separate-agent review shares the
implementer's priors; W3 judgement-adjacent work (requirement drafting)
treats unreviewed-by-third-party semantics as provisional until that
commission executes.
