# MC-PRAXIS-11 — Scoped-audit provenance and preflight correctness

PRAXIS-11 made two minimal Mission Control changes justified by the governed
scoped-audit pilot.

## 1. Typed provenance on the scoped audit result

`writer.audit_registered_book` now returns, in addition to the existing typed
fields:

- `profile`
- `canonical_fingerprint`
- `scope`
- `source_revision`
- `source_dirty`
- `findings_total`

These come directly from Writer's `writer-editing-report-v1`; they are not
recomputed by Mission Control. They let Praxis compare a governed result with a
direct Writer audit on content identity rather than only severity counts.
`findings` remains capped at 200, while `findings_total` and
`finding_counts` cover the full report.

## 2. No-`book_root` preflight advisory

The `book_resolved` preflight finding previously described a missing
`book_root` parameter as "supplied book_root differs", producing a warning when
no root was supplied. It now reports an `info` finding that MC uses the
registered root, and only reports a mismatch when a root was actually supplied.
This is advisory only; authoritative validation remains in the proposal service
and execution gate.

## 3. Pilot state

Proposal `prop-1795219304-3110bda8@1` (correlation
`mcprop-bab982517b7547ba`) was imported with all 21 validation checks passing.
It is `awaiting_approval`; no approval was simulated and no Work executed. The
imported preflight snapshot predates the no-`book_root` fix, so its
`book_resolved` finding remains a warning in that immutable record.

## Tests

`backend/tests/test_writer_scoped_audit.py` and
`backend/tests/test_praxis_proposals.py`: **30 passed**. New assertions cover
the provenance fields and the no-root info advisory. Existing scoped-action,
stale-resource, proposal, preflight and approval-binding tests remain green.
