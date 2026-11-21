# MC-PRAXIS-15 — Bounded technical verification

## Added

- `mission_control.technical.arithmetic_verifier`: exact rational arithmetic
  over a typed proposition language; no eval/import/filesystem access.
- `mission_control.adapters.technical.TechnicalAdapter`: new Technical
  integration with one action, `verify_claim`.
- Technical application registration in `config/defaults/applications.yaml`,
  `INTEGRATION_APPLICATIONS` and the adapter registry. No schema migration.
- `verify_claim` resolves the claim from MC's SQLite store read-only, checks the
  normalized source hash, validates the proposition, runs the bounded verifier
  and writes a local result artifact.

## Contract

- Parameters: `claim_id`, `source_revision`, `method=deterministic`,
  `proposition`, `max_seconds`.
- Risk: `bounded_local_computation`; side effect: `local_generated_artifacts`;
  approval/confirmation required.
- Rejects unknown claims, stale/mismatched source revisions, unsupported
  methods, invalid propositions, extra fields and excessive time.
- Does not trust a client-supplied verdict.
- Does not insert a `technical_verifications` row or change claim status.
- No arbitrary code execution; proposition expressions are allowlisted.

## Freshness

The adapter computes SHA-256 of the current chapter file with CRLF normalized,
and compares it with the claim's `source_revision`. All 1,245 existing claims
fail this check. No live claim execution occurred.

## Tests

- `backend/tests/test_arithmetic_verifier.py`: 7 engineering fixtures.
- `backend/tests/test_technical_verification.py`: 7 action/governance tests.
- Affected suites: **51 passed**.

Covered: exact true/false arithmetic, precision, division by zero, unsupported
operators, oversized inputs, deterministic replay, fidelity separation, fresh
fixture execution, stale/unknown rejection, client verdict rejection,
confirmation required, no claim-status mutation.

## Operational status

The Technical integration is seeded and available after refresh. There was no
fresh authentic claim and no human approval, so live executions remain **0**.
