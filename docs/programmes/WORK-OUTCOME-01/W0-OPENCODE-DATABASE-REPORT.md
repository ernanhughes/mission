# W0-OPENCODE-DATABASE-REPORT — Safe read-only source survey

All access read-only (`mode=ro`, short-lived connections, WAL-consistent, no copies
ignoring `-wal`/`-shm`, no writes/checkpoints/vacuums). No bodies/prompts/outputs/secrets exported —
DDL, counts, key names, sizes only.

## 1. Location (verified live)

Canonical live DB: `C:\Users\ernan\.local\share\opencode\opencode.db`
(1,588,027,392 B + `-shm` 65,536 B + `-wal` 17,757,232 B at check).
`journal_mode=wal`, `page_size=4096`, `page_count=387702`, `freelist_count=814`.
Writers active: OpenCode Desktop + `opencode-cli` + `opencode-pty` running.

Ruled out: `%APPDATA%\opencode` (absent), `%LOCALAPPDATA%\opencode` (absent),
`~/.config/opencode` (only `opencode.json`, `service.json`, no DB),
`AppData\Roaming\OpenCode` (Electron wrapper only, no DB).

Mission reference: `backend/mission_control/config.py:169-173` default
`C:\Users\ernan\.local\share\opencode\opencode.db` (`MISSION_CONTROL_OPENCODE_DB` override);
comment mandates `mode=ro` per query, never migrate/checkpoint/vacuum.
Upstream override name is `OPENCODE_DB` (`<xdg-data>/opencode/opencode.db`).
No override set in this shell. Env shows `OPENCODE=1, OPENCODE_CLIENT=desktop`,
`OPENCODE_DEFAULT_MODEL=opencode-go/deepseek-v4.1-flash`, live `OPENCODE_SESSION_ID`.

## 2. Schema (exact, 25 tables, 0 views, 0 triggers)

Alpha: `account, account_state, automation, blob, blob_ref, control_account, credential,
event, event_sequence, instruction_blob, instruction_entry, instruction_state, job, kv,
machine, migration, permission, project, project_directory, session_inbox,
session_message, session_part, session_v2, workspace, worktree`.

Core DDL (abridged — full DDL in subagent evidence):

- `session_v2(id PK, project_id FK→project.id ON DELETE CASCADE, workspace_id,
  parent_id, fork_session_id, fork_boundary, slug, directory NOT NULL, path, title,
  version, share_url, summary_additions/deletions/files/diffs, metadata,
  cost, tokens_input/output/reasoning/cache_read/cache_write,
  revert, permission, agent, model,
  time_created/updated/idle/viewed/compacting/archived/suspended/busy (ms epoch), resume_attempts)`
- `session_message(id PK, session_id FK CASCADE, type, seq, time_created/updated, data JSON)`
- `session_part(message_id, session_id, ordinal, type, call_id, time_created/updated, data JSON;
  PK(message_id,ordinal); FKs CASCADE)`
- `project(id PK, worktree NOT NULL, vcs, name (often NULL), icon_*, time_created/updated/initialized/active/archived, sandboxes, commands)`
- `event(id, aggregate_id, seq, created, type, data)` — live 0 rows, not an audit fallback
- `permission / project_directory / session_inbox / workspace / job / automation / ...` — see §4 for counts

Indexes: `session_v2_parent_idx/project_idx/workspace_idx/time_suspended_idx(partial)`;
`session_message_session_seq_idx UNIQUE(session_id,seq)`,
`session_message_session_time_created_id_idx`, `session_message_session_type_seq_idx`,
`session_message_time_created_idx`; `session_part_session_message_idx`;
`event_aggregate_seq_idx UNIQUE`; `session_inbox_session_enqueued_seq_idx UNIQUE`;
`permission_project_action_resource_idx UNIQUE`. No triggers/views.

## 3. Inventory counts (live, `mode=ro`)

`session_v2` 2993 · `session_message` 145505 · `session_part` 13233 ·
`project` 573 · `project_directory` 0 · `session_inbox` 73 · `event` 0 · `job` 5 ·
`permission` 37 · `blob/blob_ref` 0 · `automation` 0 · `workspace` 0 ·
`worktree` 88 · `credential` 15 · `account` 0 · `event_sequence` 3041 · `migration` 64.

Roles (`session_message.type`): assistant 133123, idle 5010, user 4675,
synthetic 1667, system 577, agent-switched 173, model-switched 125, compaction 121, location-switched 34.
Parts (`session_part.type`): tool 7502, reasoning 4387, text 1345.

