# PUB-06 independent editorial assessment: Jev Ch1 "Stop Generating"

Reviewer: Claude, `claude-haiku-5-5`, provider `opencode-go` (README §6: Claude for editorial judgement; no fallback used).
Generator under review: Muse. Scope: PUB-06 only. PUB-07 not started.
Read: authoritative `01-chapter.md` (562 lines), candidate `01-chapter-candidate.md` (603 lines), `diff.txt`, `before-after.md`, `verification-report.json`, `fig-01-2-paths.svg`, `P-07`, `P-09`. Authoritative files not modified. No model arms were run and none were claimed.

## Verdict

**BLOCKED (narrow).** Two new sentences state unobserved model-backed results as established, which is the hard failure the review pack names ("strengthened unresolved claims"). The fix is small. The rest of the chapter is close to publishable. After the fixes in section 4, I expect CONDITIONAL → ACCEPT as a candidate, pending author release.

## 1. Proposed rubric scores (not calibrated; critical defects override)

| Dimension | Max | Score | Basis |
|---|---|---|---|
| Conceptual clarity | 200 | 165 | Four-words section intact; the decision/generation distinction is sharper. Loss: "policy-shaped, not model-shaped" (line 129-131) blurs the line the chapter draws. |
| Narrative flow | 200 | 160 | Roadmap paragraph helps. Double announcement at 318-321 and meta-commentary at 290 slow it. |
| Cognitive workload | 150 | 118 | Willard table lowers load. Line 290-294 is dense. Figure 1.2 sits before Figure 1.1. |
| Pedagogical progression | 150 | 118 | Walkthrough and order preserved. Roadmap is earned but its first paragraph overclaims (section 3, P1). |
| Technical fidelity | 150 | 120 | All numbers preserved (25 chars, <4 µs, 8/10, 10/10, O(N)/O(1), ~50 MB, 200 labels, 26-80%). Code blocks byte-identical. Qualification lost in SVG (section 3, P5). "Exactly one place" overstated (P6). |
| Evidence fidelity | 100 | 55 | Limits, NOT_OBSERVED table, "Not yet run" block, Limitations all preserved. Two new claims read as established (P1, P2). Figure caption overreaches (P4). |
| Visual-structural | 50 | 36 | Willard table is good. Figure 1.2 order, caption, and alt text need fixes. Asset path is relative (publish-time, noted in before-after). |
| **Total** | **1000** | **772** | |

## 2. What genuinely improved

- The opening roadmap (lines 33-37) gives a first-time reader the chapter's shape up front.
- The Willard table (lines 284-288) prices the mechanism more clearly than the prose it replaced. Values match §1 and §5 of the cited paper as represented in the original.
- The Tam §5.4 split (lines 318-331) is clearer: "Constraint may help, or it may cost; we will not know until we run it" is a better-hedged statement than the original.
- The LMQL paragraph (lines 337-344) now separates "the prior art owns the idea" from "this chapter owns one measurement". That is a useful editorial move.
- The "Generate less. Measure the rest." close is retained, and the chapter's ending now names what is still owed.
- Verbatim preservation holds where it was obligated: CAPSTONE-02B correction note (107-115), NOT_OBSERVED table, "Not yet run" block, Limitations (523-543 → 566-584), the Chapter 2/16 cross-references, and the Chapter 7 stub honesty.

## 3. Passage pairs: what got worse or was lost

**P1. Roadmap overclaims (BLOCKING).**
- Candidate line 34-35: "It then takes the model-backed routes that cost something, measured against the one value the application actually reads."
- Problem: the model-backed routes are NOT_OBSERVED (table at lines 447-453). Saying they "cost something" and are "measured" reads as an established result. The chapter's own limitations say no number is estimated and the gap is left open.
- Fix: "It then sets out the model-backed routes, which have not yet been run, against the one value the application actually reads."

