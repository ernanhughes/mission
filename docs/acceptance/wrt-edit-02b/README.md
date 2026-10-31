# WRT-EDIT-02B evidence

Status: **manual 50-passage exercise stopped at 10/50.** The partial labels are
preserved as an AI-assisted pilot. Workbench now has a native Editing stage with
Readability as its first lens, grouped representative review, a Writer
before/after report comparison and finding-linked candidate **Better / Same /
Worse** verdicts; no thresholds have been changed. An independent review returned
**PASS_WITH_CORRECTIONS**; the scope-integrity, menu-overflow and candidate
verdict corrections passed targeted re-reviews. Receipt-to-finding/candidate
linkage is implemented and needs its own independent review before calibration
export begins.

## Accepted baseline

- 27 distinct manuscripts
- 799 distinct chapters
- 2,271 distinct findings
- `digital-life` canonical; `programmer_ie` publication copy
- Seven accessible projects remain under `C:\Projects`
- 50 passages prepared for independent review

## Workbench-native review

- Workbench **Editing** action: `C:\Projects\workbench\src\workbench\static\index.html`
- Writer evidence bridge: `C:\Projects\writer\packages\writer-web\writer_web\routes\editing.py`
- Writer finding identity: `C:\Projects\writer\packages\writer-runtime\writer_runtime\domains\editing\identity.py`
- Workbench decisions: `WORKBENCH_HOME/editorial-decisions.jsonl`
  - each record copies Writer's dimension, subdimension, severity, report
    profile/version, partial flag and fingerprints at decision time; the client
    cannot supply those calibration fields
- Product plan: `C:\Projects\writer\docs\analysis\WRT-EDIT-02B-PLAN.md`
- Workbench documentation: `C:\Projects\workbench\docs\workbench-editing-stage.md`
- Screenshots: `workbench/workbench-editing-language-ch3.png`,
  `workbench/workbench-editing-language-ch3-confirmed.png`

Language Chapter 3 is the first before/after workflow example. Its chapter-level
rhythm finding can be confirmed, dismissed, deferred, or used to prepare a
bounded revision prompt. Whole-book evidence was refreshed on 26 October 2026 as
`edit-20261026T102047910150Z-e41af713be96` (39 chapters, current, clean source,
no errors). Chapter 3 again has one medium chapter-level
`READABILITY.UNIFORM_CADENCE` finding, no invented passage locator. The
comparison with `edit-20261025T222102894024Z-35ddc68f54aa` showed no measured
difference in word/paragraph/sentence counts, dimensions, finding count or codes.
That is recorded as a truthful result, not a pass: it does not prove the revision
had no effect, and it cannot attribute a difference to one edit. Refreshing the
evidence did not accept the revision's voice. No manuscript text was changed.

Repeated findings are now clustered by Writer's finding code in Workbench. The
highest-severity case is the representative; remaining cases stay behind a
details control, with a flat/grouped toggle. This supports the Mission Control
queue without turning 2,271 findings into 2,271 required decisions. A controlled
non-production fixture with three same-code findings of different severities
covers representative selection, expansion, deep-link opening of a collapsed
group and coverage counts after a chapter-scope decision; no Language decisions
were created to test it.

The independent review's scope-integrity correction is implemented. A
chapter-level finding with no passage locator hides the passage option, defaults
to the chapter pattern, and is refused server-side if a passage scope is forged.
A located passage finding keeps the passage default. The live Language Chapter 3
panel showed only the chapter and book options, with the chapter pattern
selected. The review also found the Editing menu overflowing the right edge at
1422 px; the menu is now anchored to the action bar's right edge with
`max-inline-size: calc(100vw - 16px)`. A real-browser check found no horizontal
document overflow at 1280, 1366, 1422 or 1440 px; the menu is hit-testable above
the evidence drawer when deliberately opened.

