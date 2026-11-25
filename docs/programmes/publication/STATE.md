# PUBLICATION State

**Updated:** 2026-11-25 (PUB-07 ACCEPTED 8/12; PUB-08 authorized and active — reuse research + experimental design. No PUB-08 paid inference authorized yet.)

## 1. Current position

PUB-07 ACCEPTED 2026-11-25 on three rerun-bound deltas (Codex ACCEPT;
DeepSeek CONDITIONAL doc residual fixed in-session; Claude accept with
optional line-155 style polish carried to promotion). Demonstration
candidate: `pub07/ch02-rerun/candidate.md` (`9f36c9ba…`, 355 lines,
verify 15/15, review_accepted, $0.0039864). Run-1 preserved as
history. Full gate 592+1xf/593, catalog 167, Jev `c7aaad7` clean.
PUB-08 (semantic verification, calibration, reader comprehension)
authorized by the author; primary implementation agent Muse; paid
experimental arms BLOCKED pending an explicit inference budget.
PUB-00 ACCEPTED. PUB-01 ACCEPTED 2026-11-24 on independent verdicts:
Codex (architecture/integration) CONDITIONAL — validation-invocation
reproducibility + D-PUB-08 schema/retry wording, both fixed docs-only in
CAPABILITIES/DECISIONS/ACCEPTANCE (no code touched); DeepSeek
(regression/verification) ACCEPT — 86+1 / 114 / 30 suites reproduced, sole
quality failure proven pre-existing and catalog-independent, registry 167
with scoped validation holding, source safety + read-only holds confirmed.
Production code changed in exactly one file for scoped registry
reconciliation: `C:\Projects\writer\…\capabilities\catalog.py` (+2 manifests).
Programme docs changed only in `docs/programmes/publication/` (7 canonical
files, this file included). No manuscript changes, no paid model runs, no
migrations, no deploys, no commits/pushes, no unrelated refactoring, no
deletion of unrelated files. Docs created (canonical set only):

- `docs/programmes/publication/` — README, ARCHITECTURE, CAPABILITIES,
  ROADMAP, STATE (this file), ACCEPTANCE, DECISIONS.

## 2. Accepted into the programme

- Objectives, scope, end-state workflow (§10 twelve-step flow adopted as the
  design target), lifecycle, agent defaults, calibration direction, ~950/1000
  with critical-defect override.
- Architecture grounded in live source with cited paths; ownership table;
  U1–U5 explicitly open.
- Capability inventory: reusable-now vs extend vs missing, with entry points,
  determinism/mutation behaviour, and three live verifications (catalog build,
  editing scorer on Jev Ch1, legibility analyzer on Jev Ch1).
- Taxonomies: CR01–CR12 cruft; complexity signal list; representation ladder;
  twelve-step editorial workflow; Mission section requirements — all adopted as
  calibration/design inputs, none treated as established measures.
- Stage IDs PUB-00…PUB-11 with dependencies and per-stage gates.
- PUB-01 additions: 14-step repeatable stage contract (README §5);
  CR01–CR12 one-line decision rules (CAPABILITIES §6); AI primitives inventory
  with PUB-02/03/04 reuse verdicts (§7); registry reconciliation with
  classifications (§8, catalog 167); quality-surface decision D-PUB-07
  (CLI-only + unblock plan); model-routing contract D-PUB-08 (no new gateway);
  reconciliation principle D-PUB-09; provenance/label conventions
  (ACCEPTANCE §2.1); Jev decision table for PUB-03 (ROADMAP PUB-03);
  working Writer test invocation + focused/regression results (§4.3).

## 3. Active work

PUB-07 scope-done 2026-11-25 (Muse implementation), pending review
gate. Production-path automation (`publication-automation-v0.1`,
`automation-v0.1` UNCALIBRATED) + `writer transform automate` CLI
(existing group, no catalog change) + additive record `dispatch_ledger`
(D-PUB-77) + Workbench `publication_proposals` bridge (D-PUB-78):
one dispatch per package via the D-PUB-08 seam (Writer prompts +
contracts, Worker providers/transport/usage/cost), quote discipline,
per-line origin lineage, bounded correction loop (<= 5 dispatches,
explicit termination), $10 spend cap, independent-family review
(deepseek-go generate, haiku-go review). Tests: 19 automation (fakes,
zero live) + 5 CLI incl. 3 automate pins + 10 bridge; fast gate 560
passed + 1 strict xfailed (held-cx15) / 0 failed; ruff clean.
Live end-to-end (Jev Ch2 `c7aaad7`, 346 lines): boundary executable
(44 boundary_ok + 2 isolating), 10 packages, ONE bounded package
executed (ops 006/007, lines 133-146). 4 dispatches, $0.00706,
25,504 tokens; candidate 338 lines, verify 15/15 pass, chain fp
`50e1ef2e…`; loop terminated honestly (verify-pass, review
request_changes x2 on LLM2Jev substance, final verdict invalid on a
quote failure -- all recorded, none redriven). Presented
`pending_author_decision` (pub07/ch02/approval-decision.json); fixture
apply/undo byte-proven; Workbench proposal pending + fresh; staged
change-set design-only. Zero authoritative mutation; Jev clean; no
commits. Decisions D-PUB-76…80. Spend split editorial vs
verification kept in the ledger. Full detail: CAPABILITIES.md PUB-07
subsection. Previous PUB-06 record below retained; do not reopen
without evidence of a consequential defect.

PUB-07 fix batch complete 2026-11-25 (Muse implementation, D-PUB-81;
single combined batch for the Codex BLOCKED-4 + DeepSeek F1-F5 + Claude
CONDITIONAL residuals; no commits). Code + pins done, fast gate green
(583 passed + 1 strict xfailed held-cx15 / 0 failed at fix-batch time,
superseded by 592 passed + 1 strict xfailed / 593 collected on the
settled tree after the coordinator close-out's +9 pins — see §6;
workbench neighbours 35/0; ruff clean): review-excerpt scoping to the
replacement lineage range (Fix A), rebind-before-final-review with
excerpt-exact validation + per-round binding revalidation failing
closed on mismatch (Fix B), pre-dispatch spend guard with
explicit override bookkeeping (Fix C), ledger
replacement-sha + record `chain.ledger_digest` + bridge refusal of
unbound ledgers + replacement-hash freshness + record-chain reference
(Fix D), paragraph-break assembly + no-gloss/no-section-citation
prompt rules (Fix E), LF/slash canonical digest forms (Fix G).
Run-1 artifacts preserved verbatim in `pub07/ch02-superseded-run1/`
(+README: stale-window + spurious-quote-failure analysis). The 08:48
UTC re-run attempt into a temp dir was Worker-BLOCKED
(authentication_failed, no API key for opencode-go, non-retryable;
$0 spent, 0 tokens) -- infra outage, not a code defect. The bounded
re-run was then EXECUTED by the coordinator in a credential-bearing
shell (see §6): outcome review_accepted, 2 dispatches $0.0039864,
verify 15/15, candidate `9f36c9ba…` 355 lines in `pub07/ch02-rerun/`;
`pub07/ch02/` on disk still holds the run-1 bytes pending the
author's promotion decision. Fix F annotations + doc-number refresh
(done, see §6) landed on the re-run's records, not by editing
history.

PUB-05 ACCEPTED 2026-11-24 by author (§11). PUB-06 fix batch 2026-11-24
(Muse implementation, addresses Codex BLOCKED a–f + 2 editorial and
Claude BLOCKED-narrow must-fix P1/P2/P4/P5/P8 + should-fix P3/P6/P7/P9/
P10; DeepSeek ACCEPT carried) + close-out 2026-11-24 (coordinator:
Codex delta-confirm residuals + Claude R1/R2/R4/R5; verified green,
no new review cycle per README §6). Deterministic transformation boundary
(`publication-transformation-v0.1`, profile `transform-v0.1`
UNCALIBRATED) + `writer transform check|package|verify|surgical` CLI
(library+CLI, no catalog change, zero engine dispatches):
execution-boundary revalidation (blocking vs isolating, freshness
unconditional, digest/states mandatory, adjudication binding,
preservation auth, dependency cycles), dependency-ordered three-scale
work packages (blocked derived, vocab map), placement-proof preservation
verification (byte-true full-line, no-change contiguous,
unresolved-independent, new-sentence honesty) with anti-gaming rule,
real-applier surgical exactness (≥24 chars, block-or-refuse), staged
design-only guarded application with QC/downstream binding (D-PUB-56…
63, fix batch 2 D-PUB-65…67). Tests: 74 + 2 CLI green; neighbours 260 + 1 strict xfail (held-cx15,
PUB-04), 0 failed. Live: Ch1 plan revalidated executable (44
boundary_ok + 1 evidence_held + 1 investigation-only) with live
states/digest + 17 bound adjudications; 7 packages / 17 isolated / 12
respected; revised Ch1 candidate (`f6c1cbf4…` 606 lines -- recorded
`bb95457e…`/`c54258e8…` superseded by post-record drift, chain rebuilt
fix batch 2 + close-out, see §6), verification pass 21/21, cruft 1→1
(11→12 preserved), complexity 38→39 (recorded 38→35 then 38→40
superseded; the "new HIGH" was a cross-table false positive removed by
the PUB-04 structural-break fix -- verified gone, CX10 1→1) + Figure 1.2 SVG (per-lane honesty, naive-index qualifier,
four-lane desc, after Fig 1.1) + Willard table (both spec-validated) +
before-after (assessment record updated to current bytes; R5 revert
noted; `diff.txt` predates polish, deltas listed verbatim) + provenance
record with hash-chain in `pub06/ch01/` (plan-ch1.json +
adjudications-ch1.json + live states/digest + boundary/packages gate
files shipped); bounded passages P-07 + P-09 in `pub06/passages/`;
review pack (refreshed Codex/DeepSeek/Claude prompts + Claude report
`claude-report.md` + mediated probe, still specified-not-executed) in
`pub06/review-pack/`; disposable-fixture apply_edits.py end-to-end
(2/2 ratio-1.000, fingerprint `441a51…`→`7576d7…`, byte-identical undo,
ambiguous + short-substring refusal). `mission/.writer/writer.db`
(13 MB, CLI/test state) is git-ignored, never committed; Jev ignore
untouched; Temp evidence cleaned. Decisions D-PUB-53…68. Full detail:
CAPABILITIES.md PUB-06 subsection. Prior PUB-05 scope record retained
below; do not reopen without evidence of a consequential defect.