**P2. "Not model-shaped" is a claim the chapter cannot support (BLOCKING).**
- Candidate lines 129-131: "The errors are policy-shaped, not model-shaped: they mark where the rulebook ends, which is exactly where the rest of the book begins."
- Original line 119-122: "A model would get these 'right' by having absorbed conventions the runbook never states, which is either better or worse depending on whether you can tell which one you are getting."
- Problem: zero model-backed rows exist. "Not model-shaped" is an unobserved assertion. "Exactly where the rest of the book begins" is rhetoric with no evidence. The original's hedge is removed.
- Fix: "The errors look policy-shaped: they fall where the written rulebook has no answer. Whether a model would share that shape is not yet known; Chapter 7 and the arms below are where that is tested."

**P3. Editing-history narration.**
- Candidate line 290: "The table holds the numbers; the interpretation stays in the prose — constraint is a memory cost before it is a compute win."
- This narrates the edit's construction to the reader. Fix: delete the first clause, or open the paragraph with "Constraint is a memory cost before it is a compute win."

**P4. Figure 1.2 caption and alt overreach (BLOCKING with P1/P2 as the evidence set).**
- Candidate line 354 (alt) and 356 (caption): "Whichever lane answers, the caller reads 25 characters."
- Problem: the decide-stub lane returns nothing (`value=None`, `ok=False`), and the predicate abstains to a human on the 10 abstentions. Neither produces a 25-character payload. The 25-char figure is an interface constant from the original (line 422-427), not something each lane emits.
- Also the caption says "the other three lanes are the arms this chapter leaves unobserved", but four arms are NOT_OBSERVED (free-form, two schema orderings, stub), as Figure 1.1 says ("four of five arms never ran"). Lanes ≠ arms here, and the caption does not say so.
- Fix: "The caller's interface is 25 characters when a lane returns True or False; the abstention and stub lanes return no value. The four unobserved arms are free-form, two schema orderings, and the stub."

**P5. Dropped qualification in the SVG.**
- `fig-01-2-paths.svg` line 59: "constraint is memory first (~50 MB)".
- Original line 268-270 and candidate line 288 qualify the 50 MB as the naively built index for an augmented Python grammar. The figure drops it. Fix: "naive index, augmented Python grammar: ~50 MB".
- The SVG `<desc>` lists five lane descriptions while the title says "Four lanes" (line 3). Fix the wording to match the drawn four lanes.

**P6. "Exactly one place" overstated.**
- Candidate line 246-247: "Paths 2 and 3 differ in exactly one place — how the text is allowed to come out — so everything before the decoding step is shared."
- Path 2 also has a recovery step (regex, `json.loads`) that Path 3 lacks, which the chapter itself describes at line 270. Fix: "Paths 2 and 3 differ at the decoding step and in the recovery step that follows it."
- Also: lines 249-251 repeat "The prompt is identical for both model-backed paths". Cut one.

**P7. Double announcement.**
- Candidate line 318-319: "The ordering confound is not the only cost. The next finding cuts against the enthusiast case directly:" then line 321: "Their §5.4 is the finding that should worry a decision-model enthusiast most." Cut the first sentence or merge.

**P8. Figure order.**
- Figure 1.2 is placed at line 352, before Figure 1.1 at line 393. Renumber, or move Figure 1.2 after the table it parallels.

**P9. Minor rhetoric.**
- Line 270-271: "every codebase that reads values out of prose pays it, win or lose." This is editorial opinion without evidence. Drop "win or lose".

**P10. Density at line 291-294.** The Willard table is followed by a long paragraph that begins with the meta sentence in P3 and then joins the guarantee claim. Separate them after P3 is fixed.

## 4. Must-fix list for CONDITIONAL → ACCEPT

1. P1 (line 34-35): remove "cost something" and "measured" from the roadmap.
2. P2 (line 129-131): replace "not model-shaped" and "exactly where the rest of the book begins".
3. P4 (line 354, 356; SVG line 3, 72): correct the 25-character claim and the arms/lanes count.
4. P5 (SVG line 59): restore "naive index, augmented Python grammar" qualifier on the ~50 MB figure.
5. P8: fix figure numbering order.

