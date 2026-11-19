# MC-LIVING-BOOK-01 acceptance — Distillation reading room

**Date:** 2026-11-19
Scope: Phase 1 Living Book engine, Mission gateway, Distillation reading room,
quality context and real-model companion; Language source registration.

This was a local, loopback-only acceptance run. The manuscript was not modified.

## Setup

- ALIVE backend: `C:\Projects\alive\.venv\Scripts\python.exe -m alive.server --host 127.0.0.1 --port 8000`
- Mission Control: `C:\Projects\mission\.venv\Scripts\python.exe -m mission_control --host 127.0.0.1 --port 8790`
- Model: `muse-spark-1.3-contributor` through the existing Pi transport.
- Distillation source: `C:\books\distillation` approved read-only as a live project source.
- Distillation manuscript root: `C:\books\distillation\content\books\distillation`.
- Language source: `C:\books\language\content\books\language` approved read-only as a live project source.
- Language manuscript root: the same folder.

Both source approvals are 30-day, read-only, revocable ALIVE owner approvals.
The Distillation whole-repository source gives ALIVE access to the chapters plus
`planning/`, `editorial/`, `research/` and `experiments/` evidence.

## What was verified

### Book projection

- Distillation registered as one Living Book with **42 chapters**, all `current`.
- Chapter 14 resolved to **“Synthetic Data Generation”**, 4,067 words, with one
  Markdown figure at `/images/books/distillation/ch14/birthday.svg`.
- Mission served the figure through its contained asset route:
  `200 image/svg+xml`, 3,940 bytes.
- Language registered with **39 chapters**, all `current`; chapter 01
  “The Interface Between Minds” resolved with two Hugo `bookfig` diagrams, both
  served by Mission through the same contained route.

### Quality context

Distillation Mission quality summary from the real database:

```text
rubric manuscript-prose-v1
chapters_current 42 / 42
overall range 3.00–4.17
dimension means:
  clarity 3.74, argument 3.95, precision 3.76,
  economy 2.90, voice 3.86, structure 3.95
lowest chapters: 14 (3.00), 33 (3.00), 23/28/32/35 (3.33)
technical: NOT_RUN
publication: NOT_RUN
```

Chapter 14 quality context:

```text
overall 3.0
clarity 3, argument 4, precision 3, economy 2, voice 3, structure 3
limitations include:
  Single-run model judgment; repeatability not established by one observation.
  token usage recorded by execution record when available.
```

Language quality context:

```text
prose: NOT_RUN (0 / 0)
Writer readability: CURRENT at book level
chapter 01 Writer observation: STALE (report fingerprint predates the current manuscript)
technical: NOT_RUN
publication: NOT_RUN
```

The reading room does not turn any of these into a composite score.

### Real-model companion answer

Question:

> Why did this chapter receive an overall prose score of 3.0? What does that
> score actually establish, and what should I fix before publication?

Answer excerpt:

> Chapter 14 received 3.0 on mission.prose.manuscript-prose-v1 because it is the
> equal-weight mean of 6 dimensions: clarity 3, argument 4, precision 3,
> economy 2, voice 3, structure 3. … Economy 2 is the drag; argument 4 is the
> only strength. … It is single-run: repeatability not established by one
> observation. … mission.writer.readability, mission.technical.claims,
> mission.publication.readiness and mission.artifact_load are all NOT_RUN.
> NOT_RUN is not zero, not a pass, not approval. Do not average across rubrics.
> … Publication gate still missing: you need writer readability, technical
> claims verification, artifact load, and a gate decision.

Evidence from the response:

- `quality_used: true`
- **6 citations** from the chapter
- **3 model calls**, all `validated`
- **28,590 charged tokens**
- session `approved`
- answer explicitly names the quality measure ids, single-run limitation and
  missing publication/technical gates

A second real question was run after the reading session was tightened to a
smaller bounded envelope:

> Name the one quality dimension this chapter should improve first, and say why
> in one sentence.

The answer was `economy`, citing the 3.0 overall and the `economy: 2` dimension
against the 42/42 current coverage and the four `NOT_RUN` measures. Receipts:

- **2 model calls**, `validated`
- **15,168 charged tokens**
- session `2 / 50 calls`, `15,168 / 1,000,000 tokens`, `approved`
- **2 citations** from the chapter

