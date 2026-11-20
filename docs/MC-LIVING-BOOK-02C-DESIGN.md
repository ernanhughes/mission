# MC-LIVING-BOOK-02C — Semantic Mediation Design

Status: **design frozen for the first vertical slice; implementation in progress.**
Real-model operation authorised under a small bounded budget; fixture path is
the test default and is always clearly labelled.

Anchor text: *Language* ch07 ("Meaning Becomes the Source"), which specifies the
record schema this implementation reuses rather than reinventing:

```text
concepts      what a passage is about
claims        atomic statements the source makes
relations     directed connections between claims or concepts
qualifiers    scope, condition, exception, uncertainty on each claim
sequence      ordering, where order carries content
evidence      pointers to the material backing each claim
spans         where in the source each entry came from
```

## 1. Core distinction (from Language ch07)

**SOURCE ≠ SEMANTIC RECORD ≠ RENDERING.**

- The **source** is the canonical, approved, hash-identified chapter text.
  Read-only; never written by this commission.
- The **semantic record** is a fallible, versioned, inspectable derivation:
  `{concepts, claims, relations, qualifiers, sequence, evidence, spans}` bound
  to exact source version + passage offsets + task + model + session + receipts.
- The **rendering** is a task-specific view derived from the record
  (explanation, mermaid diagram, comparison table). Renderings are disposable;
  records are retained and re-checkable.

Traceability rule (ch07): *every consequential element of a rendering should
identify the record entry it came from and the exact source version and passage
supporting that entry. Traceability is required, but it is not proof of
correctness.*

## 2. What is reused (no new cognition)

| Need | Reused mechanism | Location |
| --- | --- | --- |
| Bounded model execution | existing chapter conversation session (`live.ask`, `task_mode="chat"`), 50 calls / 1M token envelope, revocable | `alive/living_book/service.py:ask`, `_prepare_session` |
| Source custody | approved capture, exact-hash chapter resolution, attachment checks | `alive/living_book/service.py`, `alive/workspace_api.py` |
| Citations | message citations (`document_id` + exact substring quotes) | `alive/living_book/service.py:_conversation_view` |
| Verification standing | message `verification` field surfaces in conversation view | same |
| Preservation checks | seven deterministic presence checks (headings, code, urls, numbers, equations, qualifications, quotes/tables) | `alive/chapter_workflow/evaluation_preservation.py` |
| Diagram rendering | existing mermaid + KaTeX blocks | `frontend/.../BookMarkdown.tsx` |
| Passage selection | existing reader selection → Ask/Keep flow | `LivingBookPage.tsx:onSelection` |
| Reading room | tabs, notes, quality, improve panels (untouched) | `LivingBookPage.tsx` |

No new model operation is introduced (deliberately: a new capability would need
a new typed dispatch binding — the Phase-A `authority_refused` lesson). The
mediation prompt travels the already-bound conversation path; all novelty is a
deterministic service layer around it (resolve → obligate → validate → retain).

Transport bounds (verified live 2026-11-20): the conversation path enforces a
1,536-token per-call output ceiling. The mediation instruction therefore
demands compact output (≤5 claims, quotes ≤160 chars, rendering ≤600 chars,
whole response ~900 tokens). A response that exceeds the ceiling is truncated
by the transport and fails closed — the candidate is retained with
`attention` + raw text, never silently accepted. The section parser tolerates
markdown header variants (`RECORD:` / `## RECORD`); section detection is the
only tolerant step — citation quotes and obligation checks remain exact.

No new memory database, workflow engine, model gateway, ranking system,
quality framework, or manuscript source is introduced.

## 3. Representation contract

Request: `{book_id, chapter_id, passage{quote,start,end}, task, conversation_id?,
idempotency_key}`. Tasks (first slice):

- **A. Reveal** — highlight distinctions already in the source
  (conditions, exceptions, definitions, assumptions, uncertainty).
- **B. Re-express** — another form of the same information
  (`explain` prose, `diagram` mermaid, `compare` table).
- **C. Add** — explicitly labelled external explanation; rendered in a
  visually separate "added" block, never merged into source claims.
- **D. Leave unchanged** — abstention with reason; a valid result.

Response (semantic record + rendering):

```text
representation_id, schema version
source: {approval_ref, capture_ref, chapter_id, chapter_sha256, passage{start,end,sha256}}
task, transformation class (reveal/re-express/add/unchanged)
record: {concepts[], claims[{text, spans[]}], relations[{from,to,type}],
         qualifiers[{claim, kind, text, spans[]}], sequence[], evidence[],
         not_represented[], ambiguous[]}
rendering: {format (markdown/mermaid/table), content}
citations: [{quote (exact substring), start, end}]
verification: {standing: verified|attention|refused, checks[], unresolved[]}
model: {name, conversation_id, session usage, call receipt}
```

## 4. Process (observable obligations)

1. Resolve exact source version + chapter; locate the passage by exact
   substring (reject fuzzy matches; record offsets + passage hash).
2. Derive preservation obligations from the passage: numbers, equations, code
   fences, URLs, qualification/negation sentences (QUALIFY scan), quote/table
   lines, entity mentions. These are recorded BEFORE generation.
3. Dispatch ONE bounded model call on the chapter conversation with the
   mediation instruction: quote exact substrings for every consequential
   claim; separate source-derived from added content; return the record fields
   above; abstain if the task cannot preserve obligations.
4. Validate deterministically: every citation quote is an exact substring of
   the passage; every obligation item is present or explicitly listed as
   `not_represented`/dropped-with-reason; added content carries the added
   label; no manuscript write occurred.
5. Standing: all checks pass → `verified`; any attention item or unresolved
   qualifier → `attention` (with the item listed); task unsuitable or
   validation unfixable → `refused` (original shown, no rendering).
6. Retain the record + rendering + receipts as workspace events; present
   source, rendering, citations, standing, limitations, and actions:
   inspect provenance, challenge/correct, reject, return to original.

A simplified explanation that drops the condition determining whether a claim
applies is an `attention`/`refused` outcome, never a `verified` view. A
reversed relationship arrow is a check failure, not a stylistic choice.

## 5. Reader interface

`Explore this passage` in the reading room, next to Ask/Keep: select a passage,
pick a task (Explain / Relationships / Diagram / Compare / Assumptions),
receive the rendering adjacent to the unchanged source with: original passage,
task, transformation class, verification standing, span citations (click →
scroll to source), unresolved limitations, added-content labelling, and
Reject / Show original actions. Follow-up questions ("why does this arrow…?")
run in the same conversation, which retains passage + record context.
Model-unavailable → honest unavailability; reading, notes, and deterministic
evidence keep working.

## 6. Experience + evaluation stance

Representation requests, rejections, corrections, and preservation failures are
recorded as observations through existing mechanisms. They are not interpreted
as demonstrated learning, comprehension improvement, or reader-profile updates.
No durable reader model is built.

Evaluated per §16 on six separate axes: source fidelity, technical validity,
task usefulness, provenance, abstention behaviour, cost. No claim that a
working rendering improves comprehension without reader-outcome evidence.

## 7. Stopping rule

Done when: a real chapter opens; a real source-bound passage is selected;
ALIVE produces ≥1 useful alternative representation via the real path under the
authorised budget; the result shows exact source version, checks, provenance,
and standing; the reader can inspect, reject, and return to the original;
state survives restart; manuscript unchanged (verified by hash).
