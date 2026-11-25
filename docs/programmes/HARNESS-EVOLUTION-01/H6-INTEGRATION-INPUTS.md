# H6 integration inputs

This is a design handoff, not authorization to integrate or execute writes. The recommended seam is Worker catalogue + versioned `WorkResult`/H3 summary as execution evidence, Mission Work Outcome as episode/evaluation/governance owner, and the existing Workbench ActionSpec/approval path for any governed action. Do not create a second episode lifecycle or copy model transcript payloads into Mission.

Mission's current Work Outcome APIs cover episodes, evaluations, observations, envelopes, intent, and corrective proposals. H6 should first reconcile the exact uncommitted Mission contracts and ownership with the owner; no H5 code wrote to them. A future adapter should carry only stable references and bounded typed fields: observed-state reference, action code, policy/version, supporting evidence references, authority requirement, and resource estimate. Worker must revalidate typed actions and local policy at execution; Mission retains approval and outcome authority.

No automatic proposal application, self-modification, production migration, service restart, or promotion follows from H5. The live pair is one task family and does not qualify broad adaptive selection. Design H6's read-only mapping and validation first, then seek a separate explicit implementation scope if needed.
