# LIVING-WORK-BLOG-01 — D4 Report: Blog-Post Collection View

**Status:** D4 implemented and verified. Read-only collection map, one new
read-only endpoint, one new UI tab. No commits, pushes, deployments, live
models, manuscript modifications, or stored Writer verdicts. No new scorer,
no new tables, no editorial rescoring, no ALIVE service wiring.

## 1. Scope (as authorized)

A collection view over the verified D2/D3 read models that shows, where
evidence exists: post title and canonical identity; editorial evaluation
state; Writer observation state; freshness of each independently; human
review state; findings requiring attention; last observed/reviewed
timestamps; evidence detail navigation. Filtering for stale, unevaluated,
weakest, duplication candidates, and provisional sections. Planned,
unavailable, and failed paths stay explicit — nothing is fabricated to fill
a gap.

## 2. Files changed

**Mission backend:**

| File | Change |
|---|---|
| `backend/mission_control/websites/collection.py` | NEW (~470 lines, ported byte-identical from the verified D4 spike). `build_collection_quality_map`: pure read-model over the live Hugo inventory plus stored `WebsitePostEvaluation` rows. Currency is rubric-bound (only the newest CURRENT `blog-editorial-v1` row per identity counts); scores aggregate current-rubric rows only with full exclusion accounting; stale/unevaluated queues oldest-first with digest pairs; deterministic duplication candidates (shared titles, shared anchored quotes ≥40 chars verified against live bodies) always `decision: pending`; contradictions/topic-gaps/outdated-claims explicitly `unavailable` with reasons. Caps reported, never silent. |
| `backend/mission_control/api/website_posts.py` | +1 endpoint: `GET /{site}/collection/quality` (optional `weakest_n`, `min_quote_chars`) → the map as JSON. Read-only; no validation, scoring, evaluation, or writes. |
| `backend/tests/test_mc_website_collection.py` | NEW (ported byte-identical; 9 tests). |
| `backend/tests/test_mc_website_collection_api.py` | NEW (3 tests): map shape/version, 422-free unknown site handling (404), editorial state reflected after a real evaluation, read-only proof (DB row counts + raw bytes unchanged). |

**Mission frontend:**

| File | Change |
|---|---|
| `frontend/src/features/websites/CollectionTab.tsx` | NEW. Stat strip (published/current/stale/unevaluated/coverage/avg), filter toolbar (needs attention, stale, not evaluated, weakest, duplication, provisional, search), per-post rows with inline evidence (canonical identity, latest evaluation id, evaluated vs live digest), on-demand Writer check (`POST …/writer-observation`, result inline with binding + findings + limitations), "Open full post" navigation into the existing PostDetail, provisional sections rendered as unavailable with reasons, collection-generated timestamp and limitations note. |
| `frontend/src/pages/WebsitesPage.tsx` | New "Collection" tab (gated on `content_section`, like Posts). No existing tab behavior changed. |
| `frontend/src/features/websites/PostsTab.tsx` | One-word change: `PostDetail` exported for reuse. No behavior change. |
| `frontend/src/types/api.ts` | Added `WebsiteCollection*` + `WebsiteWriterObservation` types. |
| `frontend/src/test/CollectionTab.test.tsx` | NEW (6 tests): stats/queues/filters without invention, Writer check dispatch + binding display, full-post navigation + back, human-review state, loading/error/empty states. |

**ALIVE:**

| File | Change |
|---|---|
| `alive/living_book/quality_history.py` | +156 lines, purely additive (verified identical to the spike hunk): `COLLECTION_SCHEMA = "site-collection-quality.v1"` + `format_collection_text` — a presentation-only renderer that carries numbers verbatim, performs no arithmetic, never averages, renders `pending` candidates and `unavailable` provisional sections as such. No measure wiring, no guidance/prompt changes, no authority change. |
| `alive/tests/test_living_book_collection_history.py` | NEW (7 tests, ported byte-identical). |

## 3. Verified behavior

- **No second scorer, no duplicate quality history.** The map carries the
  D2 editorial verdicts; it never re-scores, never averages across rubrics,
  creates no tables, writes nothing (test-asserted: row counts and blog
  listing unchanged across builds).