Timestamps are ms epoch UTC. Live spans: `session_message` min 1790945679978,
max created 1795529242914 / updated 1795529247246;
`session_v2` 1790945679850–1795529181479. `time_archived NOT NULL`: 442 sessions.
Parent/child: 479 child sessions under 81 distinct `parent_id`s (children are separate sessions;
parent rollups exclude children). `job.child_session_id` links 5 spawned works.

Model/agent/usage: `session_v2.model` (JSON) + `agent`; per-request truth in
`session_message.data→model{id,providerID,variant}`.
`session_v2.cost` + token rollups ≈ Σ assistant values; per-request `data→cost,tokens`.
Assistant `data` shapes (last-200 sample, keys only): full
`(agent,content,cost,finish,model,native,snapshot,time,tokens)` ×136;
`+rawFinish` variant ×60; in-flight `(agent,content,model,snapshot,time)` ×4 (no cost/tokens yet).
`model` keys `[id,providerID,variant]`. Tool parts `type='tool'` carry `call_id`;
data keys `['executed','id','name','native','state','time','type']`.
Compaction: `type='compaction'` 121 rows (keys `cost,metadata,model,reason,status,summary,time,tokens`)
+ `session_v2.time_compacting/summary_*`.
Cost semantics (re-confirmed shape): local `cost` = balance charge only (0 for Go/free);
`allowance/list_cost/billing_source` provider-response-only, not retained locally.

## 4. Existing consumers

- **mission (production, read-only, MC-COST-01):**
  `opencode_cost/__init__.py: _connect_ro (file:…?mode=ro, 5s timeout, Row factory);
  status() (file/type + COUNT on 3 tables);
  scan_window() (assistant aggregation by time_created, LIKE probes on idle/synthetic,
  bounded session_meta ≤5000 ids, _MAX_SCAN_MESSAGES=100000 truncation flag);
  session_detail() (≤5000 msgs, children ≤100, failures ≤50, no bodies);
  caller_identity_audit()`. `api/cost.py` GET-only
  (`/status|summary|sessions|sessions/{id}|spikes|efficiency|attribution|catalogue`).
  Tests use synthetic DBs only (`test_opencode_cost*.py` tmp fixtures; `CostPage.test.tsx` fake path).
- **workbench:** no `opencode.db` consumer (0 hits; `opencode*` hits are provider/transport/model-id refs).
- **worker:** no production consumer; observability research only
  (`packages/opencode-observability/scripts/db-sessions.py` read-only lister;
  `run-e02-*.py` hardcode `/root/...` path; `lifecycle-demo.py` synthetic DBs).
  Research note `research/opencode-observation-surface.md` documents drifted upstream table set
  (`session/session_message/message/part/todo/...`) vs live (`session_v2/session_message/session_part`, no `todo`).

## 5. Safe incremental observation (W1 mechanism, not yet built)

1. Open `file:...opencode.db?mode=ro` per poll, close immediately (mission pattern).
   Body-free poll: `id/seq/type/time_created` only; never `SELECT data` in loop.
2. High-water polling: `session_v2 WHERE time_updated > :hwm ORDER BY time_updated,id LIMIT N`
   and `session_message WHERE time_created > :hwm ORDER BY time_created,id LIMIT N`
   (PK tie-break; ms times). Persist HWM **outside** the DB (sidecar/service state) —
   never triggers/bookkeeping tables inside live DB.
3. Delete detection by periodic re-census (`COUNT(*)` + known-id spot checks):
   deletes cascade with no tombstones; vanished id ≡ never-existing.
   `time_archived` covers soft-archived only (442); hard delete leaves no trace.
4. Expect `SQLITE_LOCKED/BUSY` during checkpoints; back off/retry with explicit `locked` envelope.
   `timeout≈5s`, short read-only transactions.
5. WAL: **never copy DB without `-wal`/`-shm`**; prefer live `mode=ro` (applies WAL consistently).
   `immutable=1` ignores the 17 MB WAL and under-reports — use `mode=ro`.
   Never read/export `kv` values or `account/credential` columns (tokens/grants); key names suffice.
6. Known gaps (record as deferred): provider `allowance/billing_source/list_cost` absent locally;
   direct app→inference bypasses sessions; `cache_write` window provider-side only;
   `data` JSON shape varies by version (tolerate missing keys).

## 6. Limitations for correlation

- No stable task/episode ID in schema; identity is `(session id, message seq, part ordinal)` +
  `project.worktree/directory/path` + `parent_id/fork_*` + `job.child_session_id`.
- `project_directory` 0 rows — do not rely on it for cwd mapping; use `session_v2.directory/path`.
- `project.name` often NULL — resolve via `worktree` path + Mission `DiscoveryRoot`/`Repository`.
- Timestamps alone never prove commit belonging (see correlation design).
- `event` 0 rows — no server-side audit log to fill delete gaps.
