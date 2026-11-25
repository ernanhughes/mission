# W3-AI-PROJECT-PILOT — Bounded semantic pilot (19/20 calls, $0.00)

Scope: 10 NEEDS_SEMANTIC sessions + 7 diverse task/chain episodes (scratch
`w3_sem`; ai git snapshot copied read-only; operational DBs untouched).
Backend: loopback `qwen2.5:0.5b`, temperature 0, caps enforced in-service.

## Triage (10 calls)

5 completed, 5 provider_failed (malformed JSON past the fence-tolerant
parser — small-model truncation; rejected safely, nothing persisted).
Completed classifications unanimously `RESEARCH_OR_INVESTIGATION` with
thin reasoning ("file path is not part of the provided information").
Verdict: weak discrimination at this model size — deterministic triage
remains primary; model triage is advisory only. No false `SUBSTANTIVE`
promotions observed.

## Requirement extraction (7 calls)

4 completed, 2 provider_failed (same JSON fragility), 1 rejected by schema
validation (requirements-not-a-list — validator worked as designed).
Persisted requirements are **instruction echoes** ("提取工作需求",
"Extract work requirements from the evidence packet") — schema-valid but
semantically vacuous. Consequence: a deterministic vacuity filter is now
enforced (`is_vacuous` blocks instruction-echo phrases; tested). The 4
echo-requirements from this pilot are quarantined by that rule going
forward and must not be treated as W4 inputs.

## End-to-end evidence packet

Deterministic packet assembly → model proposal → validation → persistence
is proven working (accepted, cached, rejected, and budget-exhausted paths
all exercised and tested). Claims persisted from the deterministic path
(1,202) are unaffected by model quality.

## Conclusion for W4

Pipeline: proven. Model size: insufficient for requirement drafting at
0.5b — W4 entry requires either a stronger local model
(`mistral-small:latest` / `qwen2.5-coder:latest`, both present) within a
fresh authorized budget, or acceptance that requirement drafting stays
human-supervised. No outcome judgements were made (none possible at W3).