- **Single-rubric distributions.** Only `blog-editorial-v1` CURRENT rows on
  live content enter scores/weakest; everything else is counted in the
  explicit `excluded` buckets — never zero-filled, never merged.
- **Queue semantics.** Stale rows carry evaluated vs live digests;
  unevaluated rows list posts with no stored evaluation; weakest lists
  lowest first with evaluation ids.
- **Duplication discipline.** Candidates require verbatim shared titles or
  anchored shared quotes verified against live bodies (with quote/title
  digests and every carrier's content digest); all stay `decision: pending`.
  Unmappable/unreadable/changed-mid-read bodies are listed, never guessed.
- **Provisional honesty.** Contradictions, topic gaps, outdated claims are
  `unavailable` with the exact missing-evidence reason; no paired quotes are
  ever synthesized into verdicts.
- **Writer observation state.** Per-post on-demand check runs the real
  deterministic D3 detector against live bytes and displays status, finding
  count/codes, digest binding, and limitations inline. The collection itself
  makes no Writer freshness claim beyond "observed just now".
- **Human review state.** Expanded rows show review counts with the latest
  decision/reviewer/timestamp from the existing reviews endpoint; full
  dossiers remain one click away in the existing PostDetail.
- **Navigation.** Collection → inline evidence → full post detail
  (existing component, reused) → existing evaluation/review flows. No
  parallel post UI was created.
- **ALIVE renderer.** `format_collection_text` carries map numbers verbatim
  (`NOT_RUN`/`unknown` wording, never zero); no measure, no authority.

## 4. Test results

- Mission: `test_mc_website_collection` (9), `test_mc_website_collection_api`
  (3), `test_mc_website_posts_context` (14), `test_mc_website_posts` (15),
  living-book represent/improvement/core (25) — all pass; related websites
  sweep totals **100 passed** with only the 2 known pre-existing
  date-sensitive cultivation failures (proven unrelated on the pristine
  base; untouched per brief).
- ALIVE: new collection-history (7) + quality-history (8) + living-book (7)
  + semantics (14 with slow tests included) = **36 passed**; `ruff`
  clean (the single pre-existing F841 outside D4 hunks left as-is).
- Frontend: **145/145** full suite (incl. 6 new CollectionTab tests);
  `tsc` clean.

## 5. Screenshots (`docs/images/mc-book-pipeline-01-d4/`)

Fixture site + fixture evaluations on an isolated backend (no prod data):

- `01-collection-overview.png` — stats strip (3 published, 1 current,
  1 stale, 1 not evaluated, 33% coverage, avg 800), needs-attention
  filtering, stale/unevaluated rows with digest pairs.
- `02-matrix-auto-tags.png` — per-post evidence expansion.
- `03-writer-check.png` — on-demand Writer observation: `complete`,
  0 findings, 11 dimensions, digest binding, native limitations.

Screenshots show fixture data (seeded `wpe-shot-*` evaluations) against an
isolated backend; no production content or history was touched.

## 6. Limitations

1. The collection map has no stored Writer history: per-post Writer state is
   observed on demand (deterministic, local, governed by click), never
   auto-run, never persisted. A stored Writer history (with append-only,
   digest-bound semantics) is future work, explicitly not started.
2. Only whole-collection refresh exists (`Refresh` re-reads the map); no
   per-post background refresh. Manual editorial evaluation stays in
   PostDetail.
3. Coverage counts published posts only, by design; drafts/scheduled/unknown
   are listed but never in denominators.
4. Quote matching is byte-exact (whitespace-normalized); paraphrase-level
   duplication is out of scope and never asserted.

## Verdict: D4 ACCEPTED (scoped as above)

Mission Control now presents one coherent, evidence-backed collection view
— editorial state with freshness per post, human review state, on-demand
Writer observations, duplication candidates as pending decisions, and
provisional sections honestly unavailable — reusing every existing
evaluation, review, and post-detail flow instead of duplicating them. No
ALIVE service changes were needed or made.
