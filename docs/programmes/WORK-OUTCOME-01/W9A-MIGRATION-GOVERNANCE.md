# W9A-MIGRATION-GOVERNANCE — Procedure, not another system

W8 investigated and recommended: startup banner, approval watermark
with fail-closed default, read-only drift view, one-prefix-per-pair
convention — explicitly no new framework/scheduler. W9 adopts the
procedure half (the part requiring no code):

1. **Pending-migration review is now part of stage entry.**
   Before any activation, list working-tree migration files vs
   `schema_migrations` on the target and record ownership per file
   (workstream prefix in the filename). Done for W9: 050/051 present
   in tree, absent operationally (schema 49); 046/049 belong to
   AITEST; 040 is PG-only legacy.
2. **Authorization is written, not inferred.** Successful application
   (e.g. 048/049 via operator restart) is recorded as *unapproved but
   harmless* (additive, validated first, empty tables, counts held) —
   never relabeled "approved" after the fact. 050/051 remain
   unapplied operationally pending explicit activation approval.
3. **Drift visibility without new infrastructure.** The pending-vs-
   applied comparison above IS the drift view; it is reproduced in
   every activation doc from two read-only queries (file list +
   `schema_migrations`). No endpoint, no daemon, no second runner.
4. **Watermark convention.** The programme ledger's schema-version
   line is the human-readable watermark; any startup log showing a
   higher applied version than the ledger triggers a governance note
   before further operational writes.

The startup-banner and fail-closed watermark *mechanisms* remain
operator decisions (they touch shared startup behavior used by other
workstreams) — proposed, not imposed.

## Live test of the procedure (2026-11-25, during W9)

While W9 was in progress the schema advanced 49 → 51 → 52 without this
commission running a migration. Applying the procedure above:

| Step | Result |
| ---- | ------ |
| List applied | 050, 051 (work-outcome: envelope + linkage), 052, 053, 054 |
| Attribute ownership | 052 `aitest_quality`, 054 `aitest_quality_evidence` (**AITEST-03**); 053 `inspect_runs` (**Inspect**) — different workstreams |
| Approve? | No. Recorded as arrived-via-restart, additive (`CREATE TABLE IF NOT EXISTS`), not programme-approved |
| Data impact | Counts verified unchanged: 31 episodes, 9 requirements, 293 findings, 1 proposal, 81 projects, 12,779 commits |

050 and 051 are the last work-outcome-owned deltas; everything above
them belongs to other workstreams and is recorded as such.The procedure worked as intended: the drift was detected from two
read-only queries, attributed, and recorded instead of being silently
absorbed. This is exactly the failure mode W8 flagged — now with a
documented response. It also confirms the recommendation still stands:
detection without a startup banner requires a human to look, which is
why the mechanism is proposed.
