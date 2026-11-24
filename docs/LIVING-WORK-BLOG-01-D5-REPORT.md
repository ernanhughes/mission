# LIVING-WORK-BLOG-01 — D5 Report: Automatic Deterministic Writer Observation Maintenance

**Status:** D5 implemented as a bounded, isolated proof of concept and verified.
No commits, pushes, deployments, live models, manuscript modifications, or
catalogue-wide automatic processing. No ALIVE service changes. D3/D4 reported
separately; their acceptance is unchanged.

## 1. Objective (as authorized)

Make deterministic Writer observations a maintained property of blog posts
rather than a manually invoked, transient operation: a post is discovered or
changes, Mission Control determines whether its stored Writer observation is
current, an eligible deterministic operation runs automatically, the result is
persisted append-only with provenance and digests, the collection reflects
the stored evidence, and ALIVE can present it inside its existing authority
boundary.

**Success criterion:** a blog post can acquire and maintain current
deterministic Writer evidence without individual manual intervention, while
Mission Control and ALIVE preserve their existing authority and editorial
boundaries — **met by the pilot.**

## 2. Architecture reuse decisions

| Need | Decision | Rationale |
|---|---|---|
| Execution lifecycle | Reused `integration_executions` (queued → running → succeeded/failed) via the existing `IntegrationService.start_action`; new action `writer_observe_post_auto` on the existing Writer adapter (standing `approval_required=False`, `risk=bounded_local_computation`) | Same durable receipt contract as the governed M3 twin; no new scheduler, scorer, or capability registry. One dispatch per pass at most; the service's global per-action active guard additionally serializes automatic runs. |
| Fingerprint | Local `auto_fingerprint` in `websites/maintenance.py` with the identical canonical JSON scheme as the book-pipeline fingerprint | Intentional contract-copy kept local so D5 does not depend on the uncommitted pipeline-maintenance module; receipts stay comparable if the tracks are ever unified. Documented in code. |
| Freshness | Derived at read time (stored `body_sha256` vs live evaluated body sha), never by overwriting; receipt status and freshness kept separate | A succeeded run never flips state by itself; the projection decides. Same principle as the book pipeline, applied to post bodies. |
| Storage | New table `website_post_writer_observations` (migration 039) + `WebsitePostWriterObservation` model, deliberately separate from `website_post_evaluations` | Editorial readers are rubric-blind in places; a separate table makes it structurally impossible for Writer evidence to masquerade as an editorial verdict. History is append-only; renames create new identities with no transferred history. |
| Trigger | Polling reconciliation (`BlogMaintenanceService.run_once`) over live digest comparison, with a 1-pass debounce for mid-save edits | File-change detection via digest compare (no filesystem watcher to install/secure); debounce avoids observing half-saved bytes. No background loop is started in `main.py` — catalogue-wide processing stays off; the pilot drives the service directly and the reconcile endpoint defaults to `dry_run: true`. |
| Collection | Extended the D4 map with a read-only `writer_evidence` block; editorial keys byte-unchanged | One coherent view; Writer coverage can never be averaged with the 33%-style editorial coverage (separate block, separate denominator note). |
| ALIVE | Extended `format_collection_text` only (presentation, verbatim, no arithmetic); no service wiring, no new measure, no new authority | Same scoped pattern as D4. |

## 3. Files changed

**Mission backend:**

| File | Change |
|---|---|
| `backend/mission_control/persistence/migrations/039_website_post_writer_observations.sql` | NEW. Append-only observation table + two indexes. |
| `backend/mission_control/models.py` | +`WebsitePostWriterObservation` (JSON envelope, digests, provenance, fingerprint). |
| `backend/mission_control/websites/maintenance.py` | NEW (~1000 lines). Standing policy (settings keys, default OFF), local fingerprint, pure `decide_post` (run/skip/blocked/wait), read-only `project_post_state`, sequential `BlogMaintenanceService` (debounce, cooldown, retry cap, one dispatch/pass), append-only `store_observation` (uuid ids), idempotent `ingest_completed_execution` (receipt→row with binding re-check), read-only `maintenance_status`. |
| `backend/mission_control/adapters/writer.py` | +`writer_observe_post_auto` action spec, `_validate_post_observe` (policy pin, identity confinement, existing blog dir), `_execute_post_observe` (2 MB budget refusal, real in-process detector, receipt with `auto_inputs`+`auto_fingerprint`; current-ness explicitly not claimed). |
| `backend/mission_control/websites/collection.py` | +`writer_evidence` block (`_live_body_sha`, `_writer_evidence_block`): per-post current/stale/missing/unknown with stored summaries, totals, `needs_attention` identities. Editorial keys untouched. |
| `backend/mission_control/api/website_posts.py` | +5 endpoints: `GET writer-maintenance/status`, `POST writer-maintenance/enabled`, `POST writer-maintenance/pause`, `POST writer-maintenance/reconcile` (dry-run default true), `GET writer-observations/{identity}` (history, newest first). No dispatch without explicit opt-in. |
| `backend/tests/test_mc_website_writer_maintenance.py` | NEW (8 tests, see §5). |
| `backend/tests/test_migrations_and_seed.py` | Range 1–39, version 39, new table asserted (3 lines). |

