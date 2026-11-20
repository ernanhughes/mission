# MC-PRAXIS-07 — Governed Praxis proposal contract

Praxis proposes; Mission Control authorises and executes. This contract adds
the smallest machinery needed to import a Praxis advisory proposal, record an
identified human approval against an immutable snapshot, execute it through the
existing `IntegrationService`, and link the authoritative execution record.

## Routes (`/api/praxis/proposals`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/praxis/proposals` | Import (idempotent per proposal id+version) |
| GET | `/api/praxis/proposals` | List |
| GET | `/api/praxis/proposals/{key}` | Read |
| POST | `.../approve` | Human approval; requires `confirm: true` |
| POST | `.../reject` | Human rejection with reason |
| POST | `.../execute` | Execute an approved, digest-matched proposal |
| GET | `.../evidence` | Proposal + authoritative execution + correlation |

There is no route that executes an arbitrary action from a request body.
Execution is reachable only through an approved proposal, and
`IntegrationService.start_action` still applies the ActionSpec's own
confirmation requirement.

## Lifecycle

`imported → awaiting_approval | rejected → approved → execution_requested →
running → succeeded | failed | cancelled`

Imported proposals that fail validation are stored with `status: rejected` and
per-check findings — rejected proposals are preserved, never deleted.

## Immutability and approval

- `content_digest` is computed server-side (canonical JSON).
- Re-importing the same id+version is idempotent only when the digest matches;
  different content is `409 Conflict` (publish a new version).
- Approval records `approved_by`, `approved_at` and `approval_digest`.
  Execution refuses unless `approval_digest == content_digest`.
- `approved_by` values like `pi`, `praxis`, `agent`, `system` are refused:
  a Pi agent or automated system cannot authorise its own proposal.

## Validation on import (authoritative, not client-trusted)

Schema version, single executable step (pilot limit: no typed bindings yet),
capability id `"<app>.<action>"`, application/adapter/action existence,
action enabled, approval requirement preserved, parameters against the
ActionSpec schema plus adapter semantics (e.g. registered CoCoder repo),
no `<placeholder>` values, non-empty acceptance criteria with at least one
`human:`-sourced criterion and explicit provenance.

## Correlation

MC generates `correlation_id = mcprop-<16 hex>` and never trusts a
client-supplied one as authoritative. The evidence response exposes
`correlation_id`, `goal_id`, `proposal_key`, `recipe_digest`, `content_digest`,
`approval_digest`, `approved_by`, `execution_id`, plus an explicit
`evaluation_boundary` stating what MC asserts and what only Praxis may judge.

## Migration

`033_praxis_proposals.sql` — additive table + indexes. Schema version 33.
