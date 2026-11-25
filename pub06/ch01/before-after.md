# Ch1 before-after assessment (candidate `f6c1cbf4266b083ca4`)

Original: `01-chapter.md` @ `c7aaad7`, fingerprint `435974701050…` (562 lines).
Candidate: `01-chapter-candidate.md` in this directory (fingerprint
`f6c1cbf4266b083ca4`, 606 lines). Full unified diff: `diff.txt` (generated
against the pre-polish candidate; every later byte change is listed
verbatim in § "Post-verification polish" below, and the rebuilt
`transformation-record.json` asserts after==candidate on these bytes).
Verification: `verification-report.json` (verdict **pass**, 21/21 checks).

## Verdict

**ACCEPT as candidate after the Claude/Codex fix batch** (author review
still required; this is candidacy, not production). The pre-fix record
claimed ACCEPT while Claude BLOCKED-narrow on P1/P2/P4 (strengthened
unresolved claims) — that disagreement is preserved, and this record now
concurs: the three must-fix plus P5/P8 and Codex editorial are applied
above. Preservation holds everywhere it was obligated; honest records
are byte-true at line level; unresolved claims are not strengthened
(including the new-sentence honesty layer); no-change spans are
identical with placement proof. Findings deltas are reported as
informative confirmation, never as the verdict basis — the verdict
rests on the preservation checks, which is what makes this not
detector-count optimisation.

## Detector before-after (informative, `transform verify`)

| Screen | Before | After |
|---|---|---|
| Cruft findings | 1 (CR04-LOW, correction-note scaffolding) | 1 (same CR04-LOW — the note is preserved byte-true per the declined consolidation; the finding correctly persists) |
| Cruft preserved | 11 | 12 |
| Complexity findings | 38 | 39 (net +1: new prose carries measurable load; no joined spans, no HIGH) |
| CX14 (interruption/bridge gaps) | 8 | 6 (all LOW; six in-manuscript bridges added, two fire LOW on new bridge text — accepted residual) |
| CX10 (staccato) | 1 | 1 (no new staccato; the one firing is pre-existing; a cross-table false-positive HIGH seen mid-programme was removed by the PUB-04 structural-break fix, verified gone) |
| CX02 (clause load) | 8 | 9 (new explanatory sentences carry load) |
| CX11 | 5 | 4 |
| CX05 | 2 | 4 (split honest-record block fires per-paragraph; byte-true sentences kept — detector-on-honest-text, documented residual, PUB-08) |
| CX13 (long-distance deps) | 1 | 2 (new concluding/cross-chapter passages add dependency markers) |
| CX13 (long-distance deps) | 1 | 2 |
| Complexity preserved | 10 | 11 |

No dense→staccato trade: max severity did not rise (the mandatory
regression shape holds on the candidate: the heaviest concentration,
L509 closing, gained a synthesis line without new high findings).
No score-gaming: the engine's anti-gaming rule fails any candidate whose
counts fall while preservation checks fail; all 21 preservation checks
pass (20 byte-true/no-change/unresolved + new-sentence honesty).

## Concrete before→after passages

### 1. Opening frame (reconstruction package; no plan op — chapter frame)

Before: the opening (kept verbatim, NO_CHANGE) jumped from the straw-man
paragraph to the loop definitions with no roadmap.
After (fixed per Claude P1): one new paragraph states the chapter's shape
(one decision, one predicate, one runnable walkthrough, then the unrun
model-backed routes set against the one value; closes with the four words
and the open question). No "cost something"/"measured" claim for unrun
arms; central question already present is now signposted.

### 2. Error discussion (ops 008/009: SPLIT + SYNTHESIS, accepted; P2 fixed)

Before: one 7-line block piling error naming, hand-written-label
qualification, rulebook-hole diagnosis and model speculation.
After: two paragraphs (error naming + label qualification | rulebook-hole
diagnosis), every source line verbatim in order, plus one synthesis line
(fixed per Claude P2): "The errors look policy-shaped: they fall where the
written rulebook has no answer. Whether a model would share that shape is not
yet known; Chapter 7 and the arms below are where that is tested."
(merged into the second paragraph in Pass F — closing sentences, not a
staccato fragment). The pre-fix "not model-shaped / exactly where the book
begins" strengthening is removed.

### 3. Willard mechanism (ops 014/015/016: SYNTHESIS + TABLE + SYNTHESIS)