**ALIVE:**

| File | Change |
|---|---|
| `alive/living_book/quality_history.py` | +~28 lines: `writer_evidence` rendering (totals verbatim, per-post `WOBS` lines, absent block renders nothing). Purely additive; D4 output for maps without the block is unchanged. |
| `alive/tests/test_living_book_collection_writer_evidence.py` | NEW (3 tests). |

**Not changed:** `main.py` (no background loop — the pre-existing blog-sync references are cultivation code, untouched), editorial rubric/scoring, review flows, PostDetail UI, CollectionTab UI (the new map block is ignored by the current tab; see §7).

## 4. Real execution evidence (pilot)

Isolated Hugo fixture + disposable DB + real deterministic Writer Artifact
detector, driven end to end in `test_pilot_lifecycle_*`:

1. **Missing:** fresh post projects `has_evidence=false, freshness=missing`.
2. **Eligible:** pure decision returns `run` (enabled, unpaused, readable, no active run).
3. **One real execution:** adapter returns `succeeded` with `mc.writer_observe_post.v1` receipt bound to the evaluated-body sha; raw file bytes identical before/after.
4. **Stored:** `store_observation` persists the envelope; projection reads `current`, `history_count=1`.
5. **No duplicate:** with unchanged content and a matching receipt fingerprint, decision is `skip`.
6. **Stale after edit:** appending a paragraph flips freshness to `stale` with history preserved.
7. **Reprocessing:** a second observation restores `current` with `history_count=2` (both rows retained).
8. **Rename isolation:** renamed file reports `missing` under the new identity; the old identity keeps its 2 rows.
9. **Idempotent ingest:** ingesting the same succeeded execution twice yields one row.
10. **Endpoint behavior:** status (disabled by default), empty history, dry-run reconcile with zero dispatches, enable/pause round-trip, 404 for unknown identity.

## 5. Test results

- **D5 Mission (new): 8/8** — fingerprint contract, decision matrix, adapter validation + real-detector receipt, full pilot lifecycle, collection lifecycle, endpoint status/history/dry-run, ingest idempotency.
- **Regression: 86 passed** — D3 artifact/observe (17), D4 collection (9+3), posts (15), posts-context (14), migrations+seed, living-book represent/improvement/core.
- **Pipeline neighbors: 35 passed** — M3/M4A/adapter suites (a `ruff format` pass normalized whitespace in adjacent uncommitted M4A hunks of `writer.py`; behavior verified unchanged by these suites).
- **ALIVE: 44 passed** — incl. 3 new writer-evidence renderer tests; D4 renderer output for maps without the block is unchanged.
- **Frontend: 145/145, `tsc` clean** — no UI change required; the new map block is ignored by the current tab.
- **`ruff check` + `ruff format --check` clean** on all touched files except two pre-existing format deviations in `test_migrations_and_seed.py` outside the D5 hunks (left untouched).

## 6. Resource measurements

Single-post pilot (218-byte fixture post, local machine): envelope
computation **~12 ms**, envelope **~5.5 KB** (`complete`, 1 finding,
11 dimensions); adapter receipt **~2 ms** overhead, receipt **~0.9 KB**.
Bounds: 2 MB per-file refusal, one dispatch per reconcile pass, 200-row
receipt scan, 500-row observation scan per map build, 3-attempt retry cap,
300 s failure cooldown, 2-pass debounce. Nothing in the hot path scales
with catalogue size except the per-post digest scan, which is linear file
I/O already performed by listing.

## 7. Limitations and recommendations

1. **No background loop and no tab UI yet (by design).** The service runs on
   demand (tests, dry-run reconcile); enabling always-on maintenance means
   starting the service in `main.py` with an explicit interval and
   per-site rollout — recommended only after author review. The Collection
   tab does not render `writer_evidence` yet; the map field is stable and
   ready for a read-only section reusing the existing Writer-check styling.
2. **Polling, not watching.** Reconciliation is digest-compare per pass;
   sub-pass edits are caught on the next pass after debounce. A filesystem
   watcher was evaluated and rejected (new daemon surface for no pilot
   benefit).
3. **`ingest_completed_execution` is implemented and tested but not yet
   called from the integration completion path.** The pilot stores via
   `store_observation` directly; wiring ingest into `_run_action` (or a
   reconcile ingest step for succeeded auto executions) is the precise next
   task before enabling the loop, with the idempotency key already in place
   (`execution_id`).
4. **Boundaries preserved, to keep:** Writer coverage and editorial coverage
   are separate blocks and must never be combined into one completion
   percentage; duplication candidates stay `pending`; `unavailable` stays
   explicit; a current Writer observation never implies editorial quality.
5. **Rename semantics are conservative:** history never transfers. If
   rename-following is ever wanted, it must be an explicit human-confirmed
   link, not heuristic matching.

## Verdict: D5 ACCEPTED (scoped as above)

A blog post can now acquire and maintain current deterministic Writer
evidence without individual manual intervention: missing → eligible → one
real execution → stored → current → no duplicate → stale on edit →
reprocessed with history preserved — with the master switch defaulting to
OFF, no catalogue-wide processing enabled, and editorial/human-review
boundaries structurally intact.
