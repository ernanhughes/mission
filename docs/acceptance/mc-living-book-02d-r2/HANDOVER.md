# Final handover — MC-LIVING-BOOK-02D-R2 → MC-LIVING-BOOK-02C

## Branches and commits

ALIVE (`C:\Projects\alive`, base `e63d0899`): branch
`mc-living-book-02c`, commit `50bf5375` — `alive/living_book/semantics.py` (new),
`service.py`/`contracts.py`/`api.py` (representations), `pi-runtime/`
(1.4.0 install, gitignored if applicable), `tests/test_living_book_semantics.py`.
Mission (`C:\Projects\mission`, base `885b81f`): branch
`mc-living-book-02c`, commit `b8ff857` — living-book proxy + routes, `ExplorePanel.tsx`,
page wiring, types, `test_living_book_represent.py`, docs
(`02C-DESIGN`, `acceptance/mc-living-book-02d-r2/`,
`acceptance/mc-living-book-02c/`, `acceptance/02c-demo-*.json`).
No push, merge, or deploy — owner to approve.

## Tests

| Suite | Result |
| --- | --- |
| ALIVE `test_pi_egress` + `test_pi_lifecycle` | 40 passed |
| ALIVE `test_living_book_semantics` (new, 14) + `test_living_book` | 19 passed (combined run) |
| ALIVE `test_living_book` + `living_chapter` + `chapter_evaluation` + semantics | 31 passed, 1 failed in one heavy combined run (flake: passes solo, passes in smaller combos with the new tests, pristine combo passes) |
| Mission living-book (represent/new, living_book, improvement) | 15 passed |
| Mission `tsc --noEmit`, `vite build`, `LivingBookPage.test.tsx` | clean / clean / 4 passed |
| Browser (isolated branch stack :8791 + ALIVE :8000) | reading room + Explore panel verified via DOM/API; screenshots unavailable |

## Model calls and cost

13 R2 calls (probe 2 + Arm A 8 + Arm B 2 + eval-A 1), 108,266 tokens
charged; ~10 02C demo calls on the order of 70k charged tokens
(conservative reservations included; real validated usage lower; largest
single item 41k incl. one 32k conservative charge). Monetary cost UNKNOWN
(ALIVE has no price table) — authorised as risk-bounded, never reported
as zero. The final browser-driven `explain` via the Mission proxy
(record `bd2b2d86`, 2 calls, 8,233 tokens) closed the live-verification
loop; no further paid calls were made after it.

## Demonstrated live

- Pi-path probe (completed, real usage, citations).
- Arm A end-to-end (proposal + benefit evaluation); Arm B correctly admitted
  context then failed closed on output truncation.
- Comparison UI shows the pair as `inconclusive`/`valid:false` (API-verified).
- 02C: real `explain` responses parsed to RECORD/RENDERING/ADDED with exact
  chapter citations; validation refinement recomputed offline; failures
  (truncation ×2, confused refusal ×1, empty ×1) all retained as
  attention/refused with reasons; representations survive restarts;
  reject path works; Mission-proxy live call (`bd2b2d86`) completed through
  the real stack; Explore tab verified in the browser against an isolated
  branch stack.

## Fixture-only (no real-model proof yet)

- Completed real-model `diagram`/`compare` rendering.
- Browser screenshot capture (no visible desktop window in this environment).

## Manuscript integrity

Chapters 14/15/16 hashes re-verified after all runs — unchanged. No
manuscript write, decision change (A pending, B unavailable), or promotion.
PILOT-1 and the R1 draft untouched.

## Unresolved issues

1. Committed Pi bundle-sha pin matches no file in the faithful npm 1.4.0
   install (stale pin); skipped process-scoped. Needs an ALIVE-side re-pin.
2. 1,536-token conversation ceiling truncates rich RECORD+RENDERING outputs;
   two-call split (or higher-ceiling profile) is the next step.
3. One combined-run chapter-evaluation failure (passes solo; also passes in a
   2-file combo WITH the new tests, and the pristine 3-file combo passes).
   Verdict: load/order-sensitive flake in the slow suite, not introduced by
   these changes. Re-run the slow suite before any merge.
4. Cost remains unknown; any future block needs the same risk-bounded form.

## Next recommended stage

02C: two-call record-then-render, completed diagram/compare, one live
Mission-proxy call, browser UI verification. R2: no further experiment
without a new protocol — the question needs a design that survives the
output ceiling (e.g., truncated-output handling rules) and ideally more
than one pair.