The companion also read the chapter's matching
`planning/14-chapter-evidence.md` record and reported its status:
`CH14_DRAFT_TECHNICALLY_CHECKED`, `draft=true`, not publication-approved.

### Quality-only question and clean visible history

A quality-only question initially exposed two real defects: the quality evidence was
stored in the visible user message, and ALIVE withheld an answer that relied on
quality evidence without a manuscript citation.

Both were fixed in ALIVE's existing owner-context path:

- reader context and quality evidence are now `owner_supplied` context entries,
  not part of the visible question;
- a model may cite exact owner-context evidence with
  `owner-context:reader` or `owner-context:quality`;
- the existing verification still rejects fabricated or unobserved quotes.

Final live question:

> Is the economy score a verified fact or a model judgment? One sentence.

Answer:

> The economy score of 2 is a single-run model judgment, not a verified fact.

Receipts:

- **1 model call**, session `1 / 50 calls`
- **2 citations** with `document_id: owner-context:quality`
- visible user message: **71 characters**, no quality JSON
- browser history rendered the clean question and the answer

### Living note

Chapter 14 note generated through the same governed path:

- model `muse-spark-1.3-contributor`
- 3,095 Markdown characters
- 6 citations
- retained `current` against chapter revision
  `ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05`
- sections: `What this chapter is doing`, `Key moves`, `Questions to carry
  forward`, `Quality read`

### Reading state and annotations

- Saved chapter 14 at `progress=0.37`.
- Kept one annotation:
  “Plenty is cheap; coverage, correctness, and provenance are what have to be
  earned.”
- Restarted the ALIVE backend.
- Reopened the project through Mission: reading state, annotation, note and
  conversation were still present.

### Source truthfulness

- A changed chapter is refused by ALIVE with a 409 and a “Refresh the book
  source” message. It is never served as current bytes.
- Source reconciliation is an explicit `POST /refresh`; questions use the exact
  captured revision with per-file hash verification.
- The first acceptance attempt exposed a live-source lock deadlock between
  `chat.prepare` and the live-binding refresh. The reading path now uses ALIVE's
  existing exact-capture context and an explicit refresh route. The deadlock was
  observed in a real request, fixed, and the acceptance was rerun successfully.

## Tests

```powershell
# ALIVE
.venv\Scripts\ruff.exe check alive\living_book tests\test_living_book.py
.venv\Scripts\python.exe -m pytest -q tests\test_living_book.py -o addopts=""
# 7 passed

# Mission backend
.venv\Scripts\python.exe -m pytest -q backend\tests\test_living_book.py
# 6 passed

# Mission frontend
npm test
# 83 passed
npm run build
# production build succeeded
```

A full Mission backend run on the same day passed **499 tests with 1 skip**. Five
environment-dependent tests outside the Living Book path failed (editor launch
probe, quality-evaluator availability, two cultivation Git-date probes and a
weekly-script clock assumption) and one Pi-critique test errored in the local
setup. Those are reported, not hidden, and were not modified for this feature.

## Limitations

- This acceptance used HTTP/API, unit/build evidence, and a live Chrome load of
  `/projects/distillation/read`. The live page exposed the 42-chapter index,
  chapter 14 text, source/ALIVE status and the existing reading state. A
  screenshot could not be captured because the browser window could not be
  focused in this environment; the accessibility tree and rendered text were
  inspected instead.
- The live load exposed one real UI integration defect: KaTeX's bundled font
  data URI was blocked by the application CSP. Mission's application CSP now
  allows `font-src 'self' data:`; the font error is gone.
- The live Quality tab displayed the deterministic coverage chips, the current
  `3 / 5` prose observation, all six dimension scores with evidence lines, the
  lowest chapter observations, and the limitations. The browser console was clean
  after the CSP fix. The companion history showed only the question and answer,
  not the quality JSON.
- The prose observations are single-run model judgments. The acceptance shows
  the companion represents that limitation; it does not establish repeatability.
- Writer readability for Language chapter 01 is `STALE`; the reading room shows
  that state and does not treat it as current.
- Technical verification and publication readiness are not populated for either
  book, so the companion reports them as `NOT_RUN`.
- The authoring actions (chapter review/improvement proposals) are not part of
  this Phase 1 acceptance; they remain the next phase.
