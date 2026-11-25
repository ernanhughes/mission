# H0 — Worker architecture as-is

## Identity

Worker is currently a **thin HTTP/CLI gateway and executor selector** over a modular OpenCode Work runtime. Its public API is `POST /v1/work` and request lookup; the public contract is `worker.work-request.v1` / `worker.work-result.v1`. Worker is not currently a general-purpose programmable policy engine or a complete harness control plane.

## Representative execution path

```text
caller → request normalization → configured executor → Work declaration/run
       → model/tool execution → fresh observations → proof/acceptance → result
```

Executor selection is explicit. `opencode` and `direct` produce `AWAITING_ACCEPTANCE`; only the integrated `opencode-work` path creates real Work/Evidence/Verify/Proof/Acceptance records and can report `ACCEPTED` from its declared checks. Model prose is not evidence. Worker has a stable request/result envelope, but its request lookup and recent job/event history are process-local; Work and VFS records have their own durable stores.

## Current capability boundaries

- **Execution engines:** OpenCode CLI and Pi adapters are replaceable; Pi, OpenCode, authentication and provider services remain external. The optional Pi executor is explicitly experimental and not the default route.
- **Model selection:** Worker owns a versioned model runtime and configured route policy; Pi owns authentication and model invocation for the default OpenCode Go routes. Explicit fallback is policy-controlled; no silent executor fallback. Pricing and subscription use are not necessarily billed-cost observations.
- **Context:** Worker accepts a structured request and delegates assembly to its engine. The read-only Context Viewer observes request, calls, runtime/tool events, usage and timeline after execution; it explicitly cannot establish the exact provider prompt or tokenization.
- **Work semantics:** `opencode-work` composes Work, Evidence, Verify, Proof, Acceptance and VFS. Runtime package inclusion does not imply a plugin is enabled or used.
- **Other capabilities:** Remembering, Relate, Expertise, Authority and Observability live as packages in the Worker workspace; Workspace docs state optional capabilities are not silently wired into default execution.
- **Safety:** loopback by default, explicit remote-bind gate, environment references for credentials, declared workspace requirement, and no implicit broadening of filesystem scope.

## Implications

Worker already has the smallest credible execution boundary for a harness: normalized task request, execution strategy, engine/provider seam, result identity, and bounded resource/config policy. The missing cross-ecosystem behavior is not an entire second execution engine. It is policy lineage and correlation across caller objective/episode, Worker request, Work run, engine session, evidence, evaluation, and later experience.

Worker should not absorb Mission approvals, Writer context semantics, ECK's domain learning, Praxis effectiveness evaluation, or Stephanie's research process. A Worker-centered monolith would contradict the existing modular package boundaries and the user’s explicit direction.

## Source references

`C:\Projects\worker\README.md`; `docs/workspace.md`; `docs/V02-INTEGRATION.md`; `docs/model-runtime.md`; `src/schema/`; `src/core/`; `src/executors/`; `src/models/runtime/`; `packages/opencode-work/ARCHITECTURE.md`; `packages/opencode-work/src/{work,runs,store,engine}.ts`; `packages/opencode-remembering/README.md`; `packages/opencode-relate/README.md`.
