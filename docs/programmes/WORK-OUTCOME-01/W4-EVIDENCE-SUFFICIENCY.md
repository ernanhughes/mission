# W4-EVIDENCE-SUFFICIENCY — Requirement-specific, provenance-bound

No universal evidence ladder. What suffices depends on the requirement:

- Existence ("file X present") — resolved diff listing showing X.
- Completion claim with SHA — object existence in the episode's repo history.
- Test outcome — execution record against a pinned revision (a report of a
  report is not reproduction; W4 records execution records where found,
  reported-only otherwise).
- Review assertion — a `git_reviews` row for the assessed commits
  (independence judged from reviewer route/identity, never from the title).
- Integration/operational claims — interface/operational demonstration or an
  explicit acceptance record; code presence is not integration evidence
  (the Mission-Control-UI failure class).
- Correction claims — re-verification against the failure mode, not the
  correction commit alone.

Every verification assertion carries source, method, evaluator and revision.
Conflicting evidence is retained (both rows), never silently resolved.
Stale evidence cannot establish current completion: links pin revisions;
re-observation creates new links; supersession retires old ones.

Pilot finding: model assessments correctly abstained with missing-evidence
pointers ("no evidence of a review of file X") where the deterministic
layer agreed — abstention agreement across methods is itself a calibration
signal (W4-CALIBRATION-REPORT).
