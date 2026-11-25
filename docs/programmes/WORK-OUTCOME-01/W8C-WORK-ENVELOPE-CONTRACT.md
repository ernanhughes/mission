# W8C-WORK-ENVELOPE-CONTRACT — work-envelope.v1 (reuse, not invention)

```json
{
  "schema": "work-envelope.v1",
  "id": "we:<hex16>",
  "episode_id": "ep:task:W8-PILOT-VERIFY-08C",
  "programme_id": "WORK-OUTCOME-01",
  "stage_id": "W8",
  "objective_ref": "w8obj1",
  "requirement_refs": ["3a4b4b7d", "f0018967", "e65d1633"],
  "repositories": ["git-78e0d72b6ea4b329629520f8"],
  "commission_digest": "sha256:32...",
  "authorization_ref": "human:w8-human:W8E prospective pilot charter",
  "acceptance_policy_ref": "w6b-v1",
  "parent_work_id": null,
  "originating_findings": [],
  "version": 1,
  "status": "active"
}
```

Field provenance (every id must resolve or registration is rejected):

- `episode_id` → `WoEpisode.id` (Mission Control owns work identity).
- `objective_ref` → `WoObjective.id` (same episode; enforced).
- `requirement_refs` → `WoRequirement.id` (+ recorded versions at
  registration; re-registration on requirement amendment).
- `repositories` → `GitRepository.repo_uid`.
- `commission_digest` → sha256 over canonical
  {objective, requirements[{id,v}], scope, acceptance} (tamper-evident
  binding; duplicate digests collapse to the existing envelope).
- `authorization_ref` → `proposal:<id>@v<n>:<scope_hash>` (approved
  wo_proposal, version-pinned) OR `human:<actor>:<note>` (explicit
  attestation; system/model refused).
- `acceptance_policy_ref` → rubric/severity policy version (w6b-v1).
- `originating_findings` → `WoFinding.id[]` (corrective lineage).

Supported: single/cross-repo (repositories list), non-code (no commit
needed), review work (authorization = review commission ref),
corrective work (proposal ref + findings), subtasks (parent_work_id),
multiple executions/sessions (links, not envelope copies), resumed
work (re-register → supersede), interrupted work (status stays active
with history). No Git commit is required for an envelope.
Measured size: 671 bytes for the 3-requirement pilot envelope
(`envelope_size_bytes` probe; carries no conversation, no evidence
packets — §9/§26 bounded by construction).
