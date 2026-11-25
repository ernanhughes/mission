# W9A-POSTGRESQL-SERIALIZATION-AUDIT — TEXT DDL swallows JSON parsing

## Finding

Work Outcome migrations declare JSON-mapped columns as TEXT DDL.
On PostgreSQL, ORM reads of those columns return raw strings
(verified: `requirement_refs`, `evidence_refs` came back `str`);
SQLite deserializes to containers. Every reader that iterates,
indexes, or joins on these values behaves differently per backend —
verified live on scratch (envelope `repositories` iterated
character-by-character, breaking ref resolution).

## Scope audited (all `Wo*` JSON columns)

dicts: WoSignal.provenance, WoReconRun.scope, WoEvalRun.scope.
lists: WoEpisodeAssociation.signals, WoRequirementAssessment/
WoClaimVerification/WoFinding.evidence_refs,
WoWorkEnvelope.{requirement_refs, repositories, originating_findings}.

Pre-existing non-WO models (WorkCheckpoint, WorkflowEvent, …) share
the pattern but are out of W9 scope — flagged, not reworked.

## Fix (shared boundary, not scattered guards)

`SafeJSONList` / `SafeJSONDict` TypeDecorators in models.py:
serialize on write, parse on read, fall back to the empty container
for missing/malformed content (never None, never a string, never an
exception for a wrong-shaped value). Applied to all 10 Wo* columns;
no DDL change (columns stay TEXT), no migration needed. PG-verified:
same rows now read as `list` on both backends. The one-off `_jl`
helper in envelopes.py is retained as defense-in-depth.

Regression: `test_safejson_normalizes_pg_text_to_containers` pins
parse/mismatch/None/invalid handling for both shapes.
