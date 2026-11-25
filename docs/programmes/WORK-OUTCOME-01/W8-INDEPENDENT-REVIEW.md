# W8-INDEPENDENT-REVIEW — Separate-agent verdict + fixes

Reviewer: separate agent, same model family (explicitly NOT
cross-family; the W1–W5 commission remains the gating obligation).

## Verdict on final code: 10/10 PASS (2 initial FAILs fixed + re-tested)

- Items 1–4, 6–7, 9–10: PASS as reviewed.
- Item 5 (false associations): initially FAIL — `link_execution`
  accepted unvalidated refs. FIXED: every cited ref resolves
  (session→OpenCode `session_v2`, commit→linked assoc or read-only
  `git cat-file -e`, test receipt→AITest receipt, review→GitReview)
  or the call is rejected; docstring made true; regression tests pin
  accept + each reject path.
- Item 8 (cross-repo coupling): initially FAIL — repositories stored
  unvalidated. FIXED: validated against `GitRepository.repo_uid` at
  registration; unknown rejected; free-text only in the manual
  external_ref note field.

## Residual findings (accepted/documented)

- F4 (Major, fixed in code): digest now binds authorization_ref +
  repositories + policy; duplicate collapse respects auth.
- F5 (Minor, accepted): requirement versions live in
  `requirement_refs[{id, v}]` (readable via list API); digest
  recompute detects amendment.
- F6 (Minor, fixed): link `status` constrained to the six-state
  vocabulary.
- F7 (Info, accepted): check-then-insert without unique constraint
  (single-user local app).
- F8 (Info, noted): SQLite `ADD COLUMN` lacks `IF NOT EXISTS`
  (version gate covers).
- F9 (Info, fixed): `actor` param removed from link path
  (attribution lives in proposal events/confirmations).

## Incidental discovery (fixed)

JSON-over-TEXT columns return strings on PG (SQLite deserializes).
`_jl` normalization added at every envelope read + regression test.
Pre-existing W-code mostly slices (safe on both); remaining readers
flagged for W9 audit — recorded, not reworked here.

## Residual obligations (unchanged)

Cross-family review gates unattended operation. No critical
authority, security, data-integrity, or false-completion defects.
Scheduler stays disabled; paid budget $0.
