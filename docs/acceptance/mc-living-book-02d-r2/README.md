# MC-LIVING-BOOK-02D-R2 acceptance record

Status: **Executable path qualified structurally. H1 protocol frozen as
`PILOT-2-MANIFEST.json` (rev 2, sha256
`0f860cc6110ca69874803d994e3c711856b81c6b3c075cfb480f4772f8ca6f6a`).
NOT authorised, NOT executed.** PILOT-1 remains frozen and `inconclusive`;
the R1 three-arm draft remains historical and unexecuted.

## 1. Preflight (2026-11-20, offline, no model calls)

| Check | Result |
| --- | --- |
| Mission HEAD | `885b81f` — 2 commits ahead of reported `06ed3d0`, tree clean. The 2 commits are `MC-PRAXIS-07` (governed proposal import), unrelated to Living Book |
| ALIVE HEAD | `e63d0899` — matches reported commit, tree clean |
| Chapter 15 file hash | `5bf5c4c7…` matches PILOT-1 freeze |
| Chapter 16 file hash | `a4e0ee67…` matches R1 draft |
| `pilot2-criteria.txt` | 416 chars, `9d33af57…` matches R1 draft |
| `chapter-improvement` v1006 definition | `5cd3400f…` recomputed from ALIVE `e63d0899`, matches PILOT-1 freeze |
| `chapter-evaluation` v1 definition | `13cc2b25…` recomputed, matches PILOT-1 freeze |
| Informed family | v8 + v1001–1006 present (`informed_definitions.py`) |
| Experience path | `chapter_experience.build/validate_supplied`; quality `evaluation_failed` stays `quality_unverified`, promotion `context_only` |
| Independent evaluator | `chapter.independent_evaluate`, rubric `chapter-evaluation-v1`, six dimensions 0–4, seven mechanical presence checks |
| Mission comparison | `GET /api/living-book/projects/{id}/improvement/comparison?run_ids=`, pair rules `benefit/harm/no_benefit/inconclusive`, read-only |
| Review-confound architecture | review stage (`informed_reviewer`) receives NO experience by construction (`informed_definitions.py` injects experience only into `*_improve` stages). Sharing one review across arms would need new launch/Grant plumbing — rejected as disproportionate. PILOT-2 is therefore registered as a **complete-pipeline comparison** (see manifest §design.review_context_confound) |
| Provider timeout default | `ALIVE_META_TIMEOUT=30` (`alive/config.py`, range 1–120); httpx timeout for all Meta calls (`alive/providers.py`) |
| Pi deadline default | `alive_pi_run_deadline=120` (range 1–900); wraps the whole Pi process (`alive/pi/gateway.py`) — provider 90s sits strictly inside Pi 120s |
| Single dispatch | `alive_pi_max_provider_requests=1`, code-enforced `ge=1 le=1`; second inbound refused (`request_limit`); reservations `dispatched` before upstream call |
| Ambiguity containment | post-dispatch timeout → `ambiguous`, UNKNOWN, no retry, no re-dispatch; unknown usage stays null; conservative charge never presented as billing |
| Mission living-book suites | `test_living_book.py` + `test_living_book_improvement.py`: **12 passed** 2026-11-20 |
| ALIVE Pi suites | `test_pi_egress.py` + `test_pi_lifecycle.py`: re-run 2026-11-20 (see qualification report) |

## 2. Frozen protocol

`PILOT-2-MANIFEST.json` rev 2: two-arm H1 (A control, B relevant-experience
treatment) on held-out Distillation chapter 16. Arm C removed — only one
genuine eligible experience exists, so H2 stays untestable; no item was
manufactured. Rev 2 corrects a hand-transcribed `binding_sha256` to the
live-verified 64-char hex value; no protocol, budget, or rule changed.
Scoped transport: `ALIVE_META_TIMEOUT=90` for the experimental
process only (default unchanged), Pi deadline 120 unchanged, no retry,
A-then-B, 18 calls / 400k tokens ceiling, monetary cost unknown.

Authorisation-time live verification (2026-11-20, `freeze-receipt.json`):
capture `a632c716…`, approval `3996f4b2…`, plan `45970e69…` (v1006,
6 sections, 8 calls), definition `5cd3400f…`, binding `30f106e1…`,
B context `e5993c62…` (2070 chars, score 0.647), zero prior runs on
chapter 16 — **all match; no mismatch, no rebase.**

## 3. Owner authorisation — GRANTED 2026-11-20

1. **Manifest rev 2 authorised** with risk-bounded budget (cost unknown, never
   zero). Probe authorised (up to 100 calls; minimum used).
2. **Pi-path probe**: COMPLETED via living-book ask on chapter 16
   (`pi-probe-receipt.json`): status completed, 11.1s, 2 calls,
   10,471 tokens, real usage returned, 2 citations. Pi 1.4.0 runtime
   (repo-pinned, `npm ci` from committed lockfile) after the environment's
   1.5.0 bundle vanished; see qualification report for the infrastructure
   finding.
3. **PILOT-2 execution**: AUTHORISED and EXECUTED 2026-11-20 —
   Arm A `06e22f94` COMPLETED (8 calls, 52,487 tokens, proposal `c2f1ece1…`,
   decision pending); Arm B `618224ff` FAILED at section_1
   (`provider_output_truncated`: output hit the 1536-token section ceiling,
   NOT a timeout); independent evaluation of A `e7fd68df` verdict `benefit`
   (+1 total, +1 economy, mechanical attention on equations/qualifications).
   B has no proposal and no evaluation. **Outcome: `inconclusive`** per the
   frozen valid-comparison rule; no rerun per frozen hard-stop.
   The Mission comparison endpoint shows the pair truthfully
   (`inconclusive`, `valid: false`). See `results.json`.

## 4. 02C

See `docs/MC-LIVING-BOOK-02C-DESIGN.md` (semantic mediation design) and the
vertical-slice implementation. Proceeds independently of the R2 outcome.