Should-fix: P3, P6, P7, P9, P10.

Re-review scope after fixes: lines 33-37, 129-131, 246-251, 290-294, 318-321, 352-357, and the SVG. A full re-read is not required.

## 5. Inherited issues the author must resolve before release (not PUB-06 defects, but visible to a reader)

- **Predicate figures and walkthrough.** Lines 107-115 say the corrected predicate approves every eligible ticket, and the OBSERVED figures (10 answered, 8 correct) cite `results/ch01.jsonl`. The same note says the original measurements were taken on the buggy predicate. The walkthrough then "recomputes" the figures from corrected code. The chapter never says whether the 10/10 and 8/10 numbers changed after the correction. I did not run the walkthrough or inspect the results file. Author should confirm before release.
- **Self-test count.** Line 598 and 599 say "53 checks ... all 53 pass". `before-after.md` records an unresolved 53-vs-48 tension, kept out of the reader text. The reader should not be shown a number the record disputes. Either reconcile or footnote.
- **Figure asset path.** `assets/fig-01-2-paths.svg` is relative. The before-after note defers placement to PUB-10. Acceptable for a candidate, not for release.
- **Figure 1.1 caption** ("the chapter's honesty is the figure") is original and unchanged. Acceptable.

## 6. Bounded passages

**P-07 (Ch7 superseded pointer): ACCEPT as a passage.**
- The pointer names the absent `run_ch07.py` at revision `c7aaad7`. It adds no replacement file. The honesty sentences (not-yet-run intent, results destination, idle-machine note) are verbatim.
- The original command is kept as the record of what was written, with "currently unrunnable" attached.
- Concern: "`To run (as written, currently unrunnable):`" leaves a runnable-looking command in place. Acceptable as a record, but the author should decide whether to remove the command from the reader text.
- Open item: the L556 `run_ch07.py --merge` pointer is held, not fixed. Author should resolve it or accept the hold.
- I did not independently confirm the file is absent at the revision. I rely on the passage's cited reconciler state.

**P-09 (Ch9 staccato consolidation): ACCEPT, with a note.**
- Five staccato sentences become two. The `PROPOSED:` marker, all four roles, and the application's residual duty are preserved. No numbers or citations were added. Claim tier is not strengthened.
- Note: the first sentence now carries four parallel clauses in one long sentence. That is intentional (the four jobs are one separation), and the passage's own reasoning is sound. Still, a reader may find it dense. If the author wants relief, split after "jobs:" and keep the four roles as an unbulleted list. I do not require this.

## 7. Disagreements with the implementer's `before-after.md`

- **"No established claim reworded in meaning"** (`before-after.md` lines 104-105, "Claims"): I disagree. The roadmap (P1), the "not model-shaped" sentence (P2), and the Figure 1.2 caption (P4) introduce claims the evidence does not yet support. This is the record of my disagreement and it stands.
- **"Figure 1.2 ... validated well-formed + dims + refs"** (`before-after.md` line 115): validation confirms the SVG is well-formed. It does not confirm the caption or alt text is honest. I disagree that the figure is ready.
- **"Verdict: ACCEPT as candidate"** (`before-after.md` line 10): I cannot concur while P1, P2, and P4 stand. The verification report's 20/20 preservation checks pass, but preservation checks do not test the new sentences.
- **Preservation vs. honesty:** the implementer's gaming and detector analysis is accurate and I accept it. The problem is what the new sentences say, which the preservation checks do not cover.

## 8. Record

- Model: claude-haiku-5-5. Provider: opencode-go.
- Scope: PUB-06 ch01 and P-07/P-09 only. No authoritative file modified. Output written only to Temp.
- Not run: no model arms, no Jev walkthrough, no selftest, no long suites.
- PUB-07 not started.
