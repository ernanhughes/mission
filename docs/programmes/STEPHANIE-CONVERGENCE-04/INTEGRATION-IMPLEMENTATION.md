# SC4 integration implementation

SC4 adds Mission's Improvement workspace and a read-only adapter over the accepted SC3 artifact snapshot. It reuses existing Mission APIs and data for episodes, findings, corrective proposals, envelopes, harness catalogue, and Praxis proposals. The only write path exposed by the page creates an inert `REQUEST_USER_DECISION` corrective proposal from a selected open finding.

The adapter validates candidate/protocol/hypothesis identity and linked hashes for results, experiences, and the AI trace. It returns a bounded projection and does not return raw AI response bodies. A post-hoc sidecar manifest binds the six snapshot files for change detection; it is not cryptographic attestation.

No schema migration, Stephanie API, Worker call, experiment execution, model call, Mission data write, commit, push, or deployment was performed. The Mission service currently listening on `:8790` is pre-SC4 and returns 404 for the new route. The frontend build is not activated.

Mission-specific detail: [workspace report](../../../../mission/docs/programmes/STEPHANIE-CONVERGENCE-04/MC-IMPROVEMENT-WORKSPACE.md).
