# W6D-GOVERNED-EVALUATION — Two paths, hard budgets

Path A (deterministic, always available): observation → recon →
staleness → queue → evaluation → grouping. Zero model dependency;
outages elsewhere never block it. Enforced by construction
(`semantic=False` default in manual controls; `allow_semantic` flag in
`run_pass`).

Path B (semantic, doubly gated): runs only when (1) explicitly enabled
AND (2) a governed free route responds AND (3) call/dollar budget
remains (30 calls / $2 eval caps; 20 / $1 extraction caps).
Paid-inference budget for automatic evaluation: **$0 and unwirable from
any UI or API in this stage** (`get_auto` reports it; no setter exists).

Model operation rules (standing): capability gates (0.5b barred),
structured-output validation (tightened in W6A), source minimization +
redaction (existing sanitizer), bounded inputs/timeouts, digest
cache-hit reuse, explicit abstention, provider-failure-as-blocked.
Vacuous/echoed/unsupported output is quarantined as rejections, never
persisted as findings. No repository changes are possible on any path
(read-only git plumbing + read-only source).

Selection (§18): substantive/changed/consequential work first; probe
pings and machine-generated scoring batches are never auto-queued
(triage-gated); unchanged inputs are never re-evaluated (digest cache).