Before: five parallel numeric sentences (naive O(N), indexed O(1), ~50 MB
index) buried in prose; CX15 candidate.
After: a 4×3 comparison table (implementation / cost / what the paper
reports) with values strictly from the cited text, prose keeps the
interpretation (fixed per Claude P3: "Constraint is a memory cost before
it is a compute win." — meta-commentary cut, then split per P10).
Dims recorded in the visual spec; table validated (`validate_visual_spec`
pass).

### 4. Bridges (ops 005/013/018/021/029/030: CONNECT, adjudicated accept)

Six local transitions added, all content from adjacent in-manuscript
text: Paths 2/3 shared-decoding bridge (fixed per Claude P6: decoding +
recovery-step difference, prompt-identical repetition cut); Path-2
recovery-tax synthesis (fixed per P9: "win or lose" cut);
guarantee→Tam bridge (fixed per Codex: "What that guarantee costs in task
performance is what the next paper tests."); ordering-confound→§5.4
bridge (fixed per P7: double announcement merged);
honesty-boundary bridge into the did-not-run sentence;
unobserved-arms→25-character-payload bridge (fixed per P4);
four-definitions→claim bridge. CX14 8→6.

### 5. Research splits (ops 022–025: SPLIT + SYNTHESIS ×2, accepted)

Tam §5.4 two-sided cut → two paragraphs + closing synthesis ("pricing
that trade-off is what the arms are for", tightened in Pass F to remove
an introduced hedge pile-up). LMQL paragraph → idea/measurement split +
synthesis ("The prior art owns the idea; this chapter owns one
measurement…", merged as closing sentence in Pass F).

### 6. Closing (op 040: ADD_SYNTHESIS, accepted; op 039 table declined as evidence-blocked)

One synthesis line after the one-line summary, merged into a single
closing paragraph: "The floor is one arm, the question is Chapter 2's,
and the obligation until then is the measurement." The vendor-answer
paragraph and closing question stay verbatim (evidence-blocked).

### 7. Declined with reason (op 006 CONSOLIDATE)

The CAPSTONE-02B correction note stays byte-true. Rationale: the
attached preservation obligation forbids rewording/condensing the
amendment, and the note is already minimal. The stage objective
("correction integrated, history not narrated") is met structurally: the
main text already reflects the corrected predicate, and no additional
history narration was added anywhere.

## Preservation / claims / code / math / visuals / comprehension

- Preservation: byte-true + no-change + unresolved-obligation +
  new-sentence-honesty checks pass (honest records, NOT_OBSERVED table,
  Limitations, run-command block, failure-mode list, stub honesty, figure
  markup). The verification design now includes the Claude §7 gap layer:
  added sentences get a claim-tier evidence check (D-PUB-59); full
  semantic honesty remains PUB-08 human review.
- Claims (concur with Claude P1/P2/P4 — pre-fix record disputed, now
  fixed): roadmap no longer says unrun arms "cost something"/"measured"
  (P1 fixed); error synthesis no longer asserts "not model-shaped" /
  "exactly where the book begins" (P2 fixed); Figure 1.2 caption/alt/SVG
  no longer claim "whichever lane answers, 25 characters" (P4 fixed —
  per-lane: predicate True/abstain, stub nothing; 25 chars = serialized
  example payload; lane 3 holds two arms, four unobserved arms total).
  Proposed claims keep hypothesis framing; unresolved claims (self-test
  53 vs 48-record tension, model-arm gaps) kept visible, never
  strengthened.
- Code: all six code/output blocks byte-identical (excerpts, walkthrough,
  prompt template, stub, outputs).
- Math: O(N)/O(1)/~50 MB (SVG now qualified "naive index, augmented
  Python grammar" per P5)/25-char/4µs/8-of-10 figures unchanged.
- Visuals (concur with Claude P4/P5/P8 — pre-fix "validated" claim
  withdrawn): Figure 1.1 kept byte-true; Figure 1.2 (SVG validated
  well-formed + dims + refs, caption/alt/SVG honesty fixed per P4/P5,
  moved after Figure 1.1 per P8) orients the four lanes; Willard table
  validated. No decoration; production placement is publish-time work.
- Comprehension (reader probe, model-reader ≠ human proof): blind
  original-vs-revised probe specified in the review pack
  (`../review-pack/mediated-probe.md`); PUB-08 owns human calibration.
- Pedagogy: section order kept (REORDER investigation-only); purpose and
  cross-chapter deps (Ch2/Ch7/Ch16) intact; walkthrough runnable and
  unchanged.

## Residuals / limits

- CX05 +1 on the split honest block (byte-true sentences; detector
  behaviour on honest text, PUB-08 trap).
- 53-vs-48 self-test count tension (candidate "53 checks"
  vs preservation "48 offline checks") kept verbatim, recorded unresolved
  (evidence-blocked; PUB-10 must reconcile).
- Figure 1.2 references `assets/` relatively; production image-dir
  placement is publish-time (PUB-10), not done here.
- Mermaid not used (render path unverified → pipeline caveat stands;
  SVG only).

## Post-verification polish (coordinator-executed, Codex + Claude residuals)

After the 21/21 verify, the following edits were applied for the
confirmed review residuals and the candidate re-verified (still 21/21
pass on the final bytes; fingerprint above is the polished bytes):
- R1: "written rulebook has no answer" → "rule's numeric conditions are
  met but its intent is not covered" (Claude editorial: t11/t60 were
  answered True, so the gap is intent, not coverage).
- R2: SVG footer `\"refund_approved\"` → single quotes (no literal
  backslashes in rendered text).
- R5: lane-3 alt "parse text into values" → "constrained decoding
  into values" — REVERTED before release: the SVG `<desc>` says
  "parse text into values" and that is correct for the free-form lane,
  so the candidate keeps "parse text into values" (verified in the
  final candidate bytes).
- Codex editorial: Tam sentence reframed to task-performance effects;
  Fig 1.2 caption/alt already per-lane honest (verified, no change
  needed beyond the fix batch).
- Schema-length paragraph: "greater than 1 by construction" ratio claim
  → explicit schema-length fact with unrun qualifier ("the model-backed
  arms have not been run, so no ... comparison exists").
- Willard table: "Cost per token" → "Cost" header (row 3 is one-time
  memory, not per-token); stub row kept byte-true per preservation
  (dash alternative deferred to author/PUB-10).
- Roadmap closing line: "closes with the four words..." → "sets out
  the four words ... and closes with the one question..." (accurate
  ordering).
- LMQL slogan: dropped "which LMQL said first" attribution (the book's
  own rule, not LMQL's).
- Conflation sentence: "measurements are the evidence" → "what the
  measurement programme exists to test" (future-test framing).
- Timer limitation restored to Limitations ("CPU timer resolution was
  not characterised...").
- SVG Fig 1.2 label: "~50 MB" now carries the "(§5)" qualifier.
The `transform verify` re-run and the rebuilt `transformation-record.json`
(chain: plan/boundary/packages digests + after==candidate asserted)
cover the polished bytes; `diff.txt` predates these edits (unified diff
of the fix-batch candidate vs original).
