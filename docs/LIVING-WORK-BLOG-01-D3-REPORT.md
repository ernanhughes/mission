# LIVING-WORK-BLOG-01 — D3 Report: Writer Post Observation Path

**Status:** D3 implemented and verified. No commits, pushes, deployments,
live models, manuscript modifications, or stored Writer verdicts.
ALIVE needed no source change (D2 adapter covers post measures; verified by
new tests). D4 reported separately.

## 1. Scope (as authorized)

Implement the minimum verified path connecting a canonical Mission Control
blog-post identity to Writer's supported post-level observations:

- Real deterministic Writer Artifact detector output for real post bytes.
- Mission stays authoritative for identity, editorial evaluation, reviews,
  storage, freshness, and human decisions.
- `scoring` and every non-qualified provider rejected at the schema boundary.
- No automatic execution; the single new endpoint is manually invoked.
- ALIVE presents Writer evidence only where D2 already authorizes the
  `mission.site.post.evaluations` measure — no new ALIVE wiring.
- `absent_now` semantics preserved end to end.

Explicitly **not** done (carried, not dropped): no stored Writer
per-post history (freshness of Writer observations is meaningful only at
observation time); no QC `compile_document` routing for posts (D3 uses the
D2 post splitter); `text_sha256` stays a non-authoritative hint; byte-exact
spans are not claimed; no frontend for the observation itself (D4 covers
presentation).

## 2. Files changed (Mission)

| File | Change |
|---|---|
| `backend/mission_control/websites/post_artifact.py` | NEW. `build_artifact_envelope` (pure: body bytes → validated envelope), `artifact_envelope_for_live_post` (canonical identity → live split → envelope; `None` when unmappable; `NotFound` for unknown identities), `_unavailable_envelope` (decoder/detector failure → `unavailable`, never fabricated). The deterministic Writer Artifact module is imported read-only from the Writer checkout (stdlib-only: hashlib/logging/re/collections/dataclasses/pathlib/typing — verified no model imports), cached, with an env override and an explicit refusal to substitute copies. |
| `backend/mission_control/api/website_posts.py` | +1 endpoint: `POST /{site}/posts/{identity}/writer-observation` → validated envelope, 404 unknown, 422 unmappable, `unavailable` envelope for undecodable bodies. No storage, no manuscript writes. |
| `backend/tests/test_mc_website_post_artifact.py` | NEW (12 tests, ported byte-identical from the verified D3 spike). |
| `backend/tests/test_mc_website_post_observe.py` | NEW (5 tests): endpoint contract, 404/422 paths, unavailable-never-current, no DB writes, no manuscript changes, no editorial fields in Writer output. |

ALIVE: `tests/test_blog_post_quality_history.py` ported (5 tests); zero
source changes (the D2 `ACCEPTED_MEASURE_IDS` adapter already associates
post measures).

## 3. API contract

`POST /api/websites/{site}/posts/{identity}/writer-observation` →
`writer.evaluation-envelope.v1`-shaped JSON (validated by the D2
`validate_post_envelope` path before return):

- `work_object`: `{kind: "post", target_id, source_hash}` (sha256 of the
  **evaluated body bytes**), `content_sha256` (raw file bytes, authoritative
  for location), `text_sha256` (body hint, never authoritative),
  `body_offset_bytes`, `relpath`.
- `producer`: `{runtime_name: "artifact", method: "analyze_text",
  method_version: "writer-artifact-detection.v1"}`.
- `status`: `complete` | `empty` | `unavailable`; `findings[]` with
  body-relative `start_line`/`end_line` native evidence plus an explicit
  non-byte-exact marker; `dimensions[]` with Writer native scales verbatim;
  `limitations[]` on every envelope.

## 4. Verified behavior (real detector, deterministic fixtures)

- Byte binding: envelope `source_hash` equals the sha256 of the exact
  evaluated body (`split_post_body` output), `content_sha256` the raw file;
  raw and evaluated hashes never interchanged, including the
  front-matter-boundary case.
- Determinism: identical inputs → byte-identical envelopes (stable derived
  evaluation ids; no timestamps inside the compared payload).
- Failure honesty: undecodable bodies and detector exceptions yield
  `unavailable` envelopes bound to the observed bytes; unmappable bodies
  yield `None` → endpoint 422; unknown identities 404. Nothing becomes
  `current` without matching evidence.
- No second scorer: envelopes carry no `overall`/scores; `scoring`
  providers rejected by the D2 validator; dimensions use Writer-native
  scales without rescaling or cross-provider math.
- Span honesty: every finding carries `span.available: false` with reason;
  a whole-envelope walk test fails the suite if any byte-offset key is ever
  introduced.
- Provenance recorded: `persist: false`, `in-memory run on extracted post
  body bytes`, `no model, no writes`, detector/paragraph counts.
- End to end: live post → envelope → `build_site_post_context` carries a
  Writer measure beside the editorial measure; force-link/`previous_evaluation_id`
  chain intact; renames stay isolated; hostile/malformed inputs fail safe.

## 5. Test results

- `test_mc_website_post_artifact.py`: **12/12**.
- `test_mc_website_post_observe.py`: **5/5**.
- Regression: `test_mc_website_posts` (15), `test_mc_website_posts_context`
  (14), living-book represent/improvement/core (25) — all pass; related
  websites sweep totals **100 passed** with only the 2 known pre-existing
  date-sensitive cultivation failures (proven unrelated on the pristine
  `df08852` base; untouched per brief).
- ALIVE: `test_blog_post_quality_history` **5/5** against current main.
- `ruff check` / `ruff format --check` clean on all new/changed files.

## 6. Limitations

1. Envelopes are computed on demand and returned, never stored: there is no
   Writer per-post history, so Writer freshness exists only at observation
   time. A future stored history must be append-only and digest-bound.
2. Post scope only: the deterministic detector analyzes the extracted body
   as one unit; per-section attribution beyond native line spans is not
   claimed.
3. The Writer checkout path defaults to `C:/Projects/writer` with an env
   override; a missing detector fails loudly instead of substituting an
   implementation.

## Verdict: D3 ACCEPTED (scoped as above)

The minimum verified Writer-post path exists and is independently tested on
both sides. No ALIVE service changes were needed or made.
