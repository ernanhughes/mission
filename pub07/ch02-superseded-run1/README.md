# PUB-07 run 1 artifacts (superseded, preserved verbatim)

First bounded pipeline run, 2026-11-25 ~07:42-07:45 UTC, on the pre-fix-batch
code. Preserved here before the Fix E re-run overwrote `pub07/ch02/`.
Nothing in this directory is edited; it is the visible history Fix F
requires (supersede notes, not silent rewrites).

Why superseded (PUB-07 fix batch, D-PUB-81):

- Fix A: both review rounds sliced the review excerpt by the ORIGINAL span
  end (`candidate_lines[span.start-1:span.end]`). Round 1 (12-line
  replacement in a 14-line span) leaked 2 trailing source lines; round 2
  (6-line replacement) leaked 8 trailing source lines including the
  source's own LLM2Jev paragraph ("And then there is the paper that says
  the quiet part loudly...", on-disk lines 140-148).
- Consequence 1 (round 1): the reviewer objected to a "final paragraph
  cut off mid-sentence" -- the cut is the window edge, not the revision
  -- and to a "Taken together ... establishes" hardening.
- Consequence 2 (round 2): the reviewer attributed the LEAKED SOURCE
  paragraph's LLM2Jev claims (4B match, diminishing/negative returns,
  section-1 reading) to the revision, and raised
  `quote_not_in_either_passage` on "a resemblance, not a demonstrated
  equivalence" -- a sentence that exists ONLY in the corrected text. It
  failed because validation consumed the STALE whole-chapter bytes
  (attempt-1 assembly, Fix B) instead of the excerpt shown.
- The ledger citations in both rationales also miscite the read status
  ("section 4 read", "section 3.4"); ledger 2.13 is abstract + section 1
  + section 3.3 PARTIAL, section 4 NOT read (Fix E4; the plan's frozen
  obligation text keeps its own spelling and is corrected only in the
  new approval record, never by editing the frozen plan).

Key run-1 numbers (for delta comparison with the re-run):

- candidate fp (LF form): 50e1ef2e0886e6ee65fdbb81a7061b6dc32302c65ebcee4be3cd62fdab602f37
  (file on disk held CRLF bytes: raw sha 804706fd..., see Fix G)
- 4 dispatches, $0.00706125, 25,504 tokens; outcome `review_invalid`
- verification 15/15 pass; proposal pub07-ch02-p001 pending + fresh
- chain.candidate_fingerprint == LF sha above; chain has NO ledger_digest
  (added by Fix D in the re-run)
