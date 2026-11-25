# PUB-07 fix-batch delta re-verify — DeepSeek (incl. F1-F5)

Routine re-verification on the fix-batch tree + the re-run artifacts.
All post-re-run numbers are filled below (verified 2026-11-25 against
`pub07/ch02-rerun/`); everything else must reproduce exactly.

## 1. Fast gate (CWD `C:\Projects\writer`, venv python)

```
venv\Scripts\python -m pytest tests/core/test_publication_transformation.py tests/core/test_publication_automation.py tests/core/test_publication_cruft.py tests/core/test_publication_cruft_calibration.py tests/core/test_publication_complexity.py tests/core/test_publication_complexity_calibration.py tests/core/test_publication_pedagogy.py tests/core/test_publication_pedagogy_calibration.py tests/core/test_reader_legibility.py tests/core/test_evidence_reconciliation.py tests/core/test_evidence_reconciliation_calibration.py tests/runtime/editing tests/runtime/quality tests/cli/test_transform_cli.py -q -p no:cacheprovider
```

Expected: 592 passed + 1 strict xfailed (held-cx15) / 0 failed
(593 collected; verified 2026-11-25 on the settled tree — supersedes
the 583 expectation from the pre-close-out tree: +9 from the
coordinator close-out pins). Also: `ruff check` clean on the
4 changed writer files + 3 test files.

## 2. Workbench neighbours (CWD `C:\Projects\workbench`, `.venv` python, `PYTHONPATH=src`)

```
pytest tests/test_publication_proposals.py tests/test_quality_bridge.py tests/test_proposals_checks.py -q -p no:cacheprovider
```

Expected: 35 passed (was 31; +4 bridge pins) / 0 failed.

## 3. Deterministic live chain (zero new spend, read-only)

Re-run and compare against `pub07/ch02/inputs/`:

- `writer cruft review jev 02-chapter --book-root C:\books\jev --json`
  → 0 findings / 6 preserved / 7 needs-evidence, fp `b61a63c525e2`.
- `writer complex review jev 02-chapter --book-root C:\books\jev --json`
  → 44 findings (CX02×13/CX03×8/CX01×5/…), 6 preserved, 11 needs-context.
- `writer reconcile chapter jev 02-chapter --book-root C:\books\jev --json`
  → 14 claims (7 supported / 4 unresolved / 2 NA / 1 partial),
  chapter fp `b61a63c525e29e4339bea70b4239576c243220bcf1136f22d87a85cf69d5be3b`.
- `writer pedag plan …` (STATE §3 for exact invocation) → 46 ops.
- `writer transform check …` → executable (44 boundary_ok + 2 isolating).
- `writer transform package …` → 10 packages; demo package
  `passage:Nine older mechanisms, seven properties` op_refs
  `op:b61a63c5:006/007`, span 133-146.
- `writer transform automate … --dry-run` → exit 0, payloads present,
  zero dispatches.

## 4. Record / artifact integrity — F1-F5 close-out (no re-dispatch)

- F1 (stale window): every `review_rounds[i].review_excerpt_range` in
  the NEW `program.json` equals the dispatch lineage range; the round-1
  2-line and round-2 8-line leakages are gone (compare
  `ch02-superseded-run1/README.md`).
- F2 (stale rebind): `len(final_lineage) == len(final_lines)`; tail
  `source_line` offsets correct; final-review validation consumed the
  excerpt (no spurious `quote_not_in_either_passage`).
- F4 (narrative): NEW `program.json` carries `fix_batch_annotations`
  (labeled author-side) and NEW `approval-decision.json` carries a
  `supersedes` section quoting the run-1 narrative; originals visible
  in the archive, never edited. Numbers refreshed to the re-run set:
  candidate fp `9f36c9ba…` (355 lines, 20,239 bytes), 2 dispatches,
  $0.0039864, verification 15/15, proposal pending + fresh. Ledger-2.13 citation
  reads abstract + §1 + §3.3 PARTIAL, §4 NOT read. The 2 isolating
  violations are named as such (not "0 violations"); `before-after`
  claims name the rewritten record (no "untouched" for rewritten files).
- F5 (canonical forms): `sha256(candidate.md)` RAW FILE BYTES ==
  `chain.candidate_fingerprint` == verification-after (the run-1 CRLF
  split, 8047... vs 50e1..., must be gone). Intent path digest stable
  across slash spellings (unit-pinned). Ledger digest pinned equal on
  both sides (cross-compat vector `6ef13476…`).
- F3 (spend): ledger `spend_cap_usd` + `spend_cap_override_explicit`
  present; `program.spend_policy.pre_dispatch_enforced` true; total
  spend $0.0039864 within cap; pre-re-run BLOCKED $0 attempts disclosed in
  the approval record (no unrecorded dispatch).

## 5. Source safety

- `git -C C:\books\jev status --porcelain` → only pre-existing
  untracked `scripts/`; HEAD `c7aaad7`.
- Catalog 167; fixture temp dirs cleaned (`C:\Temp\pub07*` gone).

Verdict: ACCEPT / CONDITIONAL / BLOCKED with exact failing command +
output. Preserve disagreements in writing.
