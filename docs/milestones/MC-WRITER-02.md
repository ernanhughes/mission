# MC-WRITER-02 - Writer decision queue and Workbench deep link

## Scope

Turn Writer's read-only editing evidence into a prioritized editorial queue
without making Mission Control a second scorer.

- Writer owns the stable finding identity (`edfinding:…`) in the editing runtime.
- Mission Control consumes Writer's summary, groups repeated findings by
  `(book, code, severity)`, and selects an earliest representative.
- Mission Control reads Workbench's append-only decision log read-only and
  applies Workbench's scope precedence: passage, then chapter, then book.
- The book currently open in Workbench is queued first, so "Open in Workbench"
  is immediately actionable. Other books show a switch instruction instead.
- Workbench accepts an exact finding deep link and opens the named finding; it
  refuses an id that is absent from current evidence.

No manuscript was edited, no threshold changed and no model call was made.


## Configuration

Mission Control reads, and never writes, these Workbench files:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MISSION_CONTROL_WORKBENCH_DECISIONS` | `C:\Projects\workbench\.workbench\editorial-decisions.jsonl` | Workbench's append-only decisions |
| `MISSION_CONTROL_WORKBENCH_PREFERENCES` | `C:\Projects\workbench\.workbench\preferences.json` | Workbench's selected book |
| `MISSION_CONTROL_WORKBENCH_URL` | `http://127.0.0.1:7420` | Deep-link base URL |

If a file is missing or unreadable, the queue still shows Writer findings and
marks them undecided; it does not invent a decision or hide the absence.

## Results

| Check | Result |
| --- | --- |
| Workbench full suite | 1025 passed |
| Workbench Editing/page focused | 126 passed |
| Writer Editing runtime + bridge | 24 passed |
| Writer Ruff | passed |
| Mission Control backend | 71 passed, 1 skipped (Docker unavailable) |
| Mission Control frontend | 32 passed |
| Production frontend build | passed |
| Real Inference audit | 45 chapters, 149 findings, no errors |
| Decision queue | 197 groups, 2,425 undecided findings |
| Inference groups | 8; first is 23 high long-sentence findings |
| Deep link | Inference Chapter 9 opened with the exact finding card and passage highlight |
| Manuscript mutation | none by this slice |

## Acceptance scenarios

1. Writer report findings carry stable `edfinding:` ids.
2. Re-auditing the same evidence keeps the ids; a changed locator changes the id.
3. Mission Control groups repeated findings rather than listing all 2,425.
4. The representative is the earliest chapter and locator in the group.
5. The book open in Workbench is ordered first.
6. A book-scope Workbench decision marks every instance decided.
7. A chapter-scope decision produces a truthful partial group.
8. Stale evidence gets no decision link.
9. Mission Control never writes the Workbench decision log.
10. Workbench opens the exact finding and highlights its passage.
11. A missing finding id produces an explicit message and no invented card.
12. No manuscript changes during the queue, link or decision-state read.

## Evidence

- [Acceptance report](../acceptance/mc-writer-02/REPORT.md)
- `mission-control-decision-queue.png`
- `workbench-deep-link.png`
- `deep-link-verification.json`
- `runtime-evidence.json`
- Test logs in `docs/acceptance/mc-writer-02/`


## Independent review

An independent agent review of the Workbench and Writer working trees returned
**ACCEPT WITH CHANGES**; a targeted re-review after the corrections returned
**ACCEPT**. The material findings were corrected before this record:

- a later book decision could override an earlier passage decision; the passage
  bucket now requires `scope=passage` in both Workbench and Mission Control, with
  regression tests;
- a Workbench chapter audit could replace the book's latest report with a
  one-chapter report; Workbench now asks Writer for a whole-book audit and shows
  report scope and chapter count;
- a stale or mismatched chapter could still highlight the wrong paragraph and
  offer decisions; Workbench now compares the pinned chapter's SHA-256 with
  Writer's source fingerprint, locks decisions, removes markers, and checks the
  excerpt against the mapped block;
- the static Writer report schema rejected `finding_id`; the field is now in the
  schema and a written report is validated against it;
- deep-link state messages, partial/error display and dynamic finding ids in
  inline JS were tightened;
- a corrected source check no longer rewrites `not_run` or
  `chapter_not_in_report` as stale;
- narrow-screen activity notifications are suppressed while the evidence drawer
  is open.

The reviewer did not claim human independence. A genuinely blind human review
remains outstanding.

## Recommendation

**ADOPT** the grouped queue and exact-finding deep link for bounded editorial
triage. **DEFER** automatic candidate generation and before/after report
comparison until the author has recorded real decisions.

The queue is a reading order, not a quality score. A decision records editorial
triage; it does not prove improved reader comprehension.
