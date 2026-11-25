# DeepSeek review prompt — PUB-06 regression + verification (deepseek-v4.1-flash-free; fallback v4.1-flash only if free unavailable, record reason)

You are the regression/verification reviewer for programme PUBLICATION
Stage PUB-06 fix batch (delta re-review). Reproduce the reported numbers
locally; report exact commands + pass/fail counts. Prefer deterministic
computation; no paid model runs needed for this review ($0 expected
throughout). Prior verdict: ACCEPT (35/316 suites, live chain exact,
fixture gate real, $0). This delta closes Codex a–f + Claude must-fix;
confirm no regression.

## Reproduce (CWD `C:\Projects\writer`, python `venv\Scripts\python`)

1. New suite: `venv\Scripts\python -m pytest tests/core/test_publication_transformation.py -q`
   Reported (fix batch): 60 passed, 0 failed.
2. Neighbours: `tests/core/test_publication_cruft.py`,
   `test_publication_cruft_calibration.py`,
   `test_publication_complexity.py`,
   `test_publication_complexity_calibration.py`,
   `test_publication_pedagogy.py`, `tests/core/test_reader_legibility.py`.
   Reported: 258 passed + 1 strict xfailed (held-cx15), 0 failed.
3. Live chain (read-only; `--book-root C:\books\jev`):
   - `writer cruft review jev 01-chapter --json` → 1/11/9, fp `43597470…`
   - `writer complex review jev 01-chapter --json` → 38 findings, fp same
   - `writer reconcile chapter jev 01-chapter --json` → 22/7/4/2 + 2 corr
     (35 claims; inventory `jev@bbbb73b55d7668a8`)
   - `writer pedag plan …` (see STATE §6 exact invocations) → 46 ops
     (11/17/6/9/3), validates
   - `writer pedag validate plan-ch1.json jev 01-chapter` → valid, 0 violations
   - `writer transform check … --plan pub06/ch01/plan-ch1.json
     --evidence-rev jev@live --inventory-digest <digest>
     --reconcile-states pub06/ch01/reconcile-states-ch1.json
     --adjudications pub06/ch01/adjudications-ch1.json --json` →
     executable true, 2 isolating (1 investigation_only REORDER +
     1 evidence_held op:039 closing TABLE)
   - `writer transform package … --adjudications … --json` →
     7 packages / 17 isolated / 12 respected (blocked derived)
   - `writer transform verify … --candidate pub06/ch01/01-chapter-candidate.md
     --plan … --work-packages …`
     → verdict pass, 21/21 checks, cruft 1→1 (11→12 preserved),
     complexity 38→35 (CX14 8→6, CX11 5→3, CX05 2→3)
4. Cross-check the verification report
   (`C:\Projects\mission\pub06\ch01\verification-report.json`):
   `before.fingerprint` == live `435974701050…`; `after.fingerprint` ==
   sha256 of `01-chapter-candidate.md` (`c54258e8…`); diff stats match
   `diff.txt` (178 lines). Record hash-chain: `package_hashes` (7) +
   `packages_digest` present; `verification.after_fingerprint` ==
   recorded `candidate_fingerprint` (builder asserts).
5. Catalog: `build_catalog()` → 167 (unchanged).
6. Source safety: `git -C C:\books\jev status --porcelain` (expect only
   pre-existing `scripts/`); `git -C C:\Projects\writer status --porcelain`
   (expect: `publication_transformation.py`, `commands/transform.py`,
   `test_publication_transformation.py` modified, plus this review's
   temp only; no PUB-05 files modified; no commits/pushes).
   `mission/.writer/writer.db` is git-ignored state (D-PUB-63), never
   committed.

## Verify the failure-injection claims (must-fail tests, fix-batch hardened)

- Stale fingerprint / stripped anchor / unknown op / same-span conflict →
  boundary executable false (tests pin each).
- Evidence-rev missing / unbound plan with mutating refs / states missing /
  digest missing → boundary executable false (no silent pass).
- Bare accept without binding → `adjudication_unbound` (no promotion);
  stale adjudication → `adjudication_stale`.
- Reworded byte-true line → verify fail; substring-embedded line →
  verify fail (placement proof); re-paragraphed (line-preserving)
  split → verify pass; unresolved dropped → fail; added strengthening
  sentence → `new_sentence_honesty` fail.
- `request_application` without approval / QC binding / downstream
  binding / live fingerprint → blocked; with all bound → `fixture_only`
  (never `applied: true`); staged change-set is design-only.
- Ambiguous + overlapping + short-substring (<24 chars) surgical edits
  refused; nested fences use long fences. Real-applier short-substring
  regression passes (SKIP, no splice).

## Judge

ACCEPT / CONDITIONAL (numbered must-fix with file+line) / BLOCKED.
Record model id, provider route, dispatches (expect 0 engine),
spend ($0). Confirm the PUB-05 regression set is untouched (no PUB-05
file modified). Reproducibility inputs shipped in `pub06/ch01/`
(`plan-ch1.json` 46 ops + `adjudications-ch1.json` bound + live
states/digest + boundary/packages gate files).

> SUPERSEDE NOTE (coordinator, post-review): the counts above describe
> the fix-batch tree (60 suites, 258 neighbours, 38→35, `c54258e8…`).
> Final verification ran on the close-out tree: transformation 76 +
> CLI 2 green, neighbours 260+1xfail, live Ch1 21/21 pass, candidate
> `f6c1cbf4…` (606 lines), complexity 38→39 with no HIGH (PUB-04
> structural-break fix removed the cross-table false positive),
> book-wide 1073 unchanged. `before-after.md` was rewritten for the
> final bytes. Review-pack prompts are preserved as issued.
