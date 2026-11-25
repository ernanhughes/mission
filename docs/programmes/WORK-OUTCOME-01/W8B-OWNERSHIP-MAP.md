# W8B-OWNERSHIP-MAP — Who owns what (loosely coupled, versioned)

| Identity / record | Owner | Others |
| ----------------- | ----- | ------ |
| Work Episode id, objective, requirements, authority | Mission Control (`wo_*`) | referenced by all |
| Corrective proposal + approval + scope hash | Mission Control (`wo_proposals`) | read by executors |
| Work Envelope row (binding of the above + auth ref) | Mission Control (`wo_work_envelopes`) | carried by reference |
| Execution/job/result/usage/model identity | Worker (`wrq_*`, `work_id`, ledgers) | MC links via `wo_execution_links` |
| Invocation/receipt/artifact/admission ids | Workbench (journal/outbox) | MC cites ids as evidence |
| Session observations (Pi/Senpi only) | Sidecar (events/results) | MC W1 covers OpenCode separately |
| Test records/receipts/issues | AITest (`aitest.event.v1`) | MC links receipt ids |
| Review verdicts + coverage | Reviewer systems (GitReview, ai reviews, cocoder) | MC cites as evidence |
| Frozen plans + independent evaluations | ai experiments | MC cites fingerprints |
| Policy gating + learning | Harness / ECK | consumes MC outcome evidence |

Direction of dependence: everyone may READ Mission Control's
identities; nobody must WRITE them. Every other system writes its own
records; Mission Control only ever ADDS links pointing at them.
Coupling is by versioned id reference, never by shared tables or a
central bus. New in W8: the envelope row + four link columns on the
existing execution-link table (migration 050, additive).
