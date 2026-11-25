# W2-ASSOCIATION-PROVENANCE — Every link explains itself

Stored on every `wo_episode_associations` row: `method` (how),
`confidence` (heuristic band), `reason` (reason code), `signals` (up to 20
source signal values), `recon_version`, `valid`. Current reason codes:
`session-chain-parent-link`, `explicit-task-identifier`,
`task-id-artefact-or-fixture`, `programme-co-mention`, `sha-resolved-same-repo`,
`sha-resolved-cross-repo`, `sha-resolved-other-repo`, `sha-unresolved-no-object`,
`ambiguous-abbreviated-sha`, `file-overlap-session-seed`,
`file-overlap-temporal`, `file-overlap-only`, `review-session-shares-task`,
`no-corroborating-signal`, `commit-linked-work` (cluster seed).

Confidence ladder: parent chain / exact task id / same-repo resolved SHA →
`explicit`; corroborated derivations → `strong` (reserved; unused in W2 —
no rule currently claims it); file+temporal → `moderate`; single corroboration
or co-mention → `weak`. Rejected markers (`artefact`, `ambiguous`,
`unresolved-sha`) keep their own rows/stats so W3+ can see what was refused
and why. Contradictory evidence (e.g. SHA in repo A, task in repo B scope) is
recorded as parallel associations — never force-merged; adjudication is W3+.