The candidate-verdict slice is now implemented. **Prepare revision** attaches the
current finding and report identity to the next turn; a proposal from that turn
shows its finding and asks **Better / Same / Worse**. The verdict is append-only
in `WORKBENCH_HOME/editorial-candidates.jsonl`, binds to the exact candidate
wording by SHA-256, copies the dimension, severity and report profile context,
and never applies or authorises an edit. Editing the wording keeps the old
verdict as history but marks it as not current. The send is refused if the report
or chapter source changed after preparation, and retries carry the original
turn's link. The over-budget confirmation path preserves the resolved link,
including when a newer composer handoff exists and when the retry was unlinked.
The complete visible flow is exercised on a controlled confirmed fixture, not a
Language decision. No production candidate verdicts were created.

Receipt-to-finding/candidate linkage is now implemented on the existing journaled
Apply path. Immediately before mutation, Workbench revalidates current Writer
evidence, the finding, report/source fingerprints, the exact candidate hash and
any recorded verdict. Refusal leaves the proposal unapplied. The frozen receipt
carries an optional `workbench.editorial-link/1` object containing the finding,
evidence, candidate hash, effective decision and verdict; existing top-level
receipt fields retain the operation, commit, file/paragraph hashes and undo
reference. Ordinary unlinked proposals still apply with an unlinked receipt.
The Applied card shows the chain and states that Apply, not the verdict, changed
the manuscript. Mutation tests used controlled fixtures only; no Language
decision, verdict, turn or manuscript change was created.

The author then moved the larger live queue to **Inference**, using the Language
workflow and lessons. Writer's Inference report is
`edit-20261025T231633334069Z-904c13cd0598` (45 chapters, 149 findings, dirty
source visible). Mission Control groups the findings and opens the exact
representative finding in Workbench. See
[MC-WRITER-02](../mc-writer-02/REPORT.md) for the queue, deep link and
verification evidence.

## Review packet (historical)

- `WRT-EDIT-02B-blind-review-packet.zip` — download packet
- `review-packet/calibration-blind-passages.csv` — 50 text-only passages
- `review-packet/calibration-review-template.csv` — 50 blank assessment rows
- `review-packet/README-review.md` — reviewer instructions with no diagnostic key
- `review-packet/PACKET-MANIFEST.json` — file hashes

Packet integrity:

| File | SHA-256 |
| --- | --- |
| `calibration-blind-passages.csv` | `f768eb800381105c80dcec432c4fc58387e90bf34322297bc1bd0bef8d8fee24` |
| `calibration-review-template.csv` | `28830c74662da3080abe7ddf8a86197055698203dd93de2eafdb7a2bdb39e6df` |

The packet contains no book names, diagnostic categories, Writer scores or
findings. It contains no labels.

## Button review app

- `WRT-EDIT-02B-review-app.zip` — self-contained HTML reviewer
  - SHA-256: `812BE2B8067318AA501DA59D2CAE3085882D30A559AC31550BDE929C4D20B577`
- `review-app/WRT-EDIT-02B-review.html` — open directly in a browser
- `review-app/README-review-app.md` — app instructions
- `review-app/APP-MANIFEST.json` — app hashes and scope

The app opens in **five sets of 10 passages**. Score with buttons, click Next,
and at the end of a set download a CSV. The CSV always has 50 rows in `P01`–`P50`
order; unscored rows are blank, so a 10-passage review produces a valid partial
CSV. Answers autosave in the browser. The app contains no book names,
diagnostic categories, Writer scores or findings, and makes no network requests.

The frozen blind packet remains the canonical evidence; the HTML app is a
convenience layer over the same 50 passages. **The manual exercise is closed**
and is preserved for the pilot record, not for completion or threshold tuning.

## Workbench engineering health

