# W1-ENTRY-GATE — W0 closure + W1 authorization

## 1. W0 status

W0 conditionally accepted 2026-11-24. Verified this commission:

- [x] All 12 W0 docs present under `docs/programmes/WORK-OUTCOME-01/`, reconciled before implementation.
- [x] Live OpenCode schema inspected (25 tables, `session_v2/session_message/session_part` + `project/...`).
- [x] Mission `activity_git/git/history/api` + models/migrations inventoried; reuse points identified.
- [x] Ecosystem inventory verified (9 repos + `cocoder/steward/verity` provisional).
- [x] Persistence/security model verified (PG `mc` authoritative, ORM-baseline + `*.pg.sql` deltas).

## 2. Pre-W1 decisions (owner-approved, recorded)

| Item | Decision | Enforcement in W1 |
| ---- | -------- | ----------------- |
| Model routing | Deterministic first; DeepSeek `deepseek-v4.1-flash-free` → `deepseek-v4.1-flash`; Muse implementation; Codex `gpt-6-luna` independent review; `claude-haiku-5-5` if needed | W1 pipeline makes **zero** model calls. Review step (§13) uses existing governed invocation; cost tracked separately. Gap recorded: no Muse/Codex route exists today (only `configured-local-openai` + `pi-default`) — no new route built in W1. |
| `.workbench` allow-list | Deny-by-default; explicitly validated structured evidence only | `workbench_evidence_allowlist`: `editorial-decisions.jsonl`, `editorial-candidates.jsonl`, `preferences.json:book`, `ledgers/*.jsonl[LEDGER_FIELDS]`, `runs/metadata-book/*.{json,events.jsonl}`, `*-publication-preflight.json`, receipt projection, `activity/workbench.jsonl`, `errors/*` truncated. Deny: raw prompts/replies/manuscript text, sessions/*, sidecar tokens, `.env`/DSNs, fixtures/bundles/patches, absolute paths (relativize at boundary). Existing `EXCLUDED_DIRS={.workbench,…}` stays for discovery/git; allow-listed reader is the only ingress. |
| Retention | Durable derived records + evidence refs; minimise duplicated conversation content | W1 persists observation metadata, source refs, candidate signals, checkpoints, run/error records. Large raw payloads stay in source. Excerpts ≤800 chars, redacted. Historical records flag `source_missing` when origin vanished. |
| Git status | W0 docs-only; preserve unrelated publication changes | Baseline recorded §3. W1 stages only its own new files; never stages `docs/programmes/publication/*` or unrelated modifications. No commit/push/deploy in W1. |

## 3. Repository baseline (W1 start)

- Branch: `main`.
- High-water migration: `040_script_bigint.pg.sql` (next PG delta number verified at write time).
- Pre-existing modifications (not ours, preserved): `M docs/programmes/publication/CAPABILITIES.md`, `M .../DECISIONS.md`, `M .../STATE.md`.
- W0 addition: 12 untracked docs under `docs/programmes/WORK-OUTCOME-01/` (reconciled, not staged by this commission).

## 4. W1 entry requirements (status)

- [x] Model routing verified through existing mechanisms (gaps recorded, no new routes in W1).
- [x] Workbench formats inspected; allow-list frozen above.
- [ ] Message/part coverage understood — pending investigation report (entry requirement §2); W1 adapter design follows its findings.
- [ ] Seven-case `ai` census — executed in W1 §3, frozen as acceptance fixtures.

W1 proceeds: observation foundation only. No W2 episode reconstruction, no AI evaluation, no Activity UI, no bulk backfill.
