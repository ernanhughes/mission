# H5 implementation report

Worker adds opt-in `adaptive.v1`, an explicit request normalization policy, single-fence JSON normalization, separate normalized-artifact provenance, bounded attribution/decision evidence, and strict H3 ledger consistency checks. Existing strategies remain digest-compatible. The local route `h5_mistral7b_local` is configured as free/local-only with one policy attempt; no paid route was used. Mission changes are documentation/evidence only for this stage.

The implementation leaves valid but semantically incorrect outputs untouched. It performs one structural correction only when deterministic schema evidence supports that action. Preflight authority failures, cancellation, timeout, and budget exhaustion are represented as abstention/preemption evidence.

Focused tests and typecheck are recorded in `H5-TEST-EVIDENCE.md`. No full suite, long suite, production database, service restart, deployment, commit, push, manuscript change, or operational ledger was touched for H5.
