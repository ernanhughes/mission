# W7-PROPOSAL-CONTRACT — Minimum domain, maximum linkage

Table `wo_proposals` (§8 fields, all present): identity, originating
finding ids (join table, never moved), group id, episode id,
requirement ids + versions (via findings + confirmations), project key,
action category (closed set, validated), objective, scope, exclusions,
acceptance criteria, required verification, suggested route, cost
constraints, risk, status, version, scope_hash, closure_status.
No duplicate persistence: findings/requirements/episodes stay canonical;
the proposal references them. Events (`wo_proposal_events`) and
executions (`wo_execution_links`) are append-only side tables.

## State machine (enforced server-side, tested)

draft → ready_for_review → approved → queued → running →
reported_complete → verification_pending → verified_resolved;
rejected/deferred/failed/cancelled at the documented gates (§10).
Terminal: verified_resolved, cancelled (immutable). Illegal
transitions rejected; approval gates require confirm=True;
approve additionally requires a human actor and a matching
(version, scope_hash) — scope edits after ready_for_review bump
version, void approval, and return the proposal to draft.

Duplicate prevention: same open proposal for the same finding set →
`duplicate` with the existing id (tested). No proposal may authorize
itself: opening, previewing, or copying never transitions state.