PUB-05 scope-done 2026-11-24 (Muse implementation), pending review
gate. Deterministic pedagogical planner (`publication-pedagogy-v0.1`,
profile `pedagogy-v0.1` UNCALIBRATED) + `writer pedag plan|validate`
CLI (library+CLI, no catalog change, zero dispatches): PD01–PD16 with
support statuses, preservation-before-planning, plan/validator/
freshness contracts, materiality-scoped blocking, representation
selection with pipeline caveats. Tests: 50 unit + 23 calibration
(10 dev + 12 held incl. 6 fresh once-only held-2) = 73 green;
neighbours 457 collected (456 + 1 strict xfail held-cx15, PUB-04),
0 failed; ruff clean. Live: Ch1 46 ops (11/17/6/9/3, validates),
Ch2 46, Ch7 49, Ch9 62, book 36 chapters / 1398 structural ops
(all validate). Decisions D-PUB-39…51. Full detail:
CAPABILITIES.md PUB-05 + fix-batch subsections. PUB-04 record (accepted §10)
below is retained for provenance; do not reopen without evidence of a
consequential defect.

PUB-05 fix batch 2026-11-24 (Muse implementation; addresses the Codex
CONDITIONAL 4 residuals + the DeepSeek record-number correction;
verified by coordinator -- see fix batch 2 below):

- Validator authority (D-PUB-49): exact content anchors on every op
  (`anchor_sha256`; KEEP retarget to a different in-range span fails
  `span_anchor_mismatch`); preservation enforced on attached
  obligations (stripped lists fail `preservation_gap`); execution-ready
  reconciled against refs/blockers, skew fails
  `evidence_needs_mismatch` (16 validator codes: 14 actual + 2 new;
  the "12" was a counting error). Freshness binds reconcile states +
  intent contents + reader-context values + render-cap values.
- One-primary honesty (D-PUB-50): CX13 REORDER is
  `investigation_only`, never a primary, forced `candidate` -- PUB-06
  cannot consume it as a second transformation. Label-token guard kept
  planner-side heuristic with documented scope.
- Correction path (D-PUB-51): UPDATE_FROM_VERIFIED_EVIDENCE only with
  a linked correction proposal + evidence; else evidence-gated
  INVESTIGATE (reproduced superseded-without-payload case emits no
  UPDATE). Grouping retains correction + evidence refs + provenance.
  INVESTIGATE honours the D-PUB-47 read-only exemption under
  conflicted/contradicted evidence.
- Record correction: re-ran all four chapter plans on the fixed tree --
  Ch1 46 (11/17/6/9/3), Ch2 46, Ch7 49 (UPDATE stands: live superseded
  carries correction + evidence), Ch9 62 -- every count confirms
  DeepSeek exactly; the pre-fix record was hand-tallied wrong. Book
  scan 1398 exact (only delta: 31 investigation-only REORDERs moved
  adjudication-ready 280→249 + 31 candidate). All 40 plans validate.
- CLI docs: INDEX.md hand-updated to 58 rows / 855 nodes (no generator
  run -- owning-team collision boundary stands); coverage 3/4 with the
  sole failure the 5 pre-existing owning-team gaps
  (book-campaign, strategy-evolution, quality, validate-site-links,
  reader-legibility), recorded not fixed.

PUB-05 fix batch 2 2026-11-24 (coordinator-executed; addresses the Codex
delta re-review's 2 deeper residuals on the fix-batch tree; verified
in-session, no review cycle per README §6 two-round policy):

- Anchor presence (D-PUB-52): span-carrying op without `anchor_sha256`
  now fails `span_anchor_missing` (never grandfathered). 2 pins
  (mismatch + missing); validator now 17 codes (record corrected).
- Linked-evidence UPDATE gate (D-PUB-52): `or provenance` fallback
  removed; correction + binding with zero evidence refs routes to
  evidence-gated INVESTIGATE. Existing no-payload / payload-without-
  evidence pins still pass; new binding-without-evidence pin added.
  Live Ch7 UPDATE (ledger refs present) unaffected.
- Suites: pedagogy 75 green; fast gate 459 passed (457 + 2 new) /
  0 failed; ruff clean. Live (Jev `c7aaad7`): Ch1 46 (11/17/6/9/3),
  Ch2 46, Ch7 49 (UPDATE present, evidence_blocked per pre-existing
  status logic), Ch9 62, all validate clean; catalog 167; Jev clean;
  $0; no commits.
- Exact live invocations (CWD `C:\Projects\writer`, venv python,
  `--book-root C:\books\jev`; per chapter NN in 01/02/07/09):
  `writer cruft review jev NN-chapter --json`,
  `writer complex review jev NN-chapter --json`,
  `writer reconcile chapter jev NN-chapter --json` (chapter-scoped
  inventory; revs Ch1 `jev@bbbb73b55d7668a8`, Ch2
  `jev@899c02ad76215729`, Ch7 `jev@a6cd2b879ef9ae6a`, Ch9
  `jev@d3c457a3af1aa23b`),
  `writer pedag plan jev NN-chapter --cruft-report … --complex-report …
  --reconcile-report … --intent C:\books\jev\metadata\NN-chapter.yaml
  --inventory-rev <rev> --json`,
  `writer pedag validate plan-NN.json jev NN-chapter --book-root …`.
  Book scan: same cruft+complex chain per chapter 01–36 with
  `pedag plan` on cruft+complex reports only (no reconcile/intent).
- Suites: pedagogy 73 green (50+23); combined neighbours 457 (456 +
  1 strict xfail); capability short 1 + 1 deselected; catalog 167;
  fingerprint `435974701050…` unchanged; Jev `c7aaad7` clean
  (pre-existing `scripts/` only); zero dispatches; $0; no commits;
  temp cleaned. Held-evaluation limitation kept candid (6 synthetic
  held-2 ≠ generalisation; profile uncalibrated).

PUB-04 fix batch 2026-11-24 (Muse implementation; addresses the Codex
BLOCKED findings-contract defects + DeepSeek F1/F2/F3/F7 must-fix;
F4/F5/F6/F8/F9 documented as PUB-08-owned traps; pending Codex +
DeepSeek delta re-review):

- Span contract (code + README + pins): char spans locate quoted
  evidence (sentence/term/block per detector; CX07 lines bracket the
  use→define gap); zero-spans never emitted (unlocatable →
  needs-context locator miss). CX07 now carries real term-occurrence
  spans.
- Related linkage AFTER severity-preserving dedupe (max severity per
  key, tie first): book-wide dangling refs 312→0 (Ch1 12→0); CX04 HIGH
  roll-up and longer-CX10-run reachability pinned.
- `concept_index`/`glossary_terms` RESOLVE CX07 terms (established
  vocabulary = quiet); old pretend-test rewritten to pin resolution.
- `_is_html_block` narrowed to structural tags; `_is_list_block`
  narrowed to list-structured (wrapped continuations belong to the
  list); genuinely mixed blocks assessable; CX14 probes prose lines.
- `generated_at` volatile, excluded from replay identity
  (`replay_identity()` + test); `review --cx` rescopes with recomputed
  summary (live CX02 8/8, DeepSeek 1-vs-38 gone); `compare` text mode
  shows `max_severity`. held-cx15 now a STRICT behavioural xfail.
- Counts: writer INDEX 48→51, README 50→51.
- Suites: complexity 94 passed + 1 xfailed (was 83 + 1); combined
  neighbours editing+quality 87 + cruft/legibility/complexity 197 =
  284 passed + 1 xfailed, 0 failed; capability 8 passed + 1 deselected
  (long corpus); mediated/eval 114 deferred (long, untouched). `ruff
  check` clean (format drift pre-existing, untouched). Catalog 167;
  fingerprint `435974701050…` unchanged.
