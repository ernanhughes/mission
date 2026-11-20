# MC-PRAXIS-10 — Governed single-book Writer audit

Adds one ActionSpec, `writer.audit_registered_book`, so Mission Control can run
Writer's existing `editing audit <project>` for a single registered book under
the same governance as other actions.

## Contract

- Parameters: `book_id` (required, registered book identifier), `profile`
  (enum `technical-nonfiction-v1`).
- `book_id` format is validated (`^[a-z0-9][a-z0-9._-]{0,127}$`); Mission
  Control additionally requires an existing `writer_editing_book` integration
  resource before execution, and rejects a resource whose `source_version` is
  not `writer-editing-summary-v1` (stale registration).
- Risk: `bounded_local_computation`; side effect: `local_generated_artifacts`
  (Writer writes its own report under `.writer/editing`); no manuscript edit.
- Approval required; the existing confirmation and single-flight rules apply.
- Execution runs `writer editing audit <book_id> --profile <profile> --json`
  with the configured timeout and returns a typed result:
  `schema_version=writer-editing-report-v1`, `book_id`, `title`, `report_id`,
  `partial`, `finding_counts` by severity, up to 200 findings, limitations,
  generated_at, artifact reference.

## Why it is safe

Writer's audit is read-only with respect to manuscripts and repository source;
it emits report artifacts only. Unknown or malformed book identifiers fail
before execution. No arbitrary filesystem path is accepted.

## Tests

`backend/tests/test_writer_scoped_audit.py`: ActionSpec exposure, typed report
parsing (mocked runner), identifier rejection, typed failure and timeout,
unregistered-book rejection through the execution API, stale-resource rejection
at execution and during proposal validation, and governed proposal validation
with resource resolution and preflight.
