# MC-LIVING-BOOK-01 — Living Book reading room

## Outcome

Mission Control can open a book's actual manuscript, keep the reader's place,
retain notes, and answer questions with ALIVE while preserving the existing
quality evidence.

The first connected books are **Distillation From First Principles** (whole
read-only repository, so the companion can read planning/editorial evidence) and
**Language: When Intelligence Enters the Channel** (manuscript source plus Writer
readability evidence).

This is not a replacement for the existing project analytics. The project page
keeps checkpoints, quality maps, technical evidence and readiness. The reading
room is an additional surface.

## Architecture

```text
React reading room
  -> /api/living-book/projects/{project_id}       Mission gateway
       -> http://127.0.0.1:8000/api/v1/living-books ALIVE engine
            -> approved project source, workspace conversation,
               bounded Pi/Meta session, event ledger
```

- **ALIVE owns:** source custody, exact chapter reads, reading state,
  annotations, living notes, conversations, model sessions and receipts.
- **Mission owns:** project/book mapping, source connection/approval UI, quality
  context assembly, chapter image serving and presentation.
- **No new Mission database table** and **no new ALIVE database migration**.
- **No manuscript writes.** There is no write path to chapter files.

## Quality context

Mission builds a bounded `book-quality-context.v1` snapshot from existing
evidence:

| Measure | Source | Status handling |
| --- | --- | --- |
| Prose evaluation | Mission `quality_evaluations`, `manuscript-prose-v1` | `CURRENT`, `STALE`, `NOT_RUN`; six dimensions with quotes and limitations |
| Writer readability | Writer editing reports ingested by Mission | `CURRENT`, `STALE`, `NOT_RUN`, `UNAVAILABLE`; six independent subdimensions and findings |
| Technical claims | Mission technical workspace | claim counts, verification, coverage and gaps |
| Publication readiness | Mission publication assessments | gate/freshness state; missing is `NOT_RUN` |
| Artifact Load | Mission observations | independent burden observation |

Rules enforced by the context and prompt:

- no invented composite score;
- no averaging across incompatible rubrics;
- `NOT_RUN` is never displayed as zero;
- `STALE` is never presented as current;
- a model score is not a publication verdict;
- quoted evidence is not independently verified merely because it is quoted.

The quality panel in the reading room is deterministic Mission data. ALIVE only
explains or connects it when asked. Quality and reader context travel as
untrusted owner-supplied context, not as part of the visible question; a model
can cite exact evidence as `owner-context:quality` or `owner-context:reader`,
and ALIVE's verifier checks those quotes against the supplied context.

## Mission API

All routes are under `/api/living-book`.

| Method | Route | Meaning |
| --- | --- | --- |
| `GET` | `/projects/{project_id}` | Truthful reading-room state, candidates and quality summary |
| `GET` | `/projects/{project_id}/candidates` | Eligible source roots with bounded size preview |
| `POST` | `/projects/{project_id}/connect/preview` | ALIVE source preview for one candidate |
| `POST` | `/projects/{project_id}/connect` | Explicit read-only approval, registration and book creation |
| `GET` | `/projects/{project_id}/book` | ALIVE book detail |
| `GET` | `/projects/{project_id}/chapters/{chapter_id}` | Verified chapter text |
| `PUT` | `/projects/{project_id}/reading` | Persist reading position |
| `GET/POST/DELETE` | `/projects/{project_id}/annotations` | Retained quotes and notes |
| `GET/POST` | `/projects/{project_id}/notes/{chapter_id}` | Living note |
| `POST` | `/projects/{project_id}/ask` | Quality-aware chapter/book question |
| `GET` | `/projects/{project_id}/conversations/{conversation_id}` | Conversation detail |
| `GET` | `/projects/{project_id}/quality` | Bounded quality context |
| `POST` | `/projects/{project_id}/refresh` | Explicit live-source refresh |
| `POST` | `/projects/{project_id}/sessions/{consent_ref}/revoke` | Revoke the bound model session |
| `GET` | `/projects/{project_id}/assets` | Contained book image serving |

The ALIVE base URL comes from the registered `alive` application's
`adapter_config.base_url` or `MISSION_CONTROL_ALIVE_URL`. It must be loopback.
No browser-supplied URL becomes an outbound target.

## Source connection

`POST /connect` requires `approve: true`. The UI presents the candidate root and
a consent checkbox before calling it. Mission then:

1. calls ALIVE's project preview;
2. registers the folder if needed;
3. posts an owner source approval for read-only `live` access (30 days);
4. registers the Living Book against the approved binding.

Registration does not copy manuscript bytes into Mission. The approval can be
revoked in ALIVE.

Candidate roots are bounded before preview:

- the manuscript folder is always offered;
- the whole repository is offered only if a capped local scan is under the
  preview limits;
- Distillation's whole repository is recommended because it contains
  `planning/`, `editorial/`, `research/` and `experiments/` evidence.

## Reading room

Route: `/projects/:projectId/read`

- chapter index with word counts and changed-chapter state;
- rendered chapter: front matter stripped, headings, lists, quotes, tables,
  code, images, Hugo `bookfig` shortcodes, KaTeX math and Mermaid diagrams;
- ALIVE companion: chapter or whole-book scope, retained conversation,
  citations, model session usage and revocation;
- notes tab: generated living note, retained annotations and selection actions;
- quality tab: coverage, current prose dimensions, weakest chapters and
  limitations, with an “Ask ALIVE about quality” action;
- continue/reading state restored after restart.

Images are served through Mission with strict containment and an image-only
allowlist. Unknown shortcodes are not executed.

## Entry points

- A **Living Book** card at the top of every book project workspace.
- The card shows last-read chapter, current quality coverage and readiness, and
  links to the reading room.
- Books that are not connected offer the explicit connection flow.

## Failure states

| State | What the reader sees |
| --- | --- |
| `unavailable` | ALIVE is not running; link to Applications. Existing project evidence still works. |
| `not_connected` | Candidate source roots and explicit read-only approval. |
| `needs_source` | Source changed or no longer usable; explicit refresh action. |
| `model_unavailable` | Reading, notes and quality still work; the companion reports the model is unavailable. |
| Chapter changed | 409 from the chapter route; no stale bytes are shown as current. |
| `NOT_RUN` / `STALE` | Displayed as such; never converted to zero or current. |

## Focused verification

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q backend\\tests\\test_living_book.py
cd frontend
npm test -- src/test/LivingBookPage.test.tsx
npm run build
```

Real acceptance is recorded in [mc-living-book-01](acceptance/mc-living-book-01/README.md).
