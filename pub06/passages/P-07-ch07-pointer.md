# Bounded passage P-07: evidence-backed update (Ch7 superseded pointer)

## Source

- Chapter: `07-chapter.md` (authoritative, rev `c7aaad7`), block L443–446,
  section "The cost accounting (analytical, not measured)".
- Claim: `eclaim:871c44960296d5f0623e`, category `implementation_availability`.
- Reconcile state: **SUPERSEDED** (`evidence-reconciler-v0.1`,
  inventory `jev@a6cd2b879ef9ae6a`); `why_obsolete`: referenced file
  absent at bound revision; operation `update_impl_description`.
- Correction contract: `establishes`: "What exists at the bound revision";
  `preserve`: honesty record stays, only obsolete status words change;
  `remains_unknown`: "Whether a nearby file is the intended replacement."

## Before (verbatim, L443–446)

> **Not yet run:** measured tokens and latency, both execution paths
> To run: `python examples/ch07-the-first-token/run_ch07.py --stage S7 --metric tokens --device cuda` then `--stage S8 --metric latency --device cuda`
> Results go to: `results/ch07.jsonl`, rows with `metric: tokens` and `metric: latency`
> Note: the latency stage needs an idle machine, 200 items, warm, 3 repeats.

## After (candidate)

> **Not yet run:** measured tokens and latency, both execution paths
> **Superseded pointer (evidence-backed, rev `c7aaad7`):** the command below
> names `examples/ch07-the-first-token/run_ch07.py`, which is absent at the
> bound revision. The entry point for these stages is unresolved, and no
> nearby file is claimed as its replacement.
> To run (as written, currently unrunnable): `python examples/ch07-the-first-token/run_ch07.py --stage S7 --metric tokens --device cuda` then `--stage S8 --metric latency --device cuda`
> Results go to: `results/ch07.jsonl`, rows with `metric: tokens` and `metric: latency`
> Note: the latency stage needs an idle machine, 200 items, warm, 3 repeats.

## What changed and what did not

- Changed (only obsolete status words, per the correction contract): the
  `To run:` line is marked as written-but-unrunnable, and a two-sentence
  superseded-pointer note names the absent file, the bound revision, and
  the unresolved status.
- Preserved byte-true: the not-yet-run intent, the results destination,
  the idle-machine note, and the original command text itself (kept as the
  record of what was written, not deleted for ugliness).
- NOT inferred: no replacement file is named. `demo_ch07.py`,
  `inspect_ch07.py` and `selftest_ch07.py` exist at the revision but have
  different scopes (demo/inspect/selftest, not the S7/S8 sweep); claiming
  one as the replacement would manufacture evidence. The cited
  `STAGE_PLAN.md` itself names the same absent file, so it cannot resolve
  the pointer either — recorded as dependent-held for the author.
- Dependent held: the L556 `run_ch07.py --merge` pointer in the model-sweep
  block names the same absent file; it is out of this passage's scope and
  is recorded as held, not silently fixed.

## Verification

- No new `.py` filename introduced (checked: the only
  `examples/.../*.py` path in the candidate is the original one).
- Honesty sentences present verbatim (not-yet-run intent, results
  destination, idle-machine note).
- Correction proposal linkage: claim id, revision, evidence refs
  (`jev:ledger:ch07#7.13`–`7.23`, prereg `JEV-07-01/02/03 + hypotheses`,
  `results/ch07.jsonl` tokenizer rows) carried in this record.
- No claim strengthened: the stages remain NOT run; nothing is presented
  as established.