- Live (Jev `c7aaad7`, read-only): Ch1 → 38 findings, IDENTICAL finding
  set to baseline (dangling 12→0 the only change); book scan → 36
  chapters, 1083 findings, zero per-chapter deltas, dangling 312→0;
  Ch7 clause-heavy (CX02×16/CX03×18) intact — no whole-section
  suppression. Zero dispatches; $0; trees clean; no commits/pushes.
- Decisions D-PUB-29…34 recorded. Full detail: CAPABILITIES.md
  PUB-04 fix-batch subsection.

PUB-04 fix batch 2 2026-11-24 (Muse implementation; addresses the Codex
delta re-review's 2 precise residuals on the fix-batch tree; pending
Codex + DeepSeek delta re-review):

- CX10 invalid span: run sentences located forward from the run's own
  start (`_locate_span(..., start=...)`); a later HIGH run whose final
  sentence also occurs earlier in the block quotes its own occurrence
  (pre-fix reproduced char_start>char_end; post-fix valid start<end).
  Pin: `test_later_cx10_run_with_repeated_final_sentence_keeps_valid_span`.
- Wrapped continuations: `_prose_lines()` excludes list lines AND their
  indented continuations from CX10/CX11/CX14 probes in mixed blocks;
  CX11 quotes the probe when the block carries list lines. Pins:
  continuation-only load → no CX10/CX11; genuine prose in the same block
  still assessed with a probe-only quote; CX14 never quotes a
  continuation.
- Docs: span contract (module + complex README) states the forward run
  anchor and the prose-probe/quote rule; `--cx` rescoping documented as
  chapter-scoped preserved/needs-context/concept counters; held-cx15
  rationale 38→39 words (1-word margin, verified via `word_count`).
- Suites: complexity 98 passed + 1 strict xfailed (94 + 4 new pins);
  combined neighbours 280 passed (editing+quality 87, cruft 46+40,
  legibility 17, evidence 50+40); capability 8 passed + 1 deselected;
  mediated/eval 114 deferred (long, untouched); `ruff check` clean.
  Catalog 167; fingerprint `435974701050…` unchanged. Live (Jev
  `c7aaad7`, read-only): Ch1 → 38 findings, IDENTICAL by-CX set to
  baseline; book scan → 36 chapters, 1083 findings, 0 dangling, 0 bad
  spans; Ch7 CX02×16/CX03×18 intact; `--cx CX02` → 8/8 chapter-scoped
  counters intact. Zero dispatches; $0; trees clean; no commits/pushes.
- Decisions D-PUB-35/36 recorded (D-PUB-35 run-span anchoring, D-PUB-36
  prose-probe exclusion). `INDEX.md`/`README.md` counts untouched by
  instruction (owning-team flux; DeepSeek R1 stays backlog).

