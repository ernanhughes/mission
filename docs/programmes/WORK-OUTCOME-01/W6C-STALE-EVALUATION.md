# W6C-STALE-EVALUATION — Freshness that means something

## Model (`wo_eval_state`, one row per episode)

`queue_status`: current | stale | queued | running | blocked | failed |
unevaluated. A fresh assessment clears staleness (wired into
`_execute`); only 6 tracked reasons mark stale
(requirement_changed, new_commit, new_evidence, association_changed,
rubric_changed, review_correction). Anything else is rejected — a new
commit anywhere does NOT stale every evaluation.

## Display

Overview rows now join real state (was hardcoded `stale: false`):
stale badge + reason + queue status in Needs-attention; full
per-episode state in Controls → Freshness; queue in Controls →
Evaluation queue. Operational seed: 3 episodes `current` (W6A
re-evaluated); the rest `unevaluated` until their next manual run —
shown as unevaluated, never as current.

## History preserved

Assessments/findings/runs are append-only; staleness marks only the
pointer row. A stale assessment stays readable with its reason; the
re-evaluation appends, never overwrites.
