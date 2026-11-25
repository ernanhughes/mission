# W3-SEMANTIC-TRIAGE — Deterministic first, models only for the residue

## Classification set

`SUBSTANTIVE_NEW_WORK | CONTINUATION_OF_EXISTING_WORK | REVIEW_OR_CORRECTION |
RESEARCH_OR_INVESTIGATION | DESIGN_OR_PLANNING | TRIVIAL_INTERACTION |
DUPLICATE_OR_QUOTED_HISTORY | NON_PROJECT_ACTIVITY | INSUFFICIENT_EVIDENCE |
AMBIGUOUS` (+ internal `NEEDS_SEMANTIC` = queue marker, never reported as a
verdict).

## Deterministic rules (implemented in `triage.py`, tested, zero model cost)

- Probe/READY sessions (user text matches probe markers, ≤6 msgs, no
  task/sha/file/claim/tool signals) → `TRIVIAL_INTERACTION` (explicit).
- Attached-file instruction sessions with no resulting tool/sha/file signals →
  `INSUFFICIENT_EVIDENCE` (explicit; request present, execution absent).
- Sessions in task episodes or chains with corroborating signals →
  by construction `SUBSTANTIVE_*`/`CONTINUATION` candidates (W2 links stand;
  triage does not relitigate them).
- Sessions whose only signals are completion/test claims (no task/sha/file) →
  `AMBIGUOUS` (claim without anchor; model may resolve, default abstains).
- File-signal-only sessions with research-ish paths (docs/research/*,
  *.md plans) and no code files → `RESEARCH_OR_INVESTIGATION` (candidate).
- Review-tool sessions → `REVIEW_OR_CORRECTION` (mirrors R7).
- Everything else with corroborating signals but no episode home →
  `NEEDS_SEMANTIC` (bounded model queue); with no signals at all →
  `INSUFFICIENT_EVIDENCE`.

## Model queue discipline

Only `NEEDS_SEMANTIC` and `AMBIGUOUS` sessions reach a model, each with a
capped evidence packet (redacted excerpts ≤800 chars × ≤6 messages, signal
list, no full bodies). Output is a triage *proposal* reconciled through W2
association mechanisms — never a verified association. Abstention is a valid
output. Budget: ≤20 invocations, $1 ceiling (W3-COST-REPORT).
