# PUB-07 review — Codex (architecture / integration / acceptance)

You are reviewing Stage PUB-07 of programme PUBLICATION ( Workbench and
Worker workflow integration + production automation closure).
PUB-06 is ACCEPTED (7/12). Programme docs (all 7 canonical files):
`C:\Projects\mission\docs\programmes\publication\`.
New decisions: D-PUB-76…80. No commits were made; review the working tree.

## What was built (Muse implementation, machinery-executed demo)

1. Writer `packages/writer-core/writer_core/analysis/publication_automation.py`
   (new): Writer-owned prompts + Pydantic contracts
   (`EditorialCandidateResponse`, `EditorialReviewResponse`), one
   dispatch per package via injected callable, quote discipline,
   deterministic assembly with per-line lineage, bounded correction
   loop (editorial ≤ max+1, review ≤ 2, total ≤ 5), spend cap,
   `dispatch_ledger` builder. writer-core stays dependency-light
   (no `writer_runtime` import — pinned by test).
2. `packages/writer-cli/writer_cli/commands/transform.py` + `automate`
   subcommand (existing group): live boundary recompile (fail-closed),
   supplied-packages authentication, single-span refusal, blocked
   refusal, full artifact emission. `--dry-run` = zero dispatches.
3. `publication_transformation.py`: additive `dispatch_ledger` param +
   `model_dispatches` count on `build_transformation_record` (schema
   stays `writer.transform.record.v1`).
4. Workbench `src/workbench/publication_proposals.py` (new): candidate
   JSON → pending Proposal data with span binding + `check_proposal_fresh`;
   refuses empty/failed-unverified/unprovenanced; accept/undo never
   invoked (pinned by test + source scan).
5. Live demo `C:\Projects\mission\pub07\ch02\`: candidate (338 lines),
   program.json (4 dispatches, outcome `review_invalid`), verification
   15/15, proposal (pending, fresh), staged (design-only),
   transformation record (+ ledger, $0.00706), approval-decision
   (`pending_author_decision`), inputs/ (exact reproducible inputs).

## Live execution path (verify it exists and is the ONLY path)

Writer `models.run` → WriterProvider POST `http://127.0.0.1:7317/v1/work`
→ Worker opencode-work executor → pi provider (subscription) →
routes `default_deepseek_go` (editorial) / `default_haiku_go`
(review, independent family). No new gateway, no new model client,
no direct provider calls. Confirm: no other transport was added
(grep for `urllib`, `socket`, `httpx`, `requests` in the new module —
must be absent).

## Review dimensions

- Seam ownership: does Writer own ONLY prompts/contracts/validation
  and Worker ONLY providers/transport/usage/cost? Is the injected
  dispatch callable honest (no retry/repair smuggled into `dispatch_task`
  or `run_editorial_program`)?
- Fail-closed: boundary revalidation on the live path (supplied
  packages advisory only); single-span refusal; blocked refusal;
  spend cap; loop termination (repeat-failure, invalid-twice,
  dispatch-failed-twice). Try to construct a bypass: forged-executable
  packages file, multi-span package, blocked package, `--max-iterations 9`.
- Record integrity: does `dispatch_ledger` + `model_dispatches` preserve
  the PUB-06 chain guarantees? Is the usage anomaly (haiku
  input_tokens=4 vs total 5262, recorded verbatim) handled honestly?
- Bridge granularity: is span-binding an acceptable substitute for
  paragraph `_validate` at package scale, or does it fork proposal
  semantics? Is pending-without-accept the right terminal state?
- Governance: outcome `review_invalid` + `pending_author_decision`
  with options — correct terminal behaviour for a verify-pass /
  review-objected candidate, or should the loop have behaved
  differently? Any auto-approval or mutation path you can find?
- Scope: any unrelated refactoring, catalog change, or Mission UI?

## Reproduce (CWD `C:\Projects\writer`, venv python)

- `venv\Scripts\python -m pytest tests/core/test_publication_automation.py
  tests/core/test_publication_transformation.py
  tests/cli/test_transform_cli.py -q -p no:cacheprovider`
- `writer transform automate ... --dry-run` (see
  `docs/cli/transform/README.md`; needs plan + packages + states —
  reuse `pub07/ch02/inputs/`).
- Live dispatches cost ~$0.01; do NOT re-run the live demo without
  author direction (4 dispatches already recorded; re-running would
  double-spend for no new evidence).

Verdict: ACCEPT / CONDITIONAL (with precise residuals) / BLOCKED.
Preserve disagreements in writing.