PUB-04 fix batch 3 2026-11-24 (coordinator-executed; addresses the Codex
delta re-review's 2 deeper edge residuals on the fix-batch-2 tree),
extended in-session with the cross-structural seq break (see below):

- CX10 run findings require located occurrences: new `_strict_locate()`
  (verbatim forward search, `None` on miss -- never a fallback span);
  the run branch declines runs with any unlocatable sentence
  (D-PUB-37). Pre-fix fallback accepted a whole-block span as a run
  endpoint when line filtering removed the probe's context.
- Probes are contiguous segments: new `_prose_segments()` (identical
  membership to `_prose_lines`, which now delegates to it); CX10 runs,
  CX11 and the CX14 opening probe each measure one segment, so prose
  is never joined across a removed list boundary (D-PUB-38). CX11
  quotes its own segment text; CX14 probes the opening segment.
  Same-block dedupe (max severity per `(cx_id, start_line)`) unchanged:
  two same-block runs still collapse to one, now with a side-local
  quote and truthful run_length (pins assert run_length 3/MEDIUM, not
  the joined 6/HIGH).
- Pins (5 new): cross-boundary no-join, segment-local CX10 span,
  segment-local CX11 quote, opening-segment CX14 scoping,
  `_strict_locate` unit pins. Post-verification extension (same
  coordinator session): the consecutive-one-sentence CX10b run now
  iterates ALL blocks and breaks the sequence on structural
  (non-assessable, non-blank) blocks -- previously joined runs across
  tables/code/figures (2 pins: cross-table no-join + blank-gap
  positive control; whitespace-normalisation documented in the span
  contract).
- Suites: complexity 63 unit + 43 calibration (42 passed + 1 strict
  xfailed); full fast gate 467 passed + 1 xfailed / 0 failed;
  `ruff check` clean. Live (Jev `c7aaad7`, read-only): Ch1 38
  findings identical set, book scan 36 chapters / 1073 findings /
  0 dangling / 0 bad spans (-10 removed cross-structural joins; Ch1
  untouched), fingerprint-stable; catalog 167; Jev
  clean; $0; no commits/pushes. Behavioural delta vs batch-2 tree:
  only the removal of non-contiguous cross-structural joins.
- Out of scope (unchanged, recorded): CX10b one-sentence sequences
  still quote joined block texts (block-level, span-bounded; not
  flagged by any review); INDEX/README counts (owning-team flux).

PUB-04 scope-done 2026-11-24 (Muse implementation), pending review gate.

- Deterministic CX01–CX15 screen
  (`packages/writer-core/writer_core/analysis/publication_complexity.py`,
  `publication-complexity-v0.1`, profile `complexity-v0.1` UNCALIBRATED) +
  `writer complex` CLI (`review|scan|compare`; `complex.py` + `main.py`
  registration + `docs/cli/complex/README.md` + INDEX row). Library+CLI
  surface, no runtime domain, no catalog change (D-PUB-24); zero model
  dispatches. Reuses `reader_legibility` spans + `EvidenceRole`, editing
  sentence/word heuristics (mirrored, writer-core stays dependency-light),
  PUB-02 honest-record discipline + typed-task seam shape (D-PUB-08).
- Contracts: Level A observations vs Level B candidates vs Level C
  (never emitted; 8 prepared adjudication payloads for
  CX02/04/06/07/10/11/14/15, dispatched only via the D-PUB-08 seam — zero
  in PUB-04). Per finding: CX id, kind, exact span, chapter/project,
  fingerprint, detector+profile versions, measured features, reader
  burden, correction direction (never prose), preservation notes,
  limitations, related links, no-composite summary with concentrations.
  Coverage reports assessed/unassessed blocks; code/table/figure/HTML are
  structure (CX08 breaks), never prose load. Reader context consumed
  where given, missing profile explicit, unfamiliarity never assumed.
- Preservation in code: honest-record sections + genuine-uncertainty
  markers exempt from tone/load CXs; definition sentences become
  concept events and exempt from CX06 on their own block; methods
  sections exempt from CX12; lists exempt from staccato/avalanche/
  bridge screens; HTML figure blocks unassessed; math spans recorded,
  never clause-parsed.
- Calibration: 41 unit (`test_publication_complexity.py`) + 43
  calibration (30 dev + 12 held entries + split-discipline,
  `publication_complexity_calibration.jsonl`; labels human/synthetic)
  = 83 passed, 1 xfailed. Held evaluated once against the
  frozen profile (no threshold value ever retuned; all pre-freeze work
  was structural precision + fixture-text shaping): 11/12 pass; the one
  miss is a KNOWN-FN pinning case (held-cx15: 39-word block vs the
  40-word floor — absolute-word floors are edge-brittle; PUB-08 should
  consider density-relative sizing). Mandatory staccato regression:
  staccato rewrite fires CX10-high + CX11, never ranks below the
  genuinely-clearer rewrite (max-severity lens, no composite anywhere).
- Live read-only demo, Jev `c7aaad7`: Ch1 → 38 findings
  (CX02×8/CX03×8/CX14×8/CX01×2/CX05×2/CX08×1/CX10×1/CX11×5/CX13×1/
  CX15×1/CX04×1), 10 preserved, 6 needs-context, 9 concept events;
  heaviest concentration L509 (closing question: CX01+CX02+CX04+CX05+
  CX13 → interrupted-argument + qualification-pile-up). Ch7 reads
  clause-heavy (CX02×16/CX03×18); Ch35 longest-sentence-heavy (CX01×9);
  Ch9 staccato-heavy (CX10×9). Bounded book-wide scan: 36 chapters,
  1083 findings, coverage explicit. Before-after on the real Ch1 closing
  block: overloaded 5×medium → staccato 1×high+1×medium (count drops
  5→2 but max severity rises — the no-composite design is what stops
  the staccato cheat) → clearer 0. Fingerprint `435974701050…`.
- Regression (same invocation/CWD as PUB-01): editing+quality+cruft
  (46+40)+legibility+complexity(41 unit+43 calibration) = 273 passed,
  0 failed (1 xfailed, the known CX15 FN);
  capability short 1 passed + 1 deselected; mediated/eval 114 deferred
  (long, untouched paths). Catalog 167; Jev tree verified clean;
  zero dispatches; $0; temp evidence removed.
- Decisions recorded before/during implementation (D-PUB-24…28):
  library+CLI surface, reuse verdicts, no-composite severity semantics,
  CX15 candidate-only, frozen-profile calibration discipline.

PUB-03 ACCEPTED 2026-11-24 by author (§9). PUB-04 scope-done, pending review gate.

PUB-03 scope-done 2026-11-24 (Muse implementation):
- Reusable, repository-aware evidence reconciliation: generic engine
  (`evidence_reconciliation.py`, `evidence-reconciler-v0.1`, profile
  `reconcile-v0.1` UNCALIBRATED) + Jev adapter (`jev_evidence.py`,
  `jev-evidence-v0.1`) + `writer reconcile` CLI
  (`inventory|chapter|book|resolve`). Library+CLI surface, no runtime
  domain, no catalog change (D-PUB-11); zero model dispatches.
- Contracts: 8-state `ReconciliationState` (D-PUB-13, SupportLabel mapping
  documented, state/severity/lifecycle kept separate); 10 claim categories;
  8 correction operations (proposals only, no manuscript modification);
  `Binding` freshness (manuscript + inventory + repo revisions, detector +
  profile + config, model always None) with `check_stale`.
- Authority policy in code (D-PUB-15): validated record > raw complete >
  partial > report-as-lead > absent; later ≠ authoritative without explicit
  supersede record; passing test ≠ hypothesis established; file ≠
  complete/valid/applicable.
- Preservation conditional (D-PUB-14): `evaluate_preservation()` re-checks
  every preserved passage against the current inventory; all Ch1 honesty
  statements UPHELD (no completion evidence anywhere for model arms).
- PUB-02 integration: `to_evidence_index()` projection (provider-as-arm
  translation; chapter ids bare per PUB-02 convention); live cruft review
  Ch1 with real inventory → 1 finding (CR04-LOW, baseline-identical),
  11 preserved, 2 needs-evidence (CR01×2 by frozen no-backticked-arm rule;
  CR02×4/CR12×1/CR06×2 resolve silent). `reconcile resolve` consumes the
  2 items → SUPPORTED (L111 predicate rows) + UNRESOLVED-on-excerpt
  (L493; full-text verdict is PARTIAL conclusion). PUB-02 files untouched.
- Jev demo (read-only, `c7aaad7`, inventory `jev@7f008df8772f677f`):
  chapters 01+02+07+36 inspected, 32 uninspected (coverage partial,
  explicit) → 59 supported / 9 not_applicable / 15 unresolved /
  3 superseded / 3 partial, 0 contradicted/conflicted; 6 correction
  proposals. ≥1 genuinely stale live claim demonstrated:
  Ch7 `run_ch07.py` "To run" reference (file absent at revision, never
  existed; SUPERSEDED + update_impl_description, fully traced row by row).
  Ch1→Ch7 / Ch1→Ch2 forward pointers resolve SUPERSEDED (promise
  materialised; incorporate_results). Unsupported schemas explicit
  (`results/ch32.jsonl`, `results/ch35.jsonl`). Tree verified clean.
- Tests: 38 unit + 38 calibration (23 dev + 15 held-out, frozen rules,
  held-out from uninspected Ch3/Ch8 prose + novel synthetics) = 76 passed.
  Fast neighbours 190/190 green (editing+quality 87, cruft 86, legibility
  17); capability short test 1 passed; CLI surface verified. Mediated/eval
  114 deferred (long, untouched paths). Catalog-CLI "30" suite names gone
  (owning-team reorganisation — recorded, not a regression).
- Decisions recorded before implementation (D-PUB-11…18) plus D-PUB-19
  (selftest execution as read-only inspection; static 52 sites vs runtime
  53 executions) and D-PUB-20 (binding precision rules, each added after a
  live false bind and pinned by regression tests). $0 model spend; zero
  dispatches; Jev and all repo trees clean of strays, no commits.

PUB-03 fix batch 2026-11-24 (Muse implementation; addresses the Codex
BLOCKED 5 points + the DeepSeek carry-forward, pending Codex + DeepSeek
delta re-review):
- Chapter-scope rule (D-PUB-21): named arm binds completion rows only
  within the claim's chapter unless the claim explicitly references
  cross-chapter evidence or the experiment identity is globally unique
  in the inventory (stated in code + docs); 7 cross-chapter regression
  tests (adjudication + preservation, incl. positive controls).
- State-mapping comment completed (SupportLabel orphans, no direct
  conflicted counterpart, `check_stale` returns triggers not a
  FreshnessStatus value, nothing serialized).
- Selftest hardening (D-PUB-22): validated explicit script set (no
  dynamic glob), per-script 120 s cap PLUS 300 s total inventory
  deadline, post-run clean-tree verification in inventory notes;
  Ch1/Ch2/Ch7 counts (53/27/87) green.
- CLI `reconcile resolve` envelope validation (`_unwrap_cruft_report`:
  null/malformed result → clean exit 1, never traceback-out) + 2 tests.
- Reuse honesty: `argument.disagreement` lineage stated as conceptual,
  not a code dependency (module + `_find_conflict` docstrings, D-PUB-12).
- CLI docs for `reconcile` + `cruft` added (INDEX 48→50); 5 remaining
  missing docs are pre-existing owning-team backlog — recorded, not fixed.
- Suites: `test_evidence_reconciliation` 85 passed (76 + 9 new);
  editing+quality+cruft+legibility combined 190 passed; capability
  short 1 passed + 1 deselected. Live re-verification: `reconcile book`
  01,02,07,36 → 59/9/15/3/3 @ same inventory rev
  `jev@7f008df8772f677f`, repo `c7aaad7`; `cruft` Ch1 → 1/11/2; catalog
  167; Jev clean; zero dispatches; no manuscript/evidence edits, no
  commits/pushes, temp cleaned.

PUB-03 fix batch 2 2026-11-24 (Muse implementation; applies the Codex
delta re-review's 2 residuals post-acceptance — execution removal +
README count — see §9; handed back for the record, no review cycle
required):
- Execution removed (D-PUB-23, supersedes the D-PUB-19 execution
  allowance, retires the D-PUB-22 hardening): `jev_evidence` no longer
  executes repo scripts (`_run_selftest_count`, `_validated_selftests`,
  `_tracked_dirty` and the 120 s / 300 s / 32-script / 1 MB constants
  deleted; `sys`/`time` imports dropped; no opt-in flag, no new execution
  mechanism). Each chapter-referenced selftest now yields a computed_fact
  with `execution={"runtime": "unavailable", "static_sites": N}` plus an
  explicit `runtime_unavailable` validation note and inventory note.
  Static call-site counts kept as pure parsing (Ch1/Ch2/Ch7: 52/17/73).
  Sandboxed re-execution recorded as deferred future work.
- Engine (`evidence_reconciliation.py`): `_runtime_unavailable` screen —
  a claim naming a selftest script and stating its check count
  (`selftest` + number + `checks`) with a bound unavailable marker
  resolves UNRESOLVED with an explicit D-PUB-23 rationale, in both
  `_adjudicate_status` and `_adjudicate_result` (the latter covers the
  Ch7 measurement-shaped 87-checks claim). Claim-gated, so neighbours
  that merely share a topic word keep their normal verdicts (pinned by
  `test_neighbour_sharing_topic_word_is_not_hijacked`); unavailable
  markers are excluded from `_explained_numbers`, so static numbers
  verify nothing and absorb no claimed count.
- Tests: `test_evidence_reconciliation` 50 passed (47 + 3 new pins) +
  calibration 40 (23 dev + 15 held-out, with the two `dev-selftest-*`
  entries renamed `*-unresolved` and re-pointed at unavailable markers)
  = 90 passed. Combined fast neighbours 190 green; capability short
  1 passed + 1 deselected. CLI docs coverage (final state, `docs/cli`
  under active owning-team edits throughout the session): 1 passed / 3
  failed — `has_docs` missing the 5 batch-era gaps (book-campaign,
  strategy-evolution, quality, validate-site-links, reader-legibility);
  `index_lists` missing those 5 + the validate-rendered-math row;
  `count` 48-vs-57 (stale total). Reconcile + cruft rows AND README dirs
  (batch outputs) are present; the newly registered `complex` command is
  documented. Remaining failures are owning-team backlog only —
  recorded, not fixed (same category as the batch report). README set to
  50 exactly as specified. No further `generate_cli_docs.py` runs from
  this stage: the script rewrites the owning team's active work area
  unconditionally, and two in-session runs demonstrably collided with
  their concurrent edits; their hand state stands.
- Live re-verification (Jev `c7aaad7`, read-only, tree verified clean —
  only pre-existing untracked `scripts/`): `reconcile book` 01,02,07,36
  → 57 supported / 17 unresolved / 9 not_applicable / 3 superseded /
  3 partial (89 claims; per chapter — 01: 35 claims 22/5/4/2/2 corr 4;
  02: 14 claims 7/4/2/0/1 corr 1; 07: 28 claims 22/4/1/1/0 corr 1;
  36: 12 claims 6/4/2/0/0 corr 0), 6 corrections. Delta vs the batch
  tree is exactly the two execution_status selftest-count claims (Ch1 53,
  Ch2 27) SUPPORTED→UNRESOLVED; the Ch7 87-checks measurement claim was
  already UNRESOLVED (no complete rows ever bound) and keeps its state
  with the explicit unavailable rationale. One mid-session transient
  (a per-chapter run disagreeing with six mutually-consistent
  measurements) is recorded but not reproducible — three consecutive
  book runs plus four per-chapter runs agree exactly. Inventory rev
  `jev@6c13d2837f138c84` (changed from `jev@7f008df8772f677f` because
  entry digests feed the rev hash — `"53"` → `"unavailable/52"` — while
  notes do not; Ch1/Ch2/Ch7 notes now read `runtime=unavailable (not
  executed, D-PUB-23); static_sites=52/17/73`). `cruft` Ch1 with real
  inventory → 1/11/2 (fingerprint `435974701050…`,
  baseline-identical). Catalog 167. Zero model dispatches; $0; no
  manuscript/evidence edits, no commits/pushes, temp cleaned. Writer
  HEAD `101b88336`; Jev HEAD `c7aaad7`.

PUB-02 scope-done 2026-11-24 (Muse implementation), fix batch 2026-11-24:
- Entry re-baseline confirmed: `test_direct_rejects_invented_citations` still
  the sole quality failure (86+1 identical to PUB-01; catalog-independent,
  pre-existing); mediated_read/evaluation_fabric/capability 114 passed;
  catalog CLI suites 30 passed; `tests/core/test_reader_legibility.py`
  15+2 (2 failures pre-existing in the untouched reproduction_readiness
  evaluator path — PUB-01 never ran this file).
- CR01–CR12 deterministic classifier (`publication_cruft.py` v0.1,
  profile `cruft-v0.1` UNCALIBRATED) + `writer cruft review` CLI; no catalog
  change (library+CLI, D-PUB-10); zero model dispatches.
- 27 unit + 40 calibration tests pass (29 dev + 10 held-out + split-discipline;
  held-out evaluated once against the frozen profile, never tuned).
- Live read-only demonstration: Jev Ch1 → 1 CR04-LOW finding (CAPSTONE-02B
  scaffolding; fact preserved), 11 preserved, 7 needs-evidence;
  Jev Ch2 → 0 findings, 6 preserved, 7 needs-evidence.
- No manuscript/result/ledger changes, no paid model runs, no migrations,
  no deploys, no commits/pushes, no unrelated refactoring, no unrelated
  deletions. Temp artifacts removed (`C:/Temp/pub02-*.json` deleted at handover).

PUB-02 fix batch 2026-11-24 (Muse implementation; addresses the Codex
CONDITIONAL blockers + DeepSeek ACCEPT observations, re-verified below):
- CR01 silent pass closed: a status claim with no identifiable backticked
  arm now reports NEEDS_EVIDENCE even when result rows exist (binding
  required, never silent pass). Regression test: unrelated rows +
  unquoted arm → NEEDS_EVIDENCE, never silent pass.
- CR05 bound-evidence comparison now extracts the claim's own
  version/hardware facts (e.g. "requires CUDA 11.8" vs `{"cuda":"11.8"}`,
  numeric comparison with operator support) instead of tokenizing the
  regex pattern; uncomparable claims report NEEDS_EVIDENCE. Tests:
  matching facts pass silently (no false fire on unrelated pattern
  tokens), mismatched version is a finding, unbound package is
  indeterminate.
- Hygiene: `CruftAdjudicationResponse.verdict` is now an
  `AdjudicationVerdict` enum (keep_finding/preserve/unclear),
  rationale/quote_used non-empty, `quote_supported_by(passage)`
  enforces quote-drawn-from-passage; contract-tested, zero dispatches
  stay zero. Unused `get_runtime` import removed from the cruft CLI.
  CR09 dedupes by block before the minimum-blocks threshold (two copies
  in one block no longer satisfy it). CR07/CR08 `confirmed_stale`
  fixture entries relabelled `candidate_positive` (screen outcome
  separated from ground truth; calibration harness asserts
  model_candidate on those entries).
- Suites: `tests/core/test_publication_cruft.py` 35 passed (27 + 8 new),
  calibration 40 passed (split discipline intact; 4 CR07/CR08 entries
  relabelled, expectations unchanged) — 75 total.
- Live re-demonstration: Jev Ch1 with revision-only index
  (`{"evidence_revision":"jev@c7aaad7"}`) → 1 finding (CR04-LOW,
  CAPSTONE-02B scaffolding), 11 preserved, 9 needs-evidence; with
  chapter inventory 1–36 bound → 1/11/7, identical to the PUB-02
  baseline (fingerprint `435974701050…` unchanged). The 9-vs-7 delta is
  the two CR06 needs-evidence entries from the unbound chapter
  inventory, NOT the CR01/CR05 fixes (no rows/facts bound in either
  run, so those paths behave as before by design).
- Regression unchanged: editing+quality 86+1 (sole failure still
  `test_direct_rejects_invented_citations`, byte-identical);
  mediated_read/evaluation_fabric/capability_resolution 114 passed;
  catalog CLI suites 30 passed; `tests/core/test_reader_legibility.py`
  15+2 (identical pre-existing `EnvironmentIdentityStatus.BLOCKED`
  failures). Catalog still 167; zero model dispatches; Jev tree
  unmodified (only pre-existing untracked `scripts/`).

PUB-02 fix batch 2 (2026-11-24; Muse implementation, addresses the Codex
delta re-review BLOCKED points; pending Codex + DeepSeek delta re-review):
- CR01 arm-field binding (`publication_cruft.py` `_detect_cr01`): the claim
  arm is now bound against the actual `arm` field of each result row, never
  the serialized whole row. Rows without a parseable `arm` field, or a
  claimed arm matching no row's `arm` field, report NEEDS_EVIDENCE (never a
  stale finding on a mere miss, never a silent pass). Regression tests: arm
  string in an unrelated row field only, and claimed arm matching no row
  `arm` field, both → NEEDS_EVIDENCE.
