# W2-CORRELATION-RULES — Narrow, testable, abstaining

- **R1 explicit identifiers** (`task_id_candidate` → task/stage/programme by
  shape; `SES_/MSG_/TEST-/FIXTURE-/EXAMPLE-` rejected as artefacts).
  Programme roots (`WORK-OUTCOME`, `MC-COST`, `MC-CULTIVATION`) and stage
  tokens (`W\d+`) extract as weak candidates — explicit heuristic pending W8
  instrumentation; a bare mention seeds a *candidate* episode, never ownership.
- **R3 commit resolution**: full SHAs checked against the repo-scoped index;
  abbreviated SHAs require a *unique* prefix match (`git cat-file -e`
  semantics); ambiguous prefixes → rejected; absent → `unresolved`
  (cross-repo candidates kept when another repo holds the object — cf. the
  classified Stephanie reference `0ada120a…`; embedding hashes like `49d89821`
  stay invalid references). Mentioned ≠ executed: a SHA string is a candidate
  until the object exists.
- **Repository context**: longest-prefix worktree match, case-normalized,
  worktree-aware; a mentioned repo is not an associated repo without object
  or file evidence.
- **Temporal**: support only (14-day overlap window upgrades file-overlap to
  moderate); never sufficient alone (negative control tested).
- **File overlap**: exact + normalized-path comparison; `COMMON_FILES`
  (README, manifests, lockfiles…) alone never links; ≥2 distinctive files,
  or 1 + temporal support, yields a candidate.
- **Review/correction**: review-tool invocation (`review|cocoder` in tool
  name) + shared task id → `review_of` (candidate). A later correction never
  implies the finding was resolved.
- **Forbidden inferences** (all covered by negative tests): timestamp-only
  links, single-common-file links, correction⇒resolution, child⇒parent
  completion, claim⇒episode.
