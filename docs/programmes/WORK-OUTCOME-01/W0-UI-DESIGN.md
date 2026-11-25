# W0-UI-DESIGN — Activity → Work Evaluation tab

No UI built in W0. This specifies the integration so W5 has no new top-level app.

## 1. Placement

New tab under existing Activity page (`frontend/src/pages/ActivityPage.tsx:101
tab = commits|events` → `commits|evaluation|events`). Reuses `PageHeader/Section/Stat/Tag/
LoadingBlock/ErrorState/EmptyState/Modal/ProvenanceBadge`, `useApi + apiPath`, `copyText`,
existing Activity visual language (`.activity-feed`, `.activity-marker`).

Global cross-project view default; project-level filter narrows to one repo set.
Opening the tab triggers index queries only — never model calls (extends
`api/git_activity.py:1-5` invariant to new `/api/work-evaluation/*` routes).

## 2. Default view (operational, not wall-of-text)

Emphasise unfinished work + important unresolved gaps:

- Strip: episodes needing attention · mandatory obligations open · evaluated vs unevaluated/stale · evidence coverage.
- Tables (compact, expandable): Recent episodes (objective, project, outcome state, stale badge) ·
  Projects with unfinished work (open mandatory count) · Completed vs incomplete outcomes ·
  Unevaluated/stale episodes · Outstanding obligations (mandatory first) ·
  Evidence coverage (observed/tested/verified %) · Important quality findings (blocker/major only).
- Filters: project, repository, date, outcome (`not_started…complete/blocked/unknown`),
  review state, mandatory-only toggle, stale-only toggle, search (objective/requirement text).

## 3. Episode drill-down

Per episode: objective (source quote + locator) · requirements table (state + evidence links) ·
associated conversations (session list + redacted excerpts, deep-link to OpenCode session) ·
relevant message excerpts (≤800 chars, redacted) · commits (repo/sha/subject/stats + diff viewer reuse) ·
actual changes (first-parent diffs, truncation labelled) · existing code reviews (verdict + findings + feedback) ·
evidence/verification (test/review/demo rows with digests) · evaluation findings (dimension + reason + refs) ·
unresolved obligations (mandatory vs recommended) · recommended follow-ups (propose only, no auto-execute).

Reuse: `CommitDetailModal/PromptModal/ReviewModal/ReviewCard/RangeModal/RepoPanelModal`
patterns (ActivityPage 1050–1580), `GitDaily*` snapshot/stale pattern for episode staleness,
`research_chat` context-snapshot pattern for frozen evaluation inputs.

## 4. States/badges

Outcome badges: `NOT_STARTED/IN_PROGRESS/PARTIAL/IMPLEMENTED/VERIFIED/INTEGRATED/COMPLETE/BLOCKED/UNKNOWN`
+ `STALE` when source digest moved since evaluation. Requirement dots use rubric states (§W0-EVALUATION-RUBRIC).
`PARTIAL/TRUNCATED/REDACTED(n)` honesty labels carried from git/review builders.
`REPORTED ≠ VERIFIED` visually distinct (claim grey vs verified green).

## 5. API sketch (W5; names provisional)

`GET /api/work-evaluation/episodes?project&repo&outcome&stale&limit` ·
`GET /api/work-evaluation/episodes/{id}` (objective, requirements, associations, commits, evidence, evaluations, obligations, follow-ups) ·
`GET /api/work-evaluation/obligations?mandatory_only&project` ·
`GET /api/work-evaluation/coverage?project` ·
`POST /api/work-evaluation/episodes/{id}/re-evaluate` (explicit submit; queued, async, cached by digest) ·
`POST /api/work-evaluation/obligations/{id}/waive` (human + reason; confirm required).
All reads index-only. All model work async with `queued→running→completed|failed`, persisted rows re-readable.
