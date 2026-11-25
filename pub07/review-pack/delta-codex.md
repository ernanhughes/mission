# PUB-07 fix-batch delta re-review — Codex (close the 4 BLOCKED items)

Scope: the fix batch (D-PUB-81) only. No new broad review. Confirm each
BLOCKED item below is closed on the CURRENT tree + the re-run artifacts
in `C:\Projects\mission\pub07\ch02-rerun\` (post-fix rerun 09:18 UTC:
outcome review_accepted, 2 dispatches $0.0039864, verify 15/15;
run-1 preserved in `pub07/ch02-superseded-run1/`, and `pub07/ch02/`
on disk still holds the run-1 bytes `50e1ef2e…` pending the author's
promotion decision).

## 1. Review-window scoping (was: excerpt sliced by original span end)

- Code: `publication_automation._review_excerpt_lines` — excerpt is the
  assembly lineage dispatch range (`start + len(replacement) - 1`), never
  the original span end. Each `review_rounds[i]` records
  `review_excerpt_range` + `review_excerpt_sha256`.
- Check the re-run `program.json`: every round's `review_excerpt_range`
  must equal the dispatch region (lines 133–155 for the new paragraph
  form — 23 lines incl. blank separators — NOT the original span
  133-146), and the round-2-style leakage (8 trailing source
  lines incl. the LLM2Jev paragraph) must be gone. The review prompt in
  `dispatch.raw_response` / ledger `prompt_sha256` is over the excerpt.
- Pins: `test_review_excerpt_scopes_to_replacement_not_span`,
  `test_review_excerpt_scopes_longer_replacement`.

## 2. Rebind before final review (was: stale candidate_text + lineage)

- Code: `run_editorial_program` keeps one review `state`
  (lines/text/lineage); corrections rebind ALL THREE from the
  correction's own assembly; `validate_review_output` consumes exactly
  the excerpt bytes shown (`passage + excerpt`, never whole chapter).
  `editorial_loop.final_lineage` is synced on every exit path.
- Check: `len(final_lineage) == len(final_lines)` with correct tail
  `source_line` offsets; a final-review quote existing only in
  corrected text validates (no `quote_not_in_either_passage`).
- Pins: `test_final_review_rebinds_to_corrected_text_and_lineage`
  (shorter + tail offsets), longer-correction excerpt test above.

## 3. Spend guard (was: post-run report only, silent raise)

- Code: `check_spend_guard(ledger, cap, projected)` + per-dispatch
  pre-checks (`halted_spend_guard`, zero new dispatch) in both the loop
  and the program; `--spend-cap` default 10, values above recorded as
  `spend_cap_override_explicit` in ledger + record `config`.
- Check: `program.spend_policy.pre_dispatch_enforced` true; re-run
  ledger carries `spend_cap_usd`; no dispatch exceeds remaining budget.
- Pins: `test_spend_guard_halts_before_first_dispatch`,
  `test_spend_guard_halts_mid_run_before_next_dispatch`,
  `test_check_spend_guard_uses_projection_and_remaining`.

## 4. Dispatch provenance join (was: non-empty entries only)

- Code: ledger rows bind `replacement_sha256` (verified assemblies are
  restamped to the dispatched-region body bytes incl. paragraph blanks);
  record `chain.ledger_digest` (latency-stripped); Workbench builder
  REFUSES ledgers not binding the replacement; `check_proposal_fresh`
  covers the replacement hash; proposal carries `record_chain`
  (plan + candidate fp + ledger digest).
- Check: `proposal.bound.ledger_digest == record.chain.ledger_digest`;
  `record_chain.candidate_fingerprint == chain.candidate_fingerprint`;
  tamper simulations refuse/go-STALE (unit-pinned).
- Pins: `test_record_chain_binds_ledger_digest`,
  `test_refuse_ledger_for_other_bytes`,
  `test_proposal_carries_ledger_digest_and_record_chain`,
  `test_stale_on_replacement_tamper`, cross-compat digest vectors both sides.

Also confirm: D-PUB-81 amendments to D-PUB-68/69/79 are notes, not
history rewrites; no catalog change (167); no Mission UI; no PUB-08.

Verdict: confirm each item CLOSED / residual (precise).