| Check | Result |
| --- | --- |
| Workbench full suite | **1083 passed** (`engineering-health/workbench-full-tests.txt`) |
| Workbench Editing/page focused | **163 passed** (`engineering-health/workbench-editing-focused-tests.txt`) |
| Writer Editing runtime + bridge | **26 passed** (`engineering-health/writer-editing-tests.txt`) |
| Candidate verdict store and linked flow | **9 passed** (`tests/test_candidates.py`) |
| Receipt linkage | **8 passed** (`tests/test_editorial_receipts.py`) |
| Writer receipt schema and route | **46 passed** (`engineering-health/writer-receipt-tests.txt`) |
| Workbench menu widths 1280-1440 | no horizontal overflow (`engineering-health/workbench-menu-widths.json`) |
| Live Language Ch3 scope | chapter default, passage absent (`engineering-health/workbench-language-ch3-scope.txt`) |
| Live Language Ch3 revision handoff | finding/report linked, chip visible, no console exceptions (`engineering-health/workbench-language-ch3-handoff.txt`) |
| Live stale linked send | HTTP 400, zero turns recorded (`engineering-health/workbench-language-ch3-stale-handoff.txt`) |
| Live read-only receipt-stage check | 0 turns, 1 undecided, no decision/verdict logs (`engineering-health/workbench-language-readonly-receipt-stage.txt`) |
| Live forged passage scope | HTTP 400, no decision recorded (`engineering-health/workbench-language-ch3-forged-scope.txt`) |
| Writer Ruff on bridge and runtime | passed (`mc-writer-02/writer-ruff.txt`) |
| Mission Control backend | **71 passed, 1 skipped** (`mc-writer-02/mission-control-backend-tests.txt`) |
| Mission Control frontend | **32 passed** (`mc-writer-02/mission-control-frontend-tests.txt`) |

The Workbench suite includes the action strip, evidence panel, paragraph
highlight, chapter-level finding behaviour, scoped decision, revision handoff,
explicit audit and exact-finding deep link. The Writer tests cover the read-only
evidence route, Writer-owned finding identity and the existing editing runtime.
The Mission Control tests cover grouping, scope precedence, decision reading,
the Workbench link and the current-book ordering.

## Pilot labels and analysis

- `labels/WRT-EDIT-02B-review-completed-set1.csv` — frozen Set 1 labels
  - SHA-256: `9e0cbf6bbcd7e4a067d43de5bce7aedcec026532d45b09b6380ff87993a23568`
- `labels/LABEL-MANIFEST.json` — hash, reviewer status, completeness
- `labels/reviewed-labels-joined.csv` — human labels joined to Writer diagnostics
- `labels/agreement-cross-tabs.csv` — human × Writer dimension counts
- `labels/agreement-summary.json` — full pilot summary
- `C:\Projects\writer\docs\analysis\WRT-EDIT-02B-PILOT-AGREEMENT.md` — report

Pilot summary: 10 reviewed passages, one missing detail (`P01` fragmentation),
1 true positive, 2 false negatives, 4 false positives and 1 true negative
against `genuine_issue`. Fiction was flagged more often than the reviewer found
genuine issues; technical density and lexical difficulty were largely missed.
Pilot verdict: **REFINE**, not adopt/reject. The sample is too small for
threshold changes.

## Reviewer caveat

The first reviewer is AI-assisted and has prior exposure to the sample map and
diagnostic strata. That review must be identified as **AI-assisted with prior
diagnostic exposure**, not as blind human ground truth. It will be compared with
a genuinely blind human review.

## Next step

1. Use the Workbench Editing panel on **Language Chapter 3** as the first
   before/after example. Confirm, dismiss or defer its finding with an explicit
   scope and reason; refreshing evidence is not acceptance of the revision.
2. Use the Mission Control queue on **Inference** for the larger triage set,
   starting with representative cases and opening them in Workbench.
3. Record real Confirm / Dismiss / Defer decisions with reasons and explicit
   scope. The representative plus a chapter or book-wide scope can cover a
   repeated pattern without scoring every instance.
4. For a confirmed finding, use **Prepare revision** and judge the candidate
   independently as **Better / Same / Worse** before deciding whether to apply
   it. A verdict is not approval.
5. When applying, rely on the linked receipt: it records the finding, report and
   source fingerprints, exact candidate hash, verdict, decision and manuscript
   before/after hashes. Refusal means the evidence moved; prepare again.
6. Derive future calibration from those real, contextual decisions and verdicts,
   separated by editorial dimension and book profile. Do not treat the partial
   10/50 CSV as blind ground truth or tune thresholds from it.
7. Add a second independent reviewer for a subset when a genuinely blind review
   is needed.
8. Keep Apply/Reject/Edit and preservation checks between a candidate and the
   manuscript; never auto-apply prose.

Plan: `C:\Projects\writer\docs\analysis\WRT-EDIT-02B-PLAN.md`
