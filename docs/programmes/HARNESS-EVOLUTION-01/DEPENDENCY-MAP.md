# Dependency and ownership map

```text
Human / Workbench review
          │ intent, approved decisions
          ▼
Mission Control — governance, workflow coordination, episode/evidence observation
          │ stable run request / bounded execution
          ▼
Worker — proposed harness execution substrate and run envelope
          ├── Pi / OpenCode / other engines — reasoning and tool runtime
          ├── Writer — Writer-domain context compilation, ECK, evaluation
          ├── Remembering — durable memory, temporal resolution, selected context traces
          ├── Relate — relationship observations (with UNKNOWN)
          └── Praxis — cross-domain experiment/effectiveness records and policy advice
                    ▲
         Stephanie — future candidate proposer, not acceptance authority

Mission/Praxis independent evaluation → human-governed acceptance / promotion
```

This is a **candidate logical architecture**, not an assertion that all links are presently wired. Ownership remains at the source system; integration should use versioned contracts or references.

| System | Existing responsibility/evidence | Current connection / constraint |
|---|---|---|
| Mission Control (`C:\Projects\mission`) | Applications/actions, approvals, experiment workflows, Docker sandbox, repo observation; Work Outcome/Work Evaluation work | Worker is called through workflow client; Work Outcome's W8 prospective instrumentation is not started. Mission has extensive uncommitted current work. |
| Worker (`C:\Projects\worker`) | HTTP gateway, executor selection, model runtime, stable request/result; modular Work/Evidence/Verify/Proof/VFS/Authority/Observability packages | Pi/OpenCode remain external executors; package inclusion alone does not activate capability. |
| Writer (`C:\Projects\writer`) | Long-form context, manuscript contracts, semantic inspection, prompt/model configuration, ECK mechanisms | Writer owns domain semantics; several ECK mechanisms depend on Writer storage/schema and are not clean standalone imports. |
| Praxis (`C:\Projects\praxis`) | Cross-domain effectiveness record, frozen experiment manifests, baseline/candidate comparisons, abstention | Mission execution/approval remains external; current H01–05 show no general Praxis advantage. |
| Workbench (`C:\Projects\workbench`) | Human-owned context, Pi session control, proposal/check/apply/undo with journal | Author-facing, chapter-scoped, model has no editing tools. Not general orchestration. |
| Pi | Agent loop/session execution; SDK/CLI integration in Worker and Workbench | No `C:\Projects\pi` checkout found; external runtime/SDK exact deployed version not probed. |
| OpenCode Runtime | Work, evidence, verification, proof, acceptance and runtime composition packages | No separate `C:\Projects\opencode-runtime` repo; `opencode-runtime` is a Worker workspace package. |
| Remembering / Relate | Memory/experience and typed relationship observations | Both are Worker packages; not a separate repo and not enabled automatically. |
| Stephanie (`C:\Projects\stephanie`) | Research pipelines, hypothesis/evolution, memory and experiment/evaluation stores | Clean repo at captured HEAD; no stable Mission/Worker API contract found in inspected docs/config. |
| AI (`C:\Projects\ai`) | Shared embedding, retrieval, memory, consolidation, experience, inference abstractions | PostgreSQL/pgvector dependency for major services; neural memory research not production-qualified. |
| AITest (`C:\Projects\aitest`) | Test inventory, observe/adaptive modes, bounded invocation controls and quarantine concepts | Latest report: two observe-mode pilots, no adaptive rollouts; do not infer unattended test remediation. |
| Book (`C:\books\harness`) | Research scaffold, 30 chapter drafts, ten projects, Pi-based target architecture | Explicitly says no implementation results; currently heavily dirty. No manuscript changes authorized. |

## Integration edges to validate later

1. Mission workflow/episode ID → Worker `request_id` → Work `work_id`/`run_id` → Pi/OpenCode session → artifacts/evidence.
2. Effective model and policy/config digest → each execution attempt and result; billed cost remains distinct from estimate.
3. Mission outcome/evaluation → Praxis effectiveness record and frozen manifest, without copying transcripts or evaluator truth into the candidate context.
4. Writer/Remembering context references → Worker execution request with provenance and explicit visibility limits.
5. Human approval and protected evaluator changes → Mission governance, outside the proposer and outside ordinary Worker policy files.

## H6 integration edges now implemented (isolated only)

1. Mission Work Outcome episode/current objective → explicit Work Envelope → Worker `operation_id`; Worker request ID remains the execution identity.
2. Worker H3 summary/job/artifact APIs → Mission read-only adapter and Harness UI. Raw artifact retention remains process-memory limited.
3. Worker `episode_id` / `task_id` → Mission Work Outcome link only after exact Work Envelope correlation. Unmatched IDs do not fetch episode/evaluation details or enter project-filtered history.
4. Mission `project_key` → episode selector filtering and server-side launch validation. Project history is a filtered view of the same Worker ledger.
5. Inspect remains a future descriptive dependency; no discovered capability is executable merely because it appears in Inspect.

These edges were demonstrated on isolated loopback services only. No operational activation is implied.
