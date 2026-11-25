# W4-AI-PROJECT-PILOT — 6 episodes, deterministic + gated semantic ($0)

Scope: ai project, scratch `w4_pilot3` (git snapshot copied read-only).
Semantic budget: 10 bench + 2 probes + 6 extract + 2 eval = 20/30 calls,
$0.00 (local models; electricity unmeasured, reported as non-zero
operational cost per §16).

## Deterministic base (all 6 episodes)

Claim verification over 51 deterministic claims: commit-mention claims with
resolvable SHAs → verified_commit_exists; test/review/integration assertions
without corroborating records → reported_only/unverified (never upgraded).
Requirement assessment over W3 requirements + auto-linked evidence:
resolvable links → satisfied_reported at most; unlinked mandatory →
insufficient/not_satisfied by the sibling rule. Completion: `unknown`
everywhere except AI-CORE-05 (`incomplete`, mandatory unsatisfied) — no
episode could be complete without independent verification, and the system
said so.

## Semantic layer (mistral-small, validated, 2 calls)

Eligible requirements (evidence-linked) in 2 episodes received batched
model assessments; both returned insufficient_evidence with specific
missing-evidence pointers, agreeing with the deterministic layer.
4 episodes had no eligible requirements (no validated extraction) and
correctly received zero semantic calls. 2 extraction outputs were rejected
by validation (paraphrase filter); quarantined, not stored as requirements.

## Complete packet: ep:task:AI-CORE-05 (illustrative real output)

- Objective (inferred): AI-CORE-05 review work.
- Mandatory requirements: "Review the AI-CORE-08B-1 task" (explicit_user).
- Assessment: not_satisfied/insufficient — no review evidence linked;
  evidence refs: episode commits (unlinked to this requirement).
- Execution: unknown (no restriction violations observed, no positive proof).
- Outcome: poor (mandatory unsatisfied; no contradictory evidence).
- Completion: incomplete.
- Outstanding: verification_gap + missing_requirement findings with next
  actions (supply review evidence; implement or defer).
- Recommended next action: locate or perform the AI-CORE-08B-1 review and
  link it; re-evaluate on new evidence.
- Limitations: single local model; no independent human review; file-level
  evidence not yet bound.
- Cost: 1 extraction + 1 evaluation call, $0.00.

## Coverage of §15 kinds

Evidence-rich (08C) ✓, incomplete (05) ✓, insufficient-evidence (WEB-01B,
chain, 01) ✓, non-code proxy (unresolved bucket: honestly unknown, no
forced verdict) ✓, repeated-claims (08C: 50 deterministic claims,
dedupe demonstrated) ✓, semantic-required (05) ✓. Fully-verified-complete:
NOT AVAILABLE in the sample — recorded as a gap (no `complete` verdict was
or could be produced; the one case the system must eventually show).
