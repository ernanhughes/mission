# Bounded passage P-09: staccato consolidation (Ch9 four-jobs)

## Source

- Chapter: `09-chapter.md` (authoritative, rev `c7aaad7`), block L22–25.
- Complexity: **CX10-high** staccato run + **CX11-medium** on the block
  (`publication-complexity-v0.1`, snippet-scoped re-run below).
- Claim tier: **PROPOSED** — explicitly NOT established (D-PUB-42); the
  hypothesis framing must stay attached.

## Before (verbatim, L22–25)

**PROPOSED:** separate four jobs. The specification names the decision and its
answer set. The provider produces scores. The runtime checks their shape. An
evidence record compares those scores with outcomes. Your application still has
to choose an action and the acceptable consequences of a mistake.

## After (candidate)

**PROPOSED:** separate four jobs: the specification names the decision and its answer set, the provider produces scores, the runtime checks their shape, and an evidence record compares those scores with outcomes. Your application still has to choose an action and the acceptable consequences of a mistake.

## What changed and what did not

- Changed: five staccato sentences → two flowing sentences. The four jobs
  read as one designed separation (which is the claim's point), and the
  application's residual responsibility keeps its own closing sentence.
- Preserved: the **PROPOSED:** hypothesis marker; all four jobs named with
  their roles; the application's duty to choose an action and own the
  consequences of a mistake. No numbers, citations or cross-chapter deps in
  the block; none added.
- NOT strengthened: still a proposal, still framed as such.

## Verification (snippet-scoped `publication-complexity-v0.1` re-run)

- Before: CX10-high + CX11-medium.
- After (single-sentence variant): CX03-medium only. Rejected as a landing
  spot: trades staccato for one 60-word dense sentence.
- After (two-sentence landing above): CX03-medium on the jobs sentence only.
  Residual accepted with rationale: the four parallel clauses ARE the
  content (one separation, four named roles); re-splitting them recreates
  the staccato run. Max severity high→medium, count 2→1, and the remaining
  finding sits on the sentence whose parallelism is the point.
- No detector-count optimisation claim: the verdict rests on the
  preservation checks above (marker kept, all roles kept, none added),
  with the detector delta reported as informative confirmation only.
