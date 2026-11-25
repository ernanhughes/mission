# HARNESS-EVOLUTION-01 — H0/H1 Final Report

**Status: CONDITIONALLY READY FOR H2 ARCHITECTURAL REVIEW.** H0 inventory and H1 research review are complete within the authorized read-only scope. H2 is a proposal only; implementation remains unauthorized.

## Direction

The central hypothesis is supported: the ecosystem already has substantial harness capabilities distributed among Mission, Worker, Writer/ECK, Praxis, Workbench, and supporting packages. The best candidate is a federated architecture: Mission governs and observes; Worker is the execution substrate; Pi/OpenCode are engines; domain context and effectiveness remain with their existing owners. Do not create a new monolith or parallel evaluation system.

The first candidate slice is a reproducible execution baseline with explicit effective policy/configuration and trace identity. First check whether current Mission Work Outcome work (currently uncommitted) already provides the necessary identity/evidence contract. Praxis H01–H05 show why claims must remain conservative: bounded-loop mechanics were demonstrated, but quality/recovery advantages were not established, and H05 found a no-fault false-recovery behavior.

## Conditions for H2 decision

1. Review the architecture alternatives, proposed contract map, and vertical slice.
2. Resolve the book’s Pi-centered reference-host premise against Worker’s production-substrate role.
3. Inspect the actual durable Mission/Worker identity and event contracts once the current WIP is reviewable.
4. Define the first task family, evaluator independence, budgets, holdout protection, and promotion authority.

These are evidence gates, not questions requiring answers before this report can be reviewed. Existing repositories contain extensive active uncommitted work; it was preserved and must be considered before implementation. External research is methodological input only; no external code was installed or run.

## Scope and verification

No source code, tests, services, models, migrations, installations, commits, or manuscript files were changed or run. Only the programme documents in this directory were authored. No test suites ran; long tests were intentionally deferred under the repository test policy. Revisions and pre-existing working-tree state are recorded in [PRESERVATION-SNAPSHOT.md](PRESERVATION-SNAPSHOT.md). Supporting evidence and decisions are in the linked H0/H1/H2 records in this directory.