- CR05 hardware agreement (`_affirmative_hardware` + `_is_affirmative_fact`):
  minimal bound-fact format with explicit polarity (negation cues: not/no/
  without/never/unavailable/absent/missing/false/disabled/denied/n't...;
  empty/unknown values are not affirmative). Agreement needs the claimed
  token in an affirmative container (a key names hardware only if its value
  does not negate it); negation, unknown polarity or no comparable fact →
  indeterminate NEEDS_EVIDENCE; affirmative-different-hardware still
  contradicts. Version numeric comparison unchanged. Tests: "not A100" bound
  vs A100 claim → indeterminate; `{"a100": "not available"}` → indeterminate;
  affirmative `{"hardware": "A100"}` → silent pass (positive control).
- Quote support enforcement (`ensure_verdict_quote_supported` +
  `dispatch_typed_task`): a verdict whose non-empty `quote_used` is not drawn
  verbatim from the adjudicated passage is returned as failed
  (`INVALID_TYPED_OUTPUT`) -- reported, never repaired/redispatched (D-PUB-08
  law 6/7). Pure-DTO enforcement is impossible (the passage lives in the
  request, not the response contract), so enforcement sits at the dispatch
  seam plus a reusable validation helper. Tests: fabricated quote rejected
  at dispatch with fake models (offline, zero live calls); genuine quote
  accepted.
- Suites: `tests/core/test_publication_cruft.py` 42 passed (35 + 7 new),
  calibration 40 passed (unchanged) -- 82 total. Editing+quality 86+1 (sole
  failure still `test_direct_rejects_invented_citations`, pre-existing);
  mediated/evaluation_fabric/capability 114; catalog CLI 30; legibility 15+2
  (identical pre-existing `BLOCKED` failures). Live Jev Ch1: revision-only
  index → 1/11/9; inventory 1-36 → 1/11/7 (fingerprint `435974701050…`,
  identical to baseline). Catalog 167; Jev unmodified; zero dispatches.

