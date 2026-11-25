# W8B-HARNESS-AND-ECK-ALIGNMENT — Outcome evidence, not another engine

Harness orchestration (praxis `HarnessState`/`HarnessAction`/
`ActionExecutor` — model never executes; effectiveness records are
advisory), ECK policy/learning loop (writer: `ExecutionPolicy`,
strategy profiles, lesson aggregation, skill learning), and Work
Evaluation are three different systems with one shared need: knowing
what was intended, what happened, and what it proves.

Alignment (not merger):

- Harness owns orchestration + bounded execution state.
- ECK owns policy gating + learning from aggregated lessons.
- Work Evaluation owns outcome evidence: objectives, requirement
  satisfaction, completion, findings, closures — with the provenance
  to be believed.
- The Work Envelope is the handoff object between them: intent +
  authorization + identity, readable by all three, owned (as a row)
  by Mission Control, referenced (not copied) by the others.

Work Evaluation must never become an execution engine, a policy
learner, or a second event bus. It supplies the durable assessment of
whether the original intention was realized — the feedback ECK and
harness engineering currently lack. W8D propagates evidence through
existing paths (worker request fields, workbench journal metadata,
AITest linkage rows, mission association tables); where a path has no
metadata channel (OpenCode sessions via sidecar — Pi-only), the gap is
recorded and the manual association stands in.
