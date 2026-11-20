# MC-PRAXIS-09 — Preflight, resource resolution and test ownership

This contract extends MC-PRAXIS-07 without changing execution authority.
Preflight is **advisory**; the authoritative validation layer still decides
whether a proposal may be approved or executed.

## Preflight (`praxis_proposals/preflight.py`)

Computed from authoritative Mission Control data (execution records,
application configuration, registered resources) at import and refreshed on
every proposal read. Findings are typed:

`id · severity · capability_id · message · evidence · observed_at ·
environment_ref · remediation · confidence · blocking · advisory`

- `blocking` is always `false`: a preflight finding never blocks approval.
- Historical timeout text is parsed to report the configuration at the time of
  failure (`historical timeout 60s`) separately from the current timeout.
- Runtime evidence reports n/min/max of observed executions and compares the
  maximum with the current timeout (`timeout_risk`, `timeout_margin_thin`,
  `runtime_within_timeout`).
- Book resources are restated (`book_resolved`) and checked against the
  authoritative `project_root`.

## Resource resolution

The Writer adapter already stores each book's authoritative `project_root`.
`GET /api/integrations/writer/resources` now includes `project_root` in the
list preview so callers do not need one request per book.

Proposal import validates:
`book_registered` (resource exists), `book_root_known` (resource has a root),
`book_root_resolved` (supplied `book_root` equals the authoritative root).
Unknown or mismatched resources are authoritative validation errors.

## Approval presentation

`GET /api/praxis/proposals/{key}` and the evidence response include current
preflight findings, resolved capability metadata (risk, side effect, approval
requirement, enabled), and the stored execution configuration. Approval remains
bound to the immutable content digest; preflight is not part of the digest.
Refresh policy: preflight is recomputed on read; a material action or parameter
change still requires a new proposal version and a new approval.

## Ownership and test hygiene

Import accepts an optional `ownership: {kind: "operator"|"test", owner}`.
`POST /api/praxis/proposals/{key}/withdraw` sets `status: withdrawn` only for
test-owned proposals in a pre-execution state, with a matching owner and a
reason. Operator proposals are never withdrawable; rows are never deleted.

## Execution provenance

At execution request, MC captures `execution_config_json`:
capability id, adapter protocol version, `timeout_seconds`, captured time.
Historical proposals predating this feature show `{}` and remain readable.

## Migration

`034_praxis_preflight.sql` — additive columns; schema version 34.
