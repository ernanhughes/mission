# MC-LIVING-BOOK-02C acceptance record — first semantic-reading slice

Status: **vertical slice implemented and exercised with real model calls;
mechanism proven, one transport bound discovered and documented.**
No manuscript write; no permanent reader model; no comprehension claim.

## 1. What was built

| Piece | Location | Reuse |
| --- | --- | --- |
| Deterministic obligations + span validation + standing | ALIVE `alive/living_book/semantics.py` (new) | `evaluation_preservation` checks; Language ch07 record schema |
| Representation service (resolve → obligate → generate → validate → retain) + reject/list/read | ALIVE `alive/living_book/service.py` (+ contracts, + api routes) | existing conversation/session (`ask`), chapter custody, event ledger |
| Fixture path (labelled, no model call) | `semantics.fixture_representation` | tests + offline use |
| Mission proxy (represent/list/get/reject) + routes | `backend/mission_control/living_book/{client,service}.py`, `api/living_book.py` | existing AliveClient + `_book_for` |
| Reader UI (Explore tab, task picker, provenance, reject/return-to-original, question-this-view) | `frontend/.../ExplorePanel.tsx` + `LivingBookPage.tsx` + types | existing `BookMarkdown` (mermaid/KaTeX), selection flow |

No new model operation, memory, workflow engine, gateway, ranking, or
quality system. No new manuscript source.

## 2. Real-model evidence (authorised small budget)

Language ch07 passage (321 chars, traceability obligation), chapter
`002f2fab20…`, via the live conversation path:

- Attempt 1 (700-char passage): model output exceeded the 1,536-token
  conversation ceiling → truncated → failed closed, retained as
  `attention`/`unparseable`. No silent acceptance.
- Attempt 2 (321-char passage, `explain`): full RECORD + RENDERING + ADDED
  returned; 4 citations, all exact chapter substrings (2 passage-exact,
  2 chapter-context). Receipt `02c-demo-explain.json`, conversation
  `21262d90`.
- Attempt 3: model refused with a confused reason (digits in instruction
  labels misread as conflicting with obligations) → retained as `refused`
  with reason. Instruction labels de-numbered in response.
- Attempt 4 (`diagram`): output again hit the 1,536 ceiling → truncated →
  `attention` retained.

Under the refined validator (passage vs chapter citation split), attempt 2
recomputes to standing `attention`, class `reveal`: 2 passage-grounded
spans + 2 chapter-context quotes surfaced + `quotes_and_tables` formatting
flag. No `verified` was claimed where review is due; no genuine quote was
called fabricated.

First-attempt fixture receipts: `02c-demo-relationships.json`
(empty-output attention), `02c-demo-diagram.json` (truncation attention).

## 3. Known bound (not a failure to hide)

The conversation path's 1,536-token per-call ceiling fits compact
RECORD+RENDERING responses but not verbose ones from this model family
(high reasoning-token overhead). Mitigations applied: compactness bounds in
the instruction (≤5 claims, quotes ≤160 chars, rendering ≤600 chars),
bare section headers. Recommended next step (separate authorisation): split
generation into two bounded calls — RECORD first, then RENDERING derived
from the retained RECORD (mirrors ch07's record→rendering pipeline) — or a
higher-ceiling chat profile. Single-call `diagram` for rich passages is
NOT yet reliably completable; do not claim otherwise.

## 4. Tests (all offline except the authorised demo calls above)

- ALIVE `tests/test_living_book_semantics.py`: 14 passed — exact-substring
  resolution rejects paraphrase; invented spans → refused; genuine
  chapter-outside-passage quotes → attention (not refusal); zero grounding →
  attention; dropped numbers → attention; fixture labelling; UNCHANGED path;
  section parsing incl. markdown headers; full lifecycle via TestClient
  (create/list/get/reject), stale-source refusal (409), fuzzy-passage
  refusal (409).
- ALIVE living-book + chapter suites: `test_living_book.py`,
  `test_living_chapter.py`, `test_chapter_evaluation.py` re-run (see handover).
- Mission: `test_living_book_represent.py` (3, fake ALIVE), plus existing
  living-book suites re-run green.
- Frontend: `tsc --noEmit` clean, `vite build` clean, `LivingBookPage.test.tsx`
  (4 passed). No browser-driven verification was available in this
  environment; UI acceptance is build + unit + API-level.

## 5. Acceptance-scenario mapping

- A (experience comparison): PILOT-2 pair renders in the existing comparison
  view (`inconclusive`, `valid: false`, both arms truthful) — verified via API.
- B (source-linked explanation): attempt 2 — explanation with exact-span
  citations, provenance, standing, limitations; follow-up questions run in the
  retaining conversation.
- C (alternative representation): mechanism complete (mermaid renders through
  existing `BookMarkdown`); a completed real-model diagram is NOT yet
  demonstrated — truncation bound above. Not claimed.
- D (preservation failure): dropped-number attention, invented-span refusal,
  truncation attention, confused-refusal retention — all demonstrated live or
  in tests; nothing silently approved.
- E (source change): stale-chapter refusal tested; derived records keep their
  historical source identity; no live source was edited (hashes verified).
- F (model unavailable): honest 409 path in code; `pi_unavailable` observed
  live during R2 (first probe) and surfaced truthfully; reading/notes/evidence
  unaffected.

## 6. Cost and integrity

02C demo model calls: ~7 (attempts 1–4 incl. retries) + 1 offline-recomputed.
Manuscripts unchanged (hashes re-verified). No decisions or promotions made
by 02C. No reader profile built. Experience observations (requests,
rejections, preservation flags) are recorded as events, not learning claims.

## 7. Next recommended stage (separate commission)

Two-call record-then-render; completed real-model `diagram` + `compare` on a
process passage; Mission-proxy live call (1 call); reader-visible retry of
`attention` records; browser-driven UI verification.
