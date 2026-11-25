# W1-OPENCODE-ADAPTER-REPORT — What was built and verified

Module: `backend/mission_control/work_observation/` (`__init__`,
`opencode_adapter.py`, `evidence.py`, `workbench_allowlist.py`,
`service.py`) + `api/work_observation.py`, wired in `main.py`
(`app.state.work_observation`, `include_router`).

## Adapter (`opencode_adapter.py`)

- `status()`: required tables (`session_v2`, `session_message`, `project`),
  optional `session_part`; counts; error envelopes mirror `opencode_cost`.
- Fetchers (all bounded, ordered by `(time, id)` resume keys):
  `fetch_sessions_updated_since`, `fetch_messages_created_since` (+type filter),
  `fetch_sessions_matching` (project JOIN, LIKE with escaping),
  `fetch_messages_for_sessions` (chunked IN), `fetch_parts_for_messages`
  (chunked, empty→[]), `fetch_projects`, `message_type_counts`.
- `parse_message()`: per-type normalization (assistant model/cost/tokens/text
  excerpt/tool calls; user text; other types first-text-field); key-tolerant;
  malformed → `parse_error`. Returns metadata + digests, never full bodies.
- `extract_signals()`: `commit_sha_candidate` (hex7–40, low-entropy rejected),
  `task_id_candidate`, `file_path` (Windows + repo-relative), `git_command`
  (text + tool-name), `tool_invocation` (OBSERVED fact), `workbench_ref`,
  `test_claim` + `completion_claim` (CLAIMED). Every signal carries
  `source_ref` + `provenance`; W1 extracts only, never promotes.

## Evidence (`evidence.py`) + allow-list (`workbench_allowlist.py`)

- `classify_record()`: rows→OBSERVED, assertions→CLAIMED, signals→INFERRED,
  independent re-execution→VERIFIED (unproducible in W1 by design).
- `excerpt_redacted()` (reuses `redact_secrets`, ≤800 chars + truncation marker),
  `digest_text()` (sha256 cache keys).
- Allow-list: 14 relative-path patterns (decisions, candidates, ledgers
  projected to `LEDGER_FIELDS`, run journals, preflights, receipts, model-call
  events, errors, verdict-only scores); deny hints (prompts, sessions, sidecar
  tokens, bundles, `.env`); `relativize()` strips absolute hosts paths.

## Reuse (no competing mechanisms)

`_connect_ro` pattern, RO discipline, error envelopes, Dublin-window helpers
concept, synthetic-fixture test shape — all from `opencode_cost`.
`redact_secrets` from `activity_git.service`. Git identity/storage from
`git/history` + `GitRepository`. PG conventions (no-`relationship()`,
`flush()`-parents, `now_iso`) from `models.py`.
