# W9-USER-GUIDE — Daily use, and what to expect

**Application**: `http://127.0.0.1:8790` → Activity → **Work Evaluation**.

## The four questions

| Question | Where |
| -------- | ----- |
| What did we intend? | Work Episodes → episode → Summary / Requirements (authority, provenance, version, human decisions) |
| What did we achieve? | Summary → Execution / Outcome / Completion, each with rationale |
| How good is it? | Quality tab (three independent perspectives, no composite score) |
| What remains? | Outstanding Work (24 groups / 287 findings), Proposals |

## Daily loop (about 5 minutes)

1. Open Activity → Work Evaluation → **Overview**. Read the four
   numbers: episodes, verified complete, needs attention, unevaluated.
2. **Needs attention** lists the consequential work. Click through to
   the episode when something matters.
3. **Outstanding Work** opens on groups. Each group gives the gap
   class, affected episodes, one example wording, the recommended
   action, and what would close it.
4. **Proposals** when you decide to act: inspect → preview commission
   → copy → approve (type your name) → record the handoff. Mission
   Control never executes anything.
5. When evidence arrives, re-evaluate the episode (Controls) and
   close the finding with the citation. Closure needs your name.

## What the numbers mean (and don't)

- **0 verified complete** is currently correct, not a bug: no episode
  has all mandatory requirements independently verified. `PARTIAL` on
  AI-CORE-05 means reported satisfaction with a documented cap.
- `UNKNOWN` completion means the objective was not decomposed into
  assessable requirements — not that the work failed.
- `needs attention` includes legitimate historical evidence gaps
  (minor) and real unscheduled work; severity tells them apart.
- Findings do not auto-close and nothing runs on a timer.

## Enabling more projects

```
POST /api/work-evaluation/policies
{"project_key": "mission", "level": "manual_evaluation",
 "actor": "your-name"}
```

Levels: `disabled` → `observe` → `reconstruct` → `manual_evaluation`
→ `continuous_mechanical` → `continuous_semantic`. Every project is
`disabled` by default except `ai`. A level never authorizes corrective
execution or paid inference.

## What is deliberately off

Scheduled evaluation (no timer exists), unattended semantic
evaluation, automatic corrective execution, automatic requirement
confirmation, automatic closure, and paid inference (budget $0,
no setter). Enabling any of these is an explicit operator decision
with its own gate.

## Known usability gaps

- Requirement confirmation is per-episode; a 23-episode backlog needs
  a session of work, not a single click.
- Group subjects derive from title prefixes, so two distinct claims
  sharing 80 characters could co-group (visible on inspection).
- No cross-project rollup yet — the project filter is the workaround.
- The Envelope tab is read-only; registration is API-first.
