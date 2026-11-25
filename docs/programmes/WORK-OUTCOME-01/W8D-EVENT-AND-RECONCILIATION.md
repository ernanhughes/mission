# W8D-EVENT-AND-RECONCILIATION — No new bus

Reuse only: workbench journal/outbox envelope
(`seq,id,type,run_id,payload,occurred_at`), ai ZMQ bus + Postgres
outbox (opt-in), Mission durable tables (`ActivityEvent`,
`WorkflowEvent`, `WoProposalEvent`, `wo_eval_runs`), AITest
`aitest.event.v1` idempotent ingest, cocoder `MessageEnvelope`
(correlation/causation pattern for cross-system tracing), worker
`JobEvent` + evidence relay.

Work Evaluation publishes nothing new. It consumes, by polling or by
receiving where the producer already sends: work registered (envelope
row), requirement amended (new version + supersession), execution
started/ended (execution link status), commit associated (W1/W2
associations), test evidence available (receipt ref), review completed
(review ref), finding identified (existing pipeline), corrective work
commissioned (proposal row), verification completed (assessment row).

Idempotence (digest dedupe: envelopes, proposals, findings fids),
replay (re-runnable passes; scratch pass1/pass2 identical effect),
late evidence (links append; staleness marks re-evaluation), source
unavailability (blocked, never silent zero) — all demonstrated or
tested, none newly invented.