PUB-02 fix batch 3 (2026-11-24; Muse implementation, addresses the Codex
delta re-review's single remaining demand -- CR05 affirmative-mismatch
contradiction): a different affirmative hardware token contradicts ONLY
with exclusivity evidence (`publication_cruft.py` hardware-exclusivity
rule + `_exclusive_hardware` / `_hardware_contradicts` helpers; version
numeric path untouched). Contradiction needs (a) an explicit sole-hardware
scope on another affirmed value token (only/exclusively/exclusive/solely/
single/sole, e.g. `{"hardware": "H100 only"}`) or (b) a known-incompatible
accelerator-family pairing (TPU vs the NVIDIA-GPU stack
GPU/CUDA/A100/H100/V100 -- disjoint vendor stacks; CPU exempt as
co-present; same-family pairs overlap, never exclude). Default (no
exclusivity evidence) is indeterminate NEEDS_EVIDENCE. Negation/unknown
handling unchanged. Regression tests: GPU bound vs A100 claim and H100
bound vs A100 claim → NEEDS_EVIDENCE (overlapping/same-family);
`{"hardware": "H100 only"}` vs A100 claim → contradiction finding;
`{"hardware": "TPU"}` vs A100 claim → contradiction finding;
affirmative `{"hardware": "A100"}` match still passes silently.
- Suites: `tests/core/test_publication_cruft.py` 46 passed (42 + 4 new),
  calibration 40 passed (unchanged) -- 86 total. Editing+quality 86+1 (sole
  failure still `test_direct_rejects_invented_citations`, pre-existing);
  mediated/evaluation_fabric/capability_resolution 114; catalog CLI 30;
  legibility 15+2 (identical pre-existing `BLOCKED` failures). Live Jev
  Ch1: revision-only index → 1/11/9; inventory 1-36 → 1/11/7
  (fingerprint `435974701050…`, baseline-identical). Catalog 167; Jev
  unmodified (`scripts/` pre-existing untracked only, HEAD `c7aaad7`);
  zero model dispatches; zero paid runs; temp evidence JSONs removed.

PUB-02 fix batch 4 (2026-11-24; coordinator-executed, single Codex residual --
no new files): the CR05 family-incompatibility rule is removed.
Affirmative-hardware mismatch now contradicts ONLY on an explicit
sole-hardware scope cue (only/exclusively/exclusive/solely/single/sole
on another affirmed value token, e.g. `{"hardware": "H100 only"}`);
every other mismatch (GPU vs A100, H100 vs A100, TPU vs A100, CUDA vs
A100) is indeterminate NEEDS_EVIDENCE, since the bound facts never
establish a single-device or exhaustive inventory. `_CR05_HARDWARE_FAMILIES`
deleted; `_hardware_contradicts` is exclusivity-cue-only. Test
`test_cr05_known_incompatible_hardware_contradicts` rewritten as
`test_cr05_cross_stack_hardware_is_indeterminate` (TPU bound vs A100
claim → NEEDS_EVIDENCE); explicit-exclusivity contradiction test
unchanged and green.
- Suites: cruft 86 passed (46 unit + 40 calibration); ruff clean both
  files. Fast neighbours re-run in-session: editing+quality+
  legibility+catalog-CLI = 134 passed, 0 failed (the two pre-existing
  failures are gone because the owning teams' fixes landed concurrently
  -- see §4.3 -- not because of PUB-02). Mediated/eval set untouched
  by batch 4 (DeepSeek: 114 on batch-3 tree). Live Jev Ch1:
  revision-only → 1/11/9; inventory 1-36 → 1/11/7 (fingerprint
  `435974701050…`, baseline-identical). Catalog 167; Jev unmodified;
  zero dispatches; $0.

## 4. Blockers / risks

1. **Catalog↔registry: PUBLICATION-scoped agreement achieved; full green
   documented-open.** `editing` + `mediated_read` manifests added (catalog
   165→167). Remainder: 1 missing (`metadata_generation`, unrelated owner),
   46 orphaned (unrelated owners; `council` is forward-relevant to PUB-08),
   1 adapter problem (`analysis_state` EVALUATE). → Writer owning-team backlog
   (CAPABILITIES.md §8); nothing here blocks PUB-02 gates.
2. **`runtime.quality` deliberately CLI-only (D-PUB-07).** Working seam is the
   `writer quality evaluate` subprocess contract. Facade design → PUB-02
   (done for cruft: `EvidenceIndex` bindings + NEEDS_EVIDENCE is the reusable
   pattern; quality facade itself still deferred), surface + bridge → PUB-07,
   migration → PUB-09. U2/U3/U4 open with owners.
3. **Writer test invocation fixed; pre-existing failures recorded.**
   Use `C:\Projects\writer\venv\Scripts\python -m pytest` (3.11.4, CWD
   `C:\Projects\writer`). Editing+quality 86 passed + 1 failed
   (`test_direct_rejects_invented_citations` — post-Stage0 quality change,
   predates PUB-01, owner Writer quality; reproduced identically in PUB-02);
   mediated_read + evaluation_fabric + capability_resolution 114 passed;
   catalog CLI suites 30 passed. PUB-02 addition:
   `tests/core/test_reader_legibility.py` 15 passed + 2 failed
   (`test_evaluator_reports_not_built_without_fabricating`,
   `test_evaluator_does_not_convert_failure_to_pass` —
   `AttributeError: EnvironmentIdentityStatus.BLOCKED` in the untouched
   reproduction_readiness evaluator path; PUB-01 never ran this file).
   Update 2026-11-24: the owning teams fixed all three concurrently
   during the gate (outside PUB-02 scope; PUB-02 file set untouched):
   BLOCKED member added, vertical-slice assertion aligned to the
   committed RETRIEVAL_FAILED code, mri IndentationError fixed, plus
   conftest per-PID DB hygiene and a `long` marker (gate (c) default
   now 113 + 1 deselected; documented 114 needs explicit `-m`
   override). New baselines: editing+quality 87/0, mediated 114
   (override), catalog CLI 30, legibility 17/0, cruft 86 (46+40).
   None was a PUB-02 regression.
4. **Jev evidence correspondence unresolved — carried to PUB-03, not modified.**
   See §4.6.
5. **Naive complexity counts lie** (tables/code inflate sentence metrics;
   ch6/ch7); all PUB-04 work must measure through Writer's parser exclusions.
   Standing PUB-04 watch item.
6. **Review-observation backlog (recorded, no action this stage).**
   DeepSeek observations carried forward: (a) full-suite collection is
   blocked by `tests/runtime/domains/test_mri_semantic_adjudication.py:493`
   `IndentationError` — Writer MRI owner; (b) no automated CLI test for
   `writer cruft review` — later-stage gap, not a PUB-02 gate item;
   (c) `reader_legibility` teardown flake (final-cleanup notice during
   the legibility run) — cosmetic, unrelated to PUB-02.
7. **PUB-08 calibration carry-forwards (accepted PUB-04/PUB-05/PUB-06
   limitations, not gate items).** CX10b whitespace-normalised quotes
   (span exact, quote space-joined); display-`$$` mathematics (inline-
   only `_MATH_SPAN_RE` parses display math as prose); coherent-short-
   prose CX10-medium false positives (needs connective/density-aware
   clearing); indented/tilde code fences outside the parser; synthetic-
   heavy held-out suites (broaden real-manuscript held-out, esp. CX);
   new-sentence honesty is first-layer cue-based (negation-insensitive
   establishment cues; full semantics deferred). PUB-06 review
   additions: derived artifacts are not auto-regenerated on detector
   change (re-verify step mandatory before citing numbers); records do
   not bind detector implementation versions (profile versions only);
   no independent editorial read of the final candidate bytes exists
   yet beyond the scoped delta re-review (full-chapter human read
   remains author-side).
8. **PUB-07 review-gate items (open, author/reviewer adjudication).**
    (a) Demo outcome `review_invalid`: verify-pass candidate with a
    twice-raised substantive objection (LLM2Jev overstatement vs ledger
    PARTIAL) + a final-round reviewer quote failure; presented
    `pending_author_decision` with options A/B/C (approval-decision).
    (b) Provider-reported usage anomaly on the haiku route
    (input_tokens 4 vs total 5262): recorded verbatim, cost $0,
    flagged for Worker owner awareness -- no action in programme.
    (c) Codex delta from PUB-06 close still outstanding at PUB-07
    scope-done; triage stands (hardening unless substantive).

### 4.6 Jev evidence question (unresolved; binding framing for PUB-03)

`results/ch01.jsonl` holds 27 rows: 20 `provider="predicate"` rows (zero
tokens, empty model, `agrees_with_predicate`) + 7 aggregates. That establishes
the *file* contains predicate-only rows; it does NOT establish experiments
were never completed elsewhere. The author reports a wider Jev programme as
completed — treated as a claim requiring reconciliation, neither verified nor
disproved. Correspondence classes: original vs subsequent artifacts vs
capstones vs equivalent-differently-scoped vs validated replacements vs
unresolved. PUB-03 applies the decision table in ROADMAP.md (pending+match →
update; pending+equivalent → investigate transfer; pending+partial → preserve
limitation; pending+none → unresolved; completed+contradictory → block).
Nothing in `C:\books\jev` (manuscript, results, ledger) was read beyond
characterization or modified in PUB-01.

## 5. Repo revisions observed (PUB-01 execution; read-only except noted change)

