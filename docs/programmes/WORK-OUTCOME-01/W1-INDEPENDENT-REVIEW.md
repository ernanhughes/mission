# W1-INDEPENDENT-REVIEW — Implementer review (no model route available)

Status: honest substitute, explicitly NOT an independent model review.

## Why no model review

- W1 §13 names `deepseek-v4.1-flash-free` → `deepseek-v4.1-flash`, escalating
  to `gpt-6-luna`. Verification (W0/W1 entry): **no such route exists** in
  Mission Control (only `configured-local-openai` + `pi-default`; zero
  `Muse|codex|gpt-6|luna` references outside provider-name strings).
- Worker (the governed execution path that could run an external model) is
  unreachable (`127.0.0.1:7317` refused). No local endpoint is configured.
- Building a new model route inside W1 would violate "W1 observation must
  not require AI calls" and the W1 stop conditions.

Track as W2 pre-condition: establish a governed review route (or record a
standing exception) before any stage that requires model judgement. Review
cost this stage: 0; observation pipeline cost: 0 (verified in every envelope).

## Challenge list (10 points, verified against code + tests)

1. **Read-only access** — PASS. Single `sqlite3.connect` site
   (`opencode_adapter.py:65-67`), always `file:…?mode=ro`, closed per batch;
   no `UPDATE/INSERT/DELETE` against the source; migration touches PG only.
2. **Incremental completeness** — PASS with noted bound. `(time,id)` cursors +
   5-min overlap + ASC/limit fetch (no skipping); truncation flagged with
   resume. Bound: rows older than the overlap that arrive after hwm advance
   are caught only by re-census (documented; deletes have no tombstones).
3. **Watermark correctness** — PASS. Ties broken by id; checkpoints advance on
   `completed` only; locked/failed runs leave them untouched (tested).
4. **Duplicate prevention** — PASS. Stable `sha1(ref|type|digest)` ids +
   pre-check + in-run dedupe; repeat run → `signals_new: 0` (tested + live).
5. **Source identity** — PASS. `(session id, msg seq, part ordinal)` +
   `(project worktree, directory)` + `parent_id/fork/job.child` links;
   `project.name` NULL and `project_directory` empty confirmed unreliable and
   not used.
6. **Historical content availability** — PASS. Primary=`session_message.data`
   (complete all eras), parts=recent supplement; matrix in
   W1-HISTORICAL-COVERAGE-REPORT; absence ⇒ `source_missing`, never "no work".
7. **Evidence classification** — PASS. OBSERVED/CLAIMED/INFERRED enforced at
   extraction; VERIFIED unproducible here by construction; tests assert a claim
   never becomes verified through normalization.
8. **Git reuse** — PASS. No new history system; `resolve_identity` + existing
   index; 6/8 sampled SHAs verified present; failures recorded, not raised.
9. **PG migration safety** — CONDITIONAL PASS. Additive-only, `IF NOT EXISTS`,
   dual-file 041 with runner-guard semantics, SQLite suite green, fresh-PG
   baseline proven on scratch. Not proven against a pre-existing PG (no
   isolated PG available) — operational `mc` untouched; auto-applies on next
   start.
10. **Credential/private-content exposure** — PASS. Fixtures synthetic (no
    history in tests); excerpts redacted + ≤800 chars; allow-list denies raw
    prompts/text/creds/absolute paths; census/freeze reports carry ids +
    counts only.

## Unresolved (carried to W2)

- External model review route does not exist; Worker down.
- Pre-existing-PG application of 041 unproven (low risk, automatic on start).
- No full-backend regression run (focused suites only, per policy).
