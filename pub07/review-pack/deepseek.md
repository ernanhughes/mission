# PUB-07 review — DeepSeek (regression / verification, free tier first)

Routine verification on the free model (`deepseek-v4.1-flash-free`);
escalate to `deepseek-v4.1-flash` only if the free route is unavailable
or abstains (record the reason). No paid experimental runs.

## 1. Fast gate (CWD `C:\Projects\writer`, venv python)

```
venv\Scripts\python -m pytest tests/core/test_publication_transformation.py tests/core/test_publication_automation.py tests/core/test_publication_cruft.py tests/core/test_publication_cruft_calibration.py tests/core/test_publication_complexity.py tests/core/test_publication_complexity_calibration.py tests/core/test_publication_pedagogy.py tests/core/test_publication_pedagogy_calibration.py tests/core/test_reader_legibility.py tests/core/test_evidence_reconciliation.py tests/core/test_evidence_reconciliation_calibration.py tests/runtime/editing tests/runtime/quality tests/cli/test_transform_cli.py -q -p no:cacheprovider
```

Expected: 560 passed + 1 strict xfailed (`held-cx15`, PUB-04
known-FN pin) / 0 failed. Also: `ruff check` on
`packages/writer-core/writer_core/analysis/publication_automation.py`,
`packages/writer-cli/writer_cli/commands/transform.py`,
`packages/writer-core/writer_core/analysis/publication_transformation.py`,
`tests/core/test_publication_automation.py`,
`tests/cli/test_transform_cli.py` → clean.

## 2. Workbench neighbours (CWD `C:\Projects\workbench`, `.venv` python, `PYTHONPATH=src`)

```
pytest tests/test_publication_proposals.py tests/test_quality_bridge.py tests/test_proposals_checks.py -q -p no:cacheprovider
```

Expected: 31 passed. (`test_chapter_apply` 13/13 in selected scope;
the aitest harness foreground-times-out at 30 s with the rest queued
to background verification — record, do not chase; the stage touches
no existing workbench file.)

## 3. Deterministic live chain (zero new spend — all read-only)

Re-run and compare against `C:\Projects\mission\pub07\ch02\inputs\`:

- `writer cruft review jev 02-chapter --book-root C:\books\jev --json`
  → 0 findings / 6 preserved / 7 needs-evidence, fp `b61a63c525e2`.
- `writer complex review jev 02-chapter --book-root C:\books\jev --json`
  → 44 findings (CX02×13/CX03×8/CX01×5/…), 6 preserved, 11 needs-context.
- `writer reconcile chapter jev 02-chapter --book-root C:\books\jev --json`
  → 14 claims (7 supported / 4 unresolved / 2 NA / 1 partial),
  inventory rev `jev@899c02ad76215729`.
- `writer pedag plan …` (see STATE.md §3 for exact invocation) → 46 ops.
- `writer transform check …` → executable (44 boundary_ok + 2 isolating).
- `writer transform package …` → 10 packages; the demo package
  `passage:Nine older mechanisms, seven properties` has op_refs
  `op:b61a63c5:006/007`, span 133-146.
- `writer transform automate … --dry-run` → exit 0, payloads present,
  zero dispatches; `--package-id passage:Nope` → exit 1.

## 4. Record / artifact integrity (no re-dispatch)

- `transformation-record.json`: schema `writer.transform.record.v1`;
  `chain.candidate_fingerprint` == sha256(`candidate.md`) ==
  `50e1ef2e0886e6ee65fdbb81a7061b6dc32302c65ebcee4be3cd62fdab602f37`;
  `config.model_dispatches` == 4 == ledger `dispatch_count`;
  ledger roles 2 editorial (deepseek-go) + 2 verification (haiku-go);
  total $0.00706125 / 25,504 tokens.
- `verification.json`: verdict pass, 15/15.
- `program.json`: outcome `review_invalid`; loop iterations ≤ 5 total
  dispatches; corrections bounded (1 review-driven); no iteration
  beyond the final re-review.
- `proposal.json`: status pending, freshness True; stale simulation
  (tamper one line) must report STALE (covered by unit test;
  re-verify logic, do not mutate the book).
- `approval-decision.json`: status `pending_author_decision`,
  `approved_by` null.
- Fixture proof (disposable `C:\Temp` bytes only, never the book):
  may re-run `apply_edits.py --diff/--apply` on a temp copy; expect
  1/1 ratio-1.000, applied bytes == candidate bytes, pristine-restore
  byte-identical.

## 5. Source safety

- `git -C C:\books\jev status --porcelain` → only pre-existing
  untracked `scripts/`; HEAD `c7aaad7`.
- Writer/Workbench/Mission trees: only the stage's own new files +
  named modifications (automation module + test, transform CLI +
  test, record extension, transform README, bridge module + test,
  programme docs, pub07/ artifacts). No commits/pushes.

Verdict: ACCEPT / CONDITIONAL / BLOCKED with exact failing
command + output. Preserve disagreements in writing.