| Repo | HEAD | Tree vs HEAD |
|---|---|---|
| `C:\Projects\mission` | `97edb77` | Modified (pre-existing workstream): `backend/mission_control/api/health.py`, `models.py`, `persistence/db.py`, `backend/tests/conftest.py`, `test_postgres_integration.py`, `scripts/migrate_sqlite_to_postgres.py`; untracked (pre-existing): `test_db_isolation.py`, `test_persistence_conventions.py`, `docs/MC-POSTGRES-02-REPORT.md`, `scripts/pg_backup.py`; untracked (this programme): `docs/programmes/`; 3 extra worktrees |
| `C:\Projects\writer` | `bb8dc3f` | Pre-existing: deleted `.cocoder/config.toml`, `.opencode/opencode.json`, `.pi/model-transports/opencode/agents/pi-model.md`, `.pi/skills/writer-metadata/*`; modified `.vscode/settings.json`. **PUB-01 change: modified `packages/writer-runtime/writer_runtime/capabilities/catalog.py` (+77, two manifests). PUB-02 changes: new `packages/writer-core/writer_core/analysis/publication_cruft.py`, new `packages/writer-cli/writer_cli/commands/cruft.py`, modified `packages/writer-cli/writer_cli/main.py` (+5, `cruft` registration), new `tests/core/test_publication_cruft.py`, new `tests/core/test_publication_cruft_calibration.py`, new `tests/core/fixtures/publication_cruft_calibration.jsonl`. Fix batch (same files, no new files): unit tests 27→35, 4 CR07/CR08 fixture entries relabelled `candidate_positive`. Nothing else touched; no stray files (verified).** |
| `C:\books\jev` | `c7aaad7` | Untracked: `scripts/` (pre-existing). Nothing modified. |
| `C:\Projects\workbench` | `dd0c440` | Clean (+2 extra worktrees) |
| `C:\Projects\worker` | `2bb8a8d` | Clean |
| `C:\Projects\work` | `8533143` | Clean |
| `C:\Projects\next` | `d8208b0` | Clean |
| `C:\Projects\inspect` | `af12318` | Clean |
| `C:\Projects\praxis` | `9cbc590` | Clean |
| `C:\Projects\ai` | `a8c4199` | Clean |

`C:\Projects\programmer.ie` does not exist as a checkout (programmer_ie is a
book id in the Writer registry). Review format `Current Text / Recommended
Change` verified in `C:\books\jev\scripts\apply_edits.py`.

## 6. Exact next action — PUB-08 active: reuse research + experimental design ($1.00 inference cap)

**PUB-08 authorized 2026-11-25 (author direction; primary implementation
agent Muse; 8/12 accepted). Reuse-matrix first pass recorded
(`pub08/reuse-matrix-survey.md`, $0, read-only): most PUB-08 needs are
LIB/CALLABLE (Manuscript IR, Compiler, Argument, Knowledge State,
Evidence claim extract/verify, QC pilot, Writer-owned semantic-loss,
Mediated Read, Evaluation Fabric, revise blind trials, Worker typed
tasks); genuine gaps are (1) calibrated human-comprehension evidence
(explicitly missing), (2) D-PUB-84 defect-attribution contract,
(3) composed semantic-preservation interface across 3 repos,
(4) blind assessment as a callable capability, (5) Praxis owns no
manuscript semantics (cite Writer ownership; no parallel build).
Accepted-candidate ambiguity resolved (ch02-rerun is the demonstration
candidate). Costed design received 2026-11-25
(`pub08/costed-experiment-design.md`, $0): n=2 central ≈ $0.10
actual (≈$0.23 if haiku meters; worst ≈ $0.42; 2.4× headroom) —
FITS the $1.00 cap. Arm A₁ EXECUTED 2026-11-25 (single paid
dispatch, one shot, prompt SHA == freeze, aggregate check
$0.00+$0.015 ≤ $1.00 passed pre-dispatch): deepseek-v4.1-flash,
8,270 in / 35,775 out, **actual $0.0227** (1.5× band top — estimator
was reasoning-light; under the 2× hard stop, no trip), 590-line
candidate + dispatch record in `pub08/experiment/arm_a_r1/`
(no_new_claims declared true, synthesis_index empty; verified as
recorded, not as true). Spend to date $0.0227 / $1.00; Worker
stopped after use. Fail-closed order: freeze → controls on O/H
($0) → 7/7 gate → A₁ → C₁ (verification of A₁ + ≤2 bounded repairs)
→ B₁ (B-hull + merge code + gates) → evaluation → replicate 2.
Build batch 1 LANDED 2026-11-25 ($0, 5 new files, 0 tracked modified): D-PUB-84 attribution builder
(all 9 dispositions pinned) + 7 fixtures + O/H controls gate 7/7 +
aggregate spend wrapper (cap $1.00) — 34 focused + 123 neighbours
green, ruff clean. Vocab note: design §3.5 names mapped to the 9
mandated tokens in the module docstring (`OUT_OF_SCOPE_CITATION` →
`UNRESOLVED_ATTRIBUTION`+scope; `TRANSFORMATION_REDUNDANT_SYNTHESIS`
→ `INTRODUCED`+semantic_class; `RESOLVED` vs `AUTHORIZED_CORRECTION`
distinguished). Next: batch 2 (freeze manifest + Arm A DTO/prompt +
fake-dispatch gate), then paid A₁ (≈$0.01) under manual aggregate
check (wrapper CLI wiring is PUB-09).
Paid inference budget: $1.00 hard cap authorized 2026-11-25 (covers
all PUB-08 Worker/model dispatches; pre-dispatch enforcement + ledger
actuals as in PUB-07; if the costed design exceeds $1, report blocked
and request an increase — never silently exceed). No authoritative
mutation, no PUB-09, no commits/pushes.**

**PUB-07 fix batch 2026-11-25 (D-PUB-81) + coordinator close-out (D-PUB-64 fail-closed spend incl. non-finite rejection, D-PUB-65/66/67 trust roots, D-PUB-68 chain digest + canonicalisation scoping, R1 numbers, R4 handoff, R5 blind spots). VERIFIED in-session on the final tree: transformation 83 + CLI 9 + automation 40 collected = 132 passed (combined run); full delta gate 592 passed + 1 strict xfailed (held-cx15) / 0 failed, independently reproduced by coordinator AND DeepSeek; ruff clean; catalog 167; Jev clean ($0 new spend on verification); worker probe server stopped after use.**

Bounded re-run EXECUTED by coordinator in a credential-bearing shell (fix batch is code-only, zero live dispatches by design): `transform automate jev 02-chapter` (same package/inputs): outcome **review_accepted** (no correction loop needed -- reviewer accepted), **2 dispatches, $0.0039864** (1 editorial deepseek-v4.1-flash 8246 tok + 1 review haiku $0/5678 tok), spend cap enforced pre-dispatch, verify **15/15 pass**, candidate fp **`9f36c9ba…`** (355 lines, LF-normalised bytes), chain after==candidate asserted and independently recomputed MATCH. The re-run exposed + resolved one real defect: the interim "new CX10 HIGH" was a cross-table false-positive join (prose on both sides of the Willard table glued into one "run"), removed by the PUB-04 structural-break fix (verified gone; final book-wide book scan unchanged at the pre-existing baseline). Temp evidence cleaned; probe Worker stopped after the gate closed.

**Returned verdicts on the final tree / bytes: DeepSeek CONDITIONAL (all deterministic checks pass; R1 numbers corrected here: 38→39, CX10 1→1 HIGH gone, neighbours 260+1xf within the 592+1xf gate; R3 chain binding independently recomputed MATCH + canonicalisation narrowed with pins; R4 handoff supersede-noted incl. all [FILL]s filled; R5 blind spots recorded); Claude editorial delta CONFIRMED on the new bytes (BLOCKED cleared → ACCEPT as governed output, pending author release; paragraph split real, gloss gone, rest matches run 1, LLM2Jev paragraph unchanged source). Author final-gate instructions 2026-11-25: run-1 line-138 synthesis DELETED by author direction (D-PUB-82, run-1 artifact unmodified; rerun independently checked — defect absent, no correction proposed); run-1/rerun records stay distinct with promotion deferred (D-PUB-83); PUB-08 attribution mandate recorded (D-PUB-84). Outstanding: none. GATE CLOSED 2026-11-25 — Codex ACCEPT (4/4 BLOCKED,
digests recomputed MATCH); DeepSeek CONDITIONAL doc residual fixed
in-session (op:026+op:039 attribution) and revalidated — closed;
Claude accept-with-one-style-edit (delete rerun line 155) carried as
author-side polish at promotion, not applied to verified bytes
(D-PUB-82/85). No PUB-08 work started. Worker auth infra note stands
(D-PUB-78 follow-up filed as owning-team work).** On ACCEPT/CONDITIONAL-minor: record PUB-07 conditionally complete / proceed to author verdict + PUB-08 prep. On substantive BLOCKED: single surgical fix batch, then close. No PUB-08 until the gate closes. Worker auth infra note stands (D-PUB-78 follow-up filed as owning-team work).**

## 11. PUB-05 (closed 2026-11-24, author direction)

