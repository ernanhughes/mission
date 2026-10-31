# MC-WRITER-02 evidence

Generated 2026-10-25 against the live Writer Editing runtime, the live
Workbench at `127.0.0.1:7420`, and Mission Control at `127.0.0.1:8790`.

The pilot book is **Inference**, chosen by the author after the Language
Chapter 3 workflow. No manuscript text was changed by this slice.

## What was verified

- Writer audited Inference read-only: report
  `edit-20261025T231633334069Z-904c13cd0598`, 45 chapters, 149 findings, no
  errors. The source is dirty because the author has uncommitted chapter work;
  that is shown, not hidden.
- Finding identity is Writer-owned. Every Inference finding has an
  `edfinding:` id; re-auditing the same evidence keeps the ids.
- Mission Control grouped 2,425 Writer findings across the registered books into
  197 groups and ordered the book open in Workbench first.
- A whole-book refresh from Workbench produced a 45-chapter report, not a
  one-chapter replacement, so the queue stayed complete.
- The first Inference group is 23 high `READABILITY.LONG_SENTENCE` findings
  across 23 chapters. Its representative is Chapter 9, line 12.
- Opening **Open in Workbench** loaded the exact finding: the chapter was
  current, the evidence drawer was open, the finding card was open and the
  passage was highlighted.
- No Apply control exists in the Editing panel. Accepting a rewrite remains a
  separate proposal/check/Apply path.
- Mission Control only read Workbench's decision log. It did not create a
  decision.

## Screenshots

| File | Scenario |
| --- | --- |
| `mission-control-decision-queue.png` | Grouped queue; Inference first, switch note for other books |
| `workbench-deep-link.png` | Exact finding card open, passage highlighted |
| `workbench-book-audit.png` | Whole-book audit preserves all 45 chapters |
| `mission-control-writer-full.png` | Full Writer page after the queue was added |

## Machine-readable evidence

| File | Contents |
| --- | --- |
| `runtime-evidence.json` | Writer report ids, queue totals, top groups, deep-link target |
| `deep-link-verification.json` | Browser state after following the first link |
| `writer-editing-tests.txt` | Writer Editing runtime and bridge tests |
| `writer-ruff.txt` | Writer Ruff result |
| `workbench-focused-tests.txt` | Workbench Editing/page tests |
| `workbench-full-tests.txt` | Workbench full suite |
| `mission-control-backend-tests.txt` | Mission Control backend |
| `mission-control-frontend-tests.txt` | Mission Control frontend |
| `mission-control-frontend-build.txt` | Production build |
| `mission-control-ruff.txt` | Mission Control Ruff result |


## Review disposition

An independent agent review returned **ACCEPT WITH CHANGES**; a targeted
re-review after the corrections returned **ACCEPT**. The corrections are in the
working tree and covered by the final test logs:

- passage-scope precedence is now explicit in both decision readers;
- Workbench refreshes whole-book evidence and displays scope/chapter count;
- stale source fingerprints lock decisions and remove passage highlights;
- the Writer JSON schema includes `finding_id` and a report validates against it;
- deep links distinguish not-run, unavailable, wrong-chapter and missing-finding
  states;
- partial/error evidence is not shown as a clean empty result;
- `not_run` and `chapter_not_in_report` keep their real states instead of being
  rewritten as stale;
- finding ids no longer sit inside inline JavaScript handlers.

The final clean Workbench suite after these corrections is **1025 passed**.
The reviewer's concurrent-run failures were not reproduced in the clean run.

## Boundaries

- The queue is a reading order, not a composite quality score.
- A grouped decision is representative, not proof that every instance is the
  same editorial problem.
- Workbench must be on the same book; other books show a switch instruction.
- Stale evidence gets no decision link.
- Real author decisions have not yet been recorded in the production log. The
  screenshots show the queue and link, not an invented Confirm/Dismiss/Defer.
- No threshold change, paid inference, model download, publishing or commit was
  part of this slice.
