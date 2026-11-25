# H1 External Implementation Review

Inspection was limited to primary paper/repository material and selected source files; nothing was installed, cloned, or run.

## Reuse as design ideas

- Exo: protected kernel, replaceable execution harness, durable run history.
- Meta-Harness: isolate candidate code from trusted orchestration, freeze evaluator/task references, enforce budgets, aggregate bounded runs.
- HDA: matched comparisons and explicit attribution of overfit, inference scaling, and residual effects; human checkpoints.
- SEAGym: distinct train, frozen validation, held-out, replay, and cost artifacts.

## Do not adopt as framework dependencies

Each project solves a different scope. Exo is under construction; Meta-Harness reports limited validation; HDA has no repository license declaration; SEAGym provides an evaluation environment rather than promotion policy. The local programme already has execution, governance, evidence, and evaluation owners. Copying a whole runtime would duplicate these boundaries and complicate attribution.

## Decision

Use the patterns to shape H2 contracts and evaluation safeguards. Do not add external runtime dependencies or claim published gains apply to Mission/Worker. Any later code reuse requires license review, version pinning, focused source audit, and a concrete gap that the local owners cannot fill.
