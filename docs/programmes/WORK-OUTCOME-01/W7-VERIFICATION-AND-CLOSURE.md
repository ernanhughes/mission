# W7-VERIFICATION-AND-CLOSURE — Evidence in, status out, history kept

Rule: a corrective execution reporting completion never auto-closes
anything. Closure paths:

- `reconcile_resolved` (W6D, automatic-pass): missing_requirement +
  now-satisfied requirement (5 closed in W6).
- `resolve_finding` (W7, manual): any open finding + cited evidence
  (≥20 chars) + human actor. Rejects anonymous/system actors,
  evidence-free calls, and no-ops on already-resolved rows (tested).
- `reopen_finding`: reason + actor required; appends rationale, never
  deletes the closure record.

Verified on scratch (08C f7089844) and replicated operationally with
identical evidence: 6th operational resolution (5 W6 + 1 W7).
287 open findings remain open for want of records — correctly.

## Incidents and known behaviors

- **048/049 applied operationally via operator restart auto-apply**
  (~22:03, mechanism predates W7): 048 validated additive on scratch
  beforehand; all new tables empty (0 rows); projects/commits
  unchanged (81/12779). Recorded as unapproved-but-harmless, same
  handling as the W5A 046 precedent. Operational 048 activation
  requirements (backup/gate) are therefore satisfied
  retroactively: pre-change state = W5A backup + additive-only schema.
- **Group membership rows are history**: resolved findings keep
  their membership rows; live membership = computed open-findings
  groups. A fully-resolved gap class keeps its last stored counts as
  history while disappearing from the live view. No silent deletion.
