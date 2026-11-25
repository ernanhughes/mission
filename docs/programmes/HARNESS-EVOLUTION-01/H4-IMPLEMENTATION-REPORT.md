# H4 implementation report

Worker now composes three versioned strategies through its existing `ModelExecutor`, `ModelRuntime`, provider adapters, request/result contracts, cancellation lifecycle, and H3 execution ledger. `GET /v1/strategies` lists definitions and stable SHA-256 digests. Selecting a strategy defaults the backend to `model`; explicit non-model backends are rejected.

Implementation is in `C:\Projects\worker\src\strategies\`, with request integration in `src/schema/request.ts`, composition in `src/executors/model.ts`, strategy-aware summary/config identity in `src/core/execution-summary.ts`, strict ledger validation in `src/core/execution-ledger.ts`, and the read-only catalogue route in `src/server/server.ts`. `worker.models.yaml` adds one explicit local Qwen comparison route and a separate local Mistral review route; neither is in the default policy.

Direct, structured and corrective behavior is covered with scripted deterministic providers. The implementation retains raw outputs in Work results; the H3 ledger stores digests and bounded strategy evidence without raw model output. Strategy identity participates in the configuration digest. Legacy summary shape remains accepted.

No Mission runtime integration, operational database, migrations, production service, Writer/Praxis/AI/Workbench package, or manuscript was changed. H4 is not an adaptive policy system and does not authorize H5.
