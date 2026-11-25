# H0 — Ecosystem capability inventory

**Method:** read-only inspection of source, repository docs, tests, and prior operation reports; no test, service, model, database, or benchmark was run. Repository revisions and dirty state are in [PRESERVATION-SNAPSHOT.md](PRESERVATION-SNAPSHOT.md).

## Finding

The ecosystem already contains most proposed harness capabilities. They are split by domain and authority. This suggests a composition and identity problem before it suggests a missing framework. Current implementation evidence does not support moving all capabilities into Worker.

## Capability families

| Family | Existing capability | Authoritative home(s) | Current maturity / limitation |
|---|---|---|---|
| Execution substrate | Versioned request/result, executor registry, work declaration/run/acceptance, CLI/API, model invocation, bounded workspace and timeout | Worker; OpenCode Work runtime | Implemented; integration tests and a prior Mission/Worker real workflow are recorded. Worker request/job lookup is process-local; durable Work artifacts are separate. |
| Intelligence selection | Provider/model catalogue, route policy, fallback, data-policy and lifecycle validation, usage and cost normalization | Worker model runtime; Pi/OpenCode provider | Implemented and historically tested. Route policy is configured at service startup; billed cost, estimated value, and unknown are kept distinct. |
| Context and representation | Writer context compilation, semantic inspection, ECK context/prompt mechanisms; Workbench source/context inventory; Remembering context selection | Writer/ECK, Workbench, Remembering | Implemented in their domains. Worker Context Viewer cannot see the full provider prompt; no single shared context contract. |
| State and workflow | Mission workflow approval and ActionSpec; Worker Work/Run; Praxis bounded HarnessState; Mission Work Episode/Intent in active source work | Mission, Worker, Praxis | Multiple valid but non-identical state models. Mission Work Outcome files are dirty/uncommitted; avoid claiming cross-system episode identity already exists. |
| Memory and experience | ECK strategies/lessons/traces; Remembering temporal/standing/context-trace system; AI memory/experience; Stephanie stores | Writer, Worker package, AI, Stephanie | Several implementations, different domain contracts and stores. No evidence of one shared production memory policy. |
| Effectiveness and evaluation | Declared Worker checks and acceptance; Praxis `effectiveness-record.v1`, frozen baseline/candidate comparisons and abstention; Mission Work Outcome verification; Writer quality/evidence | Worker, Praxis, Mission, Writer | Substantial implementation and prior tests. Praxis HARNESS stages mostly rejected or abstained on improvement; independent acceptance exists as a pattern, not a universal production service. |
| Improvement and experimentation | Praxis candidate manifests, ECK learning/experiments, Worker experiments/canaries, Stephanie generation/evolution and experiment records | Praxis, Writer, Worker, Stephanie | Candidate generation and evaluation exist, but no qualified autonomous promotion path. Praxis H05 recommends retiring its generic recovery controller. |
| Governance and safety | Mission human confirmation, workflow scope hash and Docker sandbox; Worker loopback/workspace restrictions and explicit backend semantics; Workbench journaled author apply; AITest observation/quarantine records | Mission, Worker, Workbench, AITest | Implemented in distinct boundaries. Worker Authority package is not evidence that a complete external authority-grant service exists. |
| Observation and traces | Worker jobs, model attempts and Context Viewer; Mission Git/activity, integrations, Work Outcome; Workbench prompt/session ledger; Praxis manifests/reports | Worker, Mission, Workbench, Praxis | Strong local observability; cross-system episode/run/session linkage remains incomplete. |
| Test supervision | AITest discovery/profiling/observe mode; Mission test surface in current worktree; per-repository test policies | AITest, Mission, repositories | AITest latest report says 2 observe-mode pilots, 0 adaptive projects, 32 queued; no always-on adaptive remediation demonstrated. |

## Repositories discovered

Inspected relevant source/documentation at `C:\Projects\mission`, `worker`, `writer`, `workbench`, `praxis`, `stephanie`, `ai`, `aitest`, `inspect`, `next`, `work`, `cocoder`, `alive`, `verity`, `evidence-repair`, `improve`, `sidecar`, `steward`, `bookbuilder`, and the book repository `C:\books\harness`. The more focused capability evidence and ownership decisions are in [H0-CAPABILITY-OWNERSHIP-MATRIX.md](H0-CAPABILITY-OWNERSHIP-MATRIX.md).

No standalone `C:\Projects\pi`, `C:\Projects\opencode-runtime`, `C:\Projects\opencode-remembering`, or `C:\Projects\opencode-relate` checkout was found. Pi/OpenCode are external runtimes; `opencode-runtime`, Remembering and Relate are packages in the Worker workspace. No source was cloned or installed.

## Maturity and confidence rules

The matrix uses `NOT FOUND`, `DOCUMENTED ONLY`, `PARTIALLY IMPLEMENTED`, `IMPLEMENTED`, `TESTED`, `OPERATIONALLY OBSERVED`, and `UNKNOWN`. A historical test report is labeled as such; no result here implies that this investigation reran tests or verified a live service. Conflicts between docs and current working trees are called out rather than silently reconciled.
