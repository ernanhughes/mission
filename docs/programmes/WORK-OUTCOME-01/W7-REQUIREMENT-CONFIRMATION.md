# W7-REQUIREMENT-CONFIRMATION — Human decisions, preserved provenance

Workflow (§13): per-requirement confirm/amend/reject/defer/
insufficient in the Episodes detail view, reviewer name mandatory
(decisions without a reviewer are rejected — no anonymous, no auto).
Amend spawns a new requirement version (supersedes old; old row kept);
all decisions recorded in `wo_requirement_confirmations` with rationale
and timestamp. Batch-safe: an episode filter + one reviewer name covers
a review session without one-by-one ceremony; nothing auto-confirms.

Pilot: 2× 05 requirements confirmed on scratch (adversarial-rejection
gate + anchored regression suite, rationale cites R1 sections). The
remaining 20+ episode backlog is explicitly NOT bulk-confirmed.
Authority note: confirmations attest that the text matches the cited
source — they do not upgrade evidence into verification.