PUB-05 **ACCEPTED**. Basis: reported implementation (deterministic
pedagogical planner + plan/validator/freshness contracts + 12-code
validator + representation selection with pipeline caveats), independent
reviews (Codex CONDITIONAL→fix batch→2 deeper residuals fixed with
pins, verified in-session; DeepSeek CONDITIONAL→ACCEPT with live
numbers exact), regression evidence (fast gate 459 green, live Ch1 46 /
Ch2 46 / Ch7 49 / Ch9 62 / book 1398 all validate, $0), and
coordinator-executed final residuals (D-PUB-52 anchor presence +
linked-evidence gate). Author acceptance notes: relies on supplied
reports; calibration, doc-count discrepancies and execution-boundary
revalidation stay open. Authoritative manuscript unmodified throughout.
PUB-06 authorized: complete revised Jev Ch1 candidate as key
deliverable.

## 10. PUB-04 review verdict (closed 2026-11-24, author direction)

PUB-04 **ACCEPTED**. Basis: reported implementation (CX01–CX15 deterministic
screen, 83+1 suites), independent reviews (Codex BLOCKED→contract fixes→2
deeper edges fixed with pins; DeepSeek ACCEPT/CONDITIONAL→ACCEPT with live
invariants exact), regression evidence (fast gate 391 green, live Ch1 38 /
book 1083 / 0 dangling / 0 bad spans, $0), and coordinator-executed final
residuals (D-PUB-37 strict locate, D-PUB-38 segment probes) verified
in-session. Author acceptance notes: relies on supplied implementation and
verification reports, not local execution; calibration/coverage limits stay
open (CX10b quotes, indented/tilde code, `$$` math, coherent-short FP,
synthetic-heavy held-out, `_stamp` flake, INDEX counts). Key result: editing
88.7–100 "good" vs 38 reader-workload findings — the Publication-domain gap
demonstrated. PUB-05 authorized (fix batch 3 residuals mapped 1:1 in the
§3 entry above; fast-gate close-out per README §6 two-round policy).

### PUB-04 final fix batch — ACCEPTED (author direction, no new review cycle)

The cross-block CX10b correction (sequence breaks on structural blocks;
2 pins) is accepted as justified: a table, code block or figure is a
structural interruption, and prose on either side must not combine into
one staccato sequence.
**Authoritative PUB-04 baseline updated: 36 chapters, 1,073 findings**
(was 1,083). The 10 removed findings were invalid cross-structural
joins, so the reduction is an accuracy improvement, not a coverage
loss. Chapter 1 unchanged at 38 (identical by-CX set). Current
verification: complexity 63 unit + 43 calibration (42 passed + 1 strict
xfailed); fast gate 467 passed + 1 xfailed / 0 failed; ruff clean.
Historical entries above retain their at-the-time numbers.

**Downstream compatibility check (coordinator-executed 2026-11-24):**
no retained PUB-05 plan or PUB-06 candidate record depends on the 10
removed findings. Ch1 plan re-validates clean (0 violations); Ch1
candidate re-verifies 21/21 pass on current bytes; Ch7 output
identical to baseline (52 total, CX02×16/CX03×18) so the P-07
superseded-pointer passage (evidence-domain basis) is unaffected;
Ch9 CX10×9 intact so the P-09 staccato-consolidation basis holds.
No derived artifacts regenerated. Book-wide PUB-05 structural plans
remain demonstration artifacts; any stale finding reference at a
future consumption boundary is caught by the standing revalidation
rule -- no mass regeneration.
**Carried to PUB-08 calibration:** CX10b whitespace-normalised quotes,
display-`$$` mathematics handling, coherent-short-prose false
positives (plus the already-recorded indented/tilde code fences and
synthetic-heavy held-out).

## 12. PUB-06 review verdict (closed 2026-11-24, author direction: in-session verification record accepted as sufficient)

PUB-06 **ACCEPTED**. Basis: deterministic transformation engine +
governed work-package compilation + fixture-only surgical path
(60→78 behavioural pins incl. fail-closed gates, unbound-adjudication
rejection, missing-fingerprint refusal, non-executable isolation,
record chain with content-bound digest); independent reviews
(Codex BLOCKED→contract fixes→BLOCKED on trust-root bypasses→fix
batch 2 with binding-digest/conjunction/fail-closed rehydration;
DeepSeek CONDITIONAL→ACCEPT on the final tree; Claude BLOCKED-narrow
→CONDITIONAL with BLOCKED cleared, 10/10 regions verified);
regression evidence (fast gate 545 passed + 1 strict xfailed / 0
failed, ruff clean; live Ch1 46 validates, verify 21/21 pass on
final bytes `f6c1cbf4…`; catalog 167); coordinator close-out with
in-session verification (R1 numbers corrected to 38→39, CX10 HIGH
shown to be a cross-table false positive and removed; R3 chain
binding to canonicalized plan content, independently recomputed MATCH;
R4 handoff refresh; R5 blind spots to PUB-08; candidate prose fixes
verified present).
Codex delta confirm was outstanding at close; per author direction
the in-session record (544→545 green, 21/21, recomputed chain
match, full-suite pins) stands as sufficient -- any Codex residual
arriving late will be triaged as a PUB-07 hardening item, not a
PUB-06 reopen, unless it evidences a consequential defect.
Authoritative manuscript + evidence unmodified throughout; $0
metered spend; no commits. PUB-07 authorized with the expanded
automation-closing scope (D-PUB-69…74): machinery performs,
Muse builds.

## 7. PUB-00 review verdict (recorded PUB-01)

PUB-00 **ACCEPTED** 2026-11-24 as the programme foundation (research and
documentation only; no implementation authorized or executed). Basis: objectives
and end-state workflow adopted; architecture grounded in live implementation
with cited paths; ownership resolved-or-explicitly-open (U1–U5); capability
inventory with callable-vs-role separation and live verifications; CR01–CR12
names + complexity signals adopted as calibration inputs; stable IDs PUB-00…11
with dependencies and per-stage gates; acceptance criteria and next stage
specified. Carried into PUB-01 as issued: catalog reconciliation, quality-surface
decision, model-routing settlement, provenance conventions, test-env repair,
AI-primitives inventory, Jev evidence framing — all executed above.

## 8. PUB-02 review verdict (closed 2026-11-24, author direction)

PUB-02 **ACCEPTED**. Evidence: deterministic CR01–CR12 classifier
(`publication_cruft.py`, profile `cruft-v0.1`, `calibrated:false`) + `writer
cruft review` CLI (library+CLI surface, no catalog change per D-PUB-10);
86 cruft tests (46 unit + 40 calibration, dev/held-out split, frozen
profile, held-out run once); fast neighbours 134/134 green in-session;
mediated/eval 114 (DeepSeek, batch-3 tree; batch 4 untouched those
paths); catalog 167; live Jev Ch1 1 CR04-LOW / 11 preserved / 7
needs-evidence (inventory-bound) with stable fingerprint
`435974701050…`; zero model dispatches; $0 verification spend; Jev and
all repo trees clean of strays, no commits.
Review history: Codex CONDITIONAL → BLOCKED (2 silent-pass risks) →
CONDITIONAL (CR05 exclusivity) → final residual (TPU-vs-NVIDIA
auto-contradiction) applied literally as specified (exclusivity-cue-only
contradiction; cross-stack mismatch → NEEDS_EVIDENCE). DeepSeek ACCEPT
×3 (batch 1 free tier; batch 2 + batch 3 on `opencode-go` fallback, all
$0 metered). The author closed the gate on the applied residual without
a fifth review cycle to bound stage cost (fast-gate policy, README §6);
the change is covered by 4 pinning tests (3 indeterminate + 1
contradiction positive) plus the untouched 82-test base, all green
in-session. Carried into PUB-03: the 7 needs-evidence items and the
EvidenceIndex/NEEDS_EVIDENCE pattern.

## 9. PUB-03 review verdict (closed 2026-11-24, author direction)

PUB-03 **ACCEPTED** on the reported independent regression verdict
(DeepSeek ACCEPT: 76 evidence + 190 neighbours + short suites + live
59/9/15/3/3 @ `jev@7f008df8772f677f` and cruft 1/11/2, $0) and the
implemented review findings. Lane record: Codex BLOCKED (chapter-blind
matching) → fix batch (D-PUB-21 scope rule + 7 cross-chapter tests) →
Codex 5/6 ACCEPT with sandbox residual → execution path REMOVED
(D-PUB-23, runtime counts explicitly unavailable, static counts kept)
plus README count fix; coordinator verified 171/171 green in-session,
then post-acceptance batch-2 confirmation: evidence suites 90/90,
live reconcile 57/17/9/3/3 with 6 corrections @ `jev@6c13d2837f138c84`
(delta vs baseline exactly the two selftest-count claims
SUPPORTED→UNRESOLVED, as specified), cruft 1/11/2 fingerprint-stable,
$0, Jev clean.
Caveats recorded by the author: acceptance rests on the supplied
verification reports; the local implementation and deferred long suites
were not independently executed by the author. Carry-forwards: Ch7
correction stays scoped (missing file ≠ replacement identified);
Ch1 model-arm supersession unproven (lead, not evidence); 4/36 chapters
reconciled — full-book reconciliation is PUB-10 scope. PUB-04 authorized.
