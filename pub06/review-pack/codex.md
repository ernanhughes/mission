# Codex review prompt — PUB-06 integration + architecture, fix-batch delta (gpt-6-luna)

You are re-reviewing programme PUBLICATION Stage PUB-06 fix batch
(governed editing + manuscript transformation) for
integration/architecture acceptance. Prior verdict: BLOCKED (a–f + 2
editorial). This delta addresses all six architectural residuals plus
the two editorial items; confirm each is closed with file:line
evidence, or re-BLOCK with numbered residuals. Read-only: do not modify
any tree. Authoritative manuscript `C:\books\jev` must be unchanged
(verify `git status` clean apart from pre-existing untracked `scripts/`).

## Canonical context (read first, in this order)

1. `C:\Projects\mission\docs\programmes\publication\` — all 7 files
   (README lifecycle, ARCHITECTURE incl. U1, CAPABILITIES incl. fix
   batch, ROADMAP PUB-06, STATE §3/§6 fix-batch, ACCEPTANCE PUB-06
   gate, DECISIONS D-PUB-56…63).
2. Changed implementation (fix batch):
   - `C:\Projects\writer\packages\writer-core\writer_core\analysis\publication_transformation.py`
     (D-PUB-56…61: QC/downstream binding, freshness, digest/states,
     adjudication binding, preservation auth, dependency order, vocab
     map, placement proofs, new-sentence honesty, surgical ≥24 chars,
     staged design-only, hash-chain)
   - `C:\Projects\writer\packages\writer-cli\writer_cli\commands\transform.py`
     (`check|package` wire `--inventory-digest`,
     `--reconcile-states`, `--adjudications`)
   - `C:\Projects\writer\tests\core\test_publication_transformation.py`
     (35→60: all hardening pinned)
3. Stage artifacts (derived, in `C:\Projects\mission\pub06\`):
   `ch01/01-chapter-candidate.md` (fp `c54258e8…`, 604 lines),
   `ch01/assets/fig-01-2-paths.svg` (per-lane honesty),
   `ch01/verification-report.json` (21/21),
   `ch01/transformation-record.json` (hash-chain),
   `ch01/before-after.md` (concurs with Claude/Codex),
   `ch01/diff.txt` (178), `ch01/plan-ch1.json` (46 ops) +
   `ch01/adjudications-ch1.json` (17 bound) + live states/digest +
   boundary/packages gate files, `passages/P-07-ch07-pointer.md`,
   `passages/P-09-ch09-staccato.md`, review pack (this directory,
   incl. `claude-report.md`), fixture evidence (below).

## Verify the six architectural residuals (each must be closed file:line)

(a) `request_application` binds QC/downstream itself (no caller-verdict
accept), enforces freshness unconditionally (no fingerprint-optional
bypass); staged VFS change-set is an explicit design-only object with a
hard `fixture_only` gate (no silent design-as-implemented).
(b) Boundary: `inventory_digest` bound/required; `evidence_rev`
mandatory for referenced claims (no "unbound" bypass for mutating ops);
`reconcile_states` required (no silent pass); CLI supplies live
states/digest; adjudications need freshness/context binding (bare
accept/modify insufficient); plan+preservation rehydration/auth at the
boundary (consistently-edited references/obligation-stripping detected);
dependencies compile into execution order.
(c) `compile_work_packages`: invokes/requires boundary validation; uses
`chapter_text`; orders by dependencies; `blocked` derived from gates
(never False by default); adjudication promotion needs freshness+context.
Op vocabularies aligned by explicit map (`_OP_ALIASES`;
`REWRITE_FOR_CLARITY`/`ADD_WORKED_EXAMPLE` accepted, `REWRITE_PASSAGE`
canonical).
(d) Preservation verifier: unresolved-evidence obligations enforced
independently; byte-true proves placement (full-line, not
substring-anywhere); no-change spans prove contiguous placement.
(e) Surgical exactness matches `apply_edits.py` (exact inline ≥24 chars;
shorter → full-block or refuse); short-substring real-applier regression
passes (0.978-style fuzzy short text refused).
(f) Record hash-chain binds package hashes, retains before/after
fingerprints, asserts verification-after == recorded candidate
fingerprint (builder guarantees the chain).

Plus 2 editorial: Tam L296-299 sense ("what format restrictions do to
task performance"); Fig 1.2 caption/alt + SVG L3/L72 per-lane 25-char
distinction (predicate True/abstain, stub nothing; 25 chars = serialized
example payload).

## Execute (report commands + results)

1. U1 settlement (D-PUB-53/56): Workbench `chapter_apply` sole
   production; VFS staging design-only; `request_application`
   `fixture_only` with bound gates.
2. Ownership/reuse: compose (not fork) `reader_legibility`, PUB-02/03/
   04/05, `typed_task` seam, `qc`/`manuscript_ir`, VFS/Workbench.
3. Boundary: try to break it — hand-edited plan/refs, stale
   fingerprint, stripped anchor/obligation, unknown op, same-span pair,
   missing evidence-rev/states/digest, bare adjudication, dependency
   cycle.
4. Candidacy hash-chain: plan → packages (`package_hash`) → candidate
   → verification (before/after) → record (`chain` asserted).
5. `verify_candidate`: score-gaming fail; SPLIT pass / reword fail;
   substring-embedded fail; unresolved dropped fail; strengthening new
   sentence fails (`new_sentence_honesty`).
6. Surgical: long-fence + exact-unique + overlap + ≥24-char block-or-refuse
   vs real `apply_edits.py`; short-substring real-applier SKIP.
7. Run: `tests/core/test_publication_transformation.py` (expect 60
   passed) + neighbours 258 + 1 xfail from `C:\Projects\writer`.
8. Fixture gate: disposable end-to-end + short-substring refusal with
   real `apply_edits.py --diff/--apply --no-backup`; fingerprint proof +
   byte-identical undo.
9. Source safety: Jev clean; writer shows only the 3 intended files;
   `mission/.writer/writer.db` git-ignored (D-PUB-63); no PUB-05 files
   modified.

## Judge

- APPROVE / CONDITIONAL / BLOCKED with numbered residuals, each with
  the exact file + line + required change. Preserve disagreements.
- Confirm or dispute: catalog 167 (no manifest); zero engine dispatches
  ($0, editorial spend separately recorded); no commits/pushes; no
  production figures overwritten; no Mission UI; PUB-07 not begun.

> SUPERSEDE NOTE (coordinator, post-review): the numbers above describe
> the fix-batch tree. Final verification ran on the coordinator
> close-out tree: transformation 76 + CLI 2 green, neighbours
> 260+1xfail, live Ch1 21/21 pass, candidate `f6c1cbf4…` (606 lines),
> complexity 38→39 (no HIGH), book scan unchanged at 1073. The
> `before-after.md` assessment record was rewritten for the final
> bytes; `diff.txt` predates the polish edits (deltas listed verbatim
> in before-after.md). Review-pack prompts are preserved as issued.
