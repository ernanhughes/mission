# MC-LIVING-BOOK-02A — Living Intelligence Capability Audit and Design

**Status:** Audit and design complete. 02B was subsequently approved and implemented; see
[the 02B acceptance record](acceptance/mc-living-book-02b/README.md).

**Post-audit activation note:** this document preserves the audit-time state. The live v6/801–806
family became historical when a real 02B run exposed a 100,000-token ceiling in the section workflow.
That repair is **v7/901–906**. The follow-up quality gate is **v8/1001–1006**, which is current. The
accepted proposal remains readable as a v806 run. The audit's v6 references describe what was live
before those repairs, not the final activation.

**Scope:** one book (Distillation), one chapter (`14-chapter.md`, “Synthetic Data Generation”), one
task (economy), one transformation (a retained Chapter Improvement proposal), one measurable result
(a completed proposal, its model assessment and the author’s decision). No manuscript write, no
automatic learning and no general “living intelligence” platform.

---

## 1. Verdict

A narrow 02B is justified. The reusable core already exists in ALIVE:

- approved project-source custody, exact captures and hashes;
- a Living Book workspace with chapter reads, reading state, annotations, notes and conversations;
- a bounded, revocable Meta/Pi read session;
- the Chapter Improvement workflow (review → improve → save proposal → evaluate → record);
- retained proposal provenance, a deterministic text diff and append-only author decisions;
- bounded retrieval of prior owner decisions as improvement experience;
- Pi/model receipts and dispatch-time source and consent rechecks.

A full “understand, mediate, remember/adapt, act and evaluate” system is **not** justified by the
evidence. Two live gaps block the improvement journey today:

1. **The Living Book workspace’s source attachment is stale.** The book reports the current approval
   `abc83294-…`, but the workspace still points at `bd77a514-…`. The chapter-workflow plan request
   therefore returns `409 conversation_source_not_in_workspace`.
2. **The live Chapter Improvement family is v5/701–706.** The local AI-01A repair report records that
   this family fails current informed-stage binding rechecks after EXP-04 changes. The repaired
   v6/801–806 family is not exposed by the running service. The live endpoint’s
   `integrity.verified` flag is definition integrity, not proof of current stage executability.

02B must therefore begin with an explicit source reattachment step and a workflow-family activation
check. It must fail closed if either is not satisfied.

**Recommendation:** approve 02B only as the narrow journey in §8, after the activation checks in
§12 are accepted. Do not build the full system.

---

## 2. Evidence standard and live snapshot

This audit distinguishes four evidence states:

| Label | Meaning |
| --- | --- |
| **VERIFIED_LIVE** | A running Mission/ALIVE route returned the stated result during this audit. |
| **VERIFIED_TEST** | A focused automated test passed in this workspace. Scripted model gateways prove wiring, not editorial quality. |
| **PRESENT_UNWIRED** | Code exists but no running route or active workflow uses it. It is not a dependency for 02B. |
| **DESIGN_ONLY** | Proposed contract or behavior; not implemented or claimed as working. |

Method: inspected the running OpenAPI and route catalogue, called read-only Mission/ALIVE routes,
traced the code paths named below, ran the focused tests, and computed the chapter section plan
offline. No chapter workflow was launched and no model was called during the audit.

### 2.1 Live services

| Item | Observed value |
| --- | --- |
| ALIVE | `http://127.0.0.1:8000`, health `ok`, version `0.2.0` |
| Mission Control | `http://127.0.0.1:8790` |
| Distillation book | `72b95337-795f-5327-87c6-ad67e4246086` |
| Distillation workspace | `9a992443-ee5f-4a30-a52d-6760e584baf1` |
| Source root | `C:\books\distillation` |
| Manuscript root | `C:\books\distillation\content\books\distillation` |
| Binding | `bdaefced-4d88-4b62-ad20-ffe044c73d89` (live) |
| Current binding approval | `abc83294-fe42-4473-b4dc-643feac9a8ad` |
| Current binding capture | `dc7dda14-cb81-4c97-9514-32aa0746c545` |
| Current capture manifest SHA-256 | `41d298eb738d6facaa8156e4aa12cd7672cb62807dbde8ea74c7f89b9b8dcb01` |
| Current source | 1,260 files, 14,433,121 bytes, captured `2026-11-19T21:03:02Z`, refreshed `2026-11-19T21:09:53Z` |
| Workspace attachment | approval `bd77a514-5ddd-4aac-b0d2-e6046157478a`, capture `c7b03373-211e-476d-808a-550dd0e81138`, 1,273 files, 14,013,731 bytes |
| Model | `muse-spark-1.3-contributor`, transport `pi`, ready `true` |

The source changed between the workspace attachment and the binding’s current capture. Chapter 14’s
bytes did **not** change: both the live chapter read and the local file hash are
`ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05`.

The plan probe also caused ALIVE’s existing live-binding reconciliation to update
`last_refresh_at`; it did not create a new capture and did not change the chapter hash. The workspace
attachment still points at the old approval and capture. This is evidence that “read reconciliation”
and “workspace reattachment” are separate operations and must not be conflated in 02B.

### 2.2 Chapter 14 quality evidence

From Mission’s `book-quality-context.v1` for chapter 14:

| Measure | Status | Value / limitation |
| --- | --- | --- |
| Prose (`mission.prose.manuscript-prose-v1`) | `CURRENT` | overall `3`, rubric `manuscript-prose-v1`, model `opencode-go/deepseek-v4.1-flash`, observed `2026-11-16T21:47:33Z` |
| Economy dimension | `CURRENT` | score `2`; evidence `a rejection audit that discards its rejects is advertising`; `evidence_validated: false` |
| Technical claims | `NOT_RUN` | 0 claims, `NOT_ASSESSED`; not zero, not a pass |
| Writer readability | `NOT_RUN` | no chapter-level observation |
| Publication readiness | `NOT_RUN` | no publication assessment |
| Artifact Load | `NOT_RUN` | no observation |

Book-level prose coverage is 42/42 current; overall range 3.00–4.17; economy mean 2.90. Limitations
include “single-run model judgment; repeatability not established by one observation.” The quality
record is evidence for choosing a focus, not a verified fact or a publication verdict.

### 2.3 Executed checks

| Check | Result |
| --- | --- |
| ALIVE `tests/test_living_book.py` | 7 passed in 28.32s |
| Mission `backend/tests/test_living_book.py` | 6 passed in 2.69s |
| Live Mission chapter 14 read | 200; `ad89a4e9…`, 4,067 words, 27,034 rendered characters |
| Live Mission chapter 14 quality | 200; prose `CURRENT`, economy 2, technical/publication `NOT_RUN` |
| Live ALIVE chapter-workflow plan | **409** `conversation_source_not_in_workspace` |
| Live ALIVE experience preview (`/workspaces/{id}/experience`) | 200; `eligible_candidates: 0`, `selected: []`, `context_sha256` present |
| Live ALIVE MEMORY-03 route (`/experience/relevant`) | **404**; not registered |
| Live workflow catalogue | v5 and v701–v706 present; no v6/v801–v806 |
| Offline plan on the exact chapter file | 6 sections, 8 model calls, 12,288 output tokens, 900 s, plan `642e4792…` (not a live plan; see §4.2) |

An expanded ALIVE run including `tests/test_experience.py`, `tests/test_improvements.py` and
`tests/test_experience_memory.py` was stopped after the living-book tests completed and the remaining
process made no further progress. No pass or failure is claimed for those suites. They are not a 02B
dependency, and the audit does not rely on them.

---

## 3. Capability inventory

### 3.1 Reusable now

| Capability | Owner | Callable surface | Evidence | 02B use |
| --- | --- | --- | --- | --- |
| Project source custody, capture and hashes | ALIVE | `/api/v1/sources/...` | Live binding/capture; chapter hash verified | Read-only source identity |
| Source approval and revocation | ALIVE | `/sources/{capture}/approve`, `/sources/approvals/{id}/withdraw` | Live approval `abc83294-…`; binding current | Reading authority only; never widened by Mission |
| Living Book registration and chapter index | ALIVE | `/api/v1/living-books`, `/{id}`, `/{id}/chapters/{chapter}` | Live book ready; 42 chapters | Book/workspace/chapter mapping |
| Reading state, annotations and notes | ALIVE | `/living-books/{id}/reading`, `/annotations`, `/chapters/{id}/note` | Live book detail; 7 focused tests | Optional reader context |
| Workspace conversation and citations | ALIVE | `/living-books/{id}/ask`, `/conversations/{id}` | Live model ready; acceptance from 01 | Existing reading path only |
| Bounded model session | ALIVE | `chat.prepare` behind Living Book ask/note | 50 calls, 1,000,000 tokens, 1 hour, revocable | Separate consent for any model use |
| Quality context as untrusted owner context | Mission → ALIVE | `quality_context` on ask/note | `book-quality-context.v1`; `owner-context:quality` | Source of chapter-14 focus evidence |
| Chapter workflow plan/preview | ALIVE | `GET /workspaces/{id}/workflows/plan` | Route exists; live 409 on stale attachment | Plan and budget confirmation |
| Chapter Improvement run | ALIVE | `POST /workspaces/{id}/workflows` | Launch contract, 7 stages, 3 calls whole / 8 calls for six sections | Review → proposal → evaluate |
| Retained proposal and actual-text diff | ALIVE | `GET /workspaces/{id}/workflows/{run}/improvement` | `save_proposal`, `difflib` blocks, artifact integrity checks | Review UI |
| Author decision | ALIVE | `POST /workspaces/{id}/workflows/{run}/improvement/decisions` | Append-only event; `applied: false` | Accept/reject only in 02B |
| Prior owner-decision experience | ALIVE | `GET /workspaces/{id}/experience` | Live 200, 0 eligible; bounded 5 items/4,000 chars | Optional second-run experiment |
| Pi and model receipts | ALIVE | `/api/v1/pi/runs`, stage receipts, run detail | Existing workflow and Pi records | Evidence of what was sent |
| Writer/technical/publication evidence | Mission | `book-quality-context.v1` | Live `NOT_RUN` for chapter 14 | Excluded from the brief, shown as limits |

### 3.2 Present but not a dependency

| Capability | State | Why not used in 02B |
| --- | --- | --- |
| ALIVE-MEMORY-03 (`alive/experience_memory/`) | **PRESENT_UNWIRED** | No router in `alive/app.py`; live `/experience/relevant` returns 404. It is a discovery/qualification design over EXP-04 evaluations and only documentation-improvement has those today. |
| Independent `improvement.evaluated` records | **PRESENT_UNWIRED for chapters** | `chapter_workflow/evaluations.py` requires `documentation-improvement`; chapter runs use the `evaluate` stage model assessment instead. |
| Strategy candidate generation (EXP-03) | Existing | Not needed for one chapter/one focus; adds model calls and selection scope. |
| Conditional lessons (LEARN-01) | Existing | No chapter-14 lesson exists; 02B must not create one. |
| Demo tour / workspace demo | Existing demonstrations | They exercise separate scripted flows; they are not real-model evidence for this journey. |
| `accepted_with_edits` | Existing decision value | It requires an already-approved final Markdown file. 02B has no write authority, so it is hidden until a separate write phase. |

### 3.3 The important distinction

There are three different “evaluation” artifacts and they must not be merged:

1. **Mission prose evaluation** — a single-run model judgment about the manuscript, with rubric,
   dimensions, quotes and limitations. It is `CURRENT` for chapter 14 but not independently verified.
2. **Chapter workflow `evaluate` stage** — a model assessment of the original versus the retained
   proposal, with `verdict ∈ {promising, mixed, not_improved, undetermined}`. It is not an independent
   evaluation and not owner acceptance.
3. **`improvement.evaluated`** — an append-only independent evaluation record. It currently requires
   `documentation-improvement`; it is not produced by the chapter workflow.

02B may show all three only when each is actually present, with its own label. It must not call the
chapter evaluator “independent” or use a model verdict as proof of quality.

### 3.4 Gap summary

| Gap | Evidence | Effect | 02B action |
| --- | --- | --- | --- |
| Workspace source attachment stale | Live plan 409; workspace `bd77…` vs binding `abc83294…` | Chapter workflow cannot plan | Explicit refresh/re-plan; compare IDs |
| Informed family not live | Catalogue v5/701–706; no v6/801–806; AI-01A report | Executability unproven | Activate and verify before launch |
| No Mission improvement route/UI | Current gateway exposes reading/connect/quality, not improvement | Author cannot preview, launch or decide from Mission | Add the narrow gateway and review UI |
| No chapter independent evaluation | `evaluations.py` requires `documentation-improvement` | Cannot claim measured quality improvement | Label the stage result `model_assessment`; defer |
| MEMORY-03 unwired | No router; live route 404 | Evaluated experience memory is not available | Do not depend on it |
| Criteria is 600 chars | `Launch.criteria` limit | Full quality JSON cannot be sent | Deterministic brief + full evidence in Mission |
| `accepted_with_edits` needs a file | Decision code requires `final_path` | Would imply a write | Hide it in 02B |
| Source refresh changes edition | 1,273-file attachment vs 1,260-file current capture | Proposal may be against a different edition | Require review when chapter hash changes |

---

## 4. Current path and the gap

### 4.1 Reading path (working)

```text
React LivingBookPage
  -> Mission /api/living-book/projects/{project}/ask
       -> build_quality_context()                    Mission evidence, untrusted
       -> AliveClient.ask()
            -> ALIVE /api/v1/living-books/{book}/ask
                 -> _source_for_registration()       current binding approval
                 -> _ensure_workspace_attachment()   updates workspace to current approval
                 -> chat.prepare()                   50 calls / 1M tokens / 1 hour
                 -> live.ask()                       Meta/Pi, owner_context, citations
                 -> conversation + message + receipts
```

Reading works because `ask()` reattaches the workspace to the current binding approval; the explicit
refresh path uses the same reattachment after reconciling the live source. The chapter read is
hash-verified. Quality travels as `owner-context:quality`, not as visible chat text; the reader
context travels as `owner-context:reader`. Exact quotes are checked against the supplied entries.

### 4.2 Improvement path (blocked today)

```text
Mission (no route yet)
  -> ALIVE GET /workspaces/{ws}/workflows/plan
       -> chat.context_for(session, kernel, ws)      workspace attachment: bd77a514-…
       -> original_for(..., resources["approval_id"]) current binding: abc83294-…
       -> 409 conversation_source_not_in_workspace
```

The plan route does not call `_ensure_workspace_attachment`; only the Living Book ask/note/refresh
paths do. This is why reading is healthy and planning is not. The exact chapter can still be read from
the old capture, but the workflow recheck compares the resources it just resolved with the workspace
attachment. An ALIVE read may also advance the live binding’s `last_refresh_at` without moving the
workspace attachment, so the preview must compare approval/capture IDs, not just “current” status.

Once the attachment is reconciled, the plan must still prove that the selected definition is
currently executable. The live catalogue exposes v5 and v701–v706. The local AI-01A report says these
failed current informed-stage binding rechecks after EXP-04 changed shared experience code, and that
v6/v801–v806 are the repaired family. No v6/v801–v806 appears in the live catalogue. The offline plan
on the exact chapter file (6 sections, 8 calls, 12,288 output tokens, 900 s) is useful only as a
chapter-eligibility check; it is not a live workflow plan.

### 4.3 What 02B must therefore do first

1. Fetch the current book and workspace state.
2. If the workspace attachment does not match the current binding approval, tell the owner exactly
   what changed and require an explicit `POST /living-books/{book}/refresh`.
3. Re-read the book, chapter hash and source identity after refresh.
4. If the chapter hash changed, stop and ask the owner to read the new revision before improving.
5. Plan the chapter. If the plan returns no executable family, stop with a clear activation error.
6. Only then show the budget/authority confirmation.

No hidden workspace reattachment or source-edition refresh inside the preview or launch transaction.
ALIVE may reconcile a live binding’s freshness on a read; 02B must still detect the stale workspace
attachment and require the explicit `refresh` action to move it. A source refresh changes the exact
source edition used by the workflow; it is an owner action, not a side effect.

---

## 5. Architecture for 02B

```text
Mission Living Book UI
  |-- Reading (existing) ---------------------- Mission gateway -> ALIVE Living Book
  |
  `-- Improve this chapter (02B)
        |
        v
  Mission Improvement Gateway
    - current book/workspace/chapter identity
    - deterministic evidence envelope + <=600-char editorial brief
    - exact ALIVE plan/experience preview
    - explicit source-refresh and budget confirmation
        |
        v
  ALIVE workspace-scoped Chapter Improvement
    review -> improve -> save_proposal -> evaluate -> record_outcome
        |
        +--> retained proposal artifact + actual-text diff
        +--> model assessment (not independent, not acceptance)
        +--> Pi/model invocation receipts
        |
        v
  Mission Proposal Review
    - evidence used, exact plan, source/chapter hashes
    - proposal diff, coverage, limitations, model receipts
    - Accept / Reject (no write)
        |
        v
  ALIVE append-only decision (applied: false)
        |
        +--> experience preview for an optional second run
```

Reader and author modes share the same Living Book registration, source capture and workspace. Author
mode adds a workspace-scoped workflow action; it does not create a second book, source, model engine or
memory.

### Responsibilities

| Layer | Owns | Must not do |
| --- | --- | --- |
| Mission UI | Reading-room presentation, evidence display, confirmation, proposal review | Write files, call a model directly, store source bytes |
| Mission gateway | Project/book mapping, bounded evidence envelope, exact ALIVE route allowlist, error translation | Generic proxy, parallel memory, source approval, workflow execution |
| ALIVE Living Book | Source custody, chapter reads, workspace, conversations, read sessions | Write the manuscript, infer approval from a read |
| ALIVE workflow | Plan, admission, Grant, model dispatch, proposal artifact, evaluation, decision record | Auto-accept, apply a proposal, widen source scope |
| Author | Confirm source refresh, confirm budget, decide the proposal | Be replaced by a model or by Mission |

### Why Mission does not send the full quality JSON to the workflow

The Chapter Improvement launch accepts `criteria` with `max_length=600`. It has no owner-context field,
and its review/improve/evaluate stages do not verify Mission quality citations. Sending the full
`book-quality-context.v1` would either be silently truncated or become unverified prompt text. 02B
therefore sends a short, deterministic **editorial brief** derived from selected evidence and keeps
the full evidence in Mission for the author. This is semantic mediation, not evidence laundering.

---

## 6. Authority model

| Authority | Grant | Bound to | 02B rule |
| --- | --- | --- | --- |
| Read | Source approval (`context.reason`, `context.validate`) and exact capture | Binding, approval, capture, scope hash | Reading and preview may read the approved source. No approval is created or widened by Mission. |
| Model data use | `admission.standing.prepared/approved` with model, endpoint, paths and budget | Conversation, model, endpoint, resources, 1-hour TTL | A read session is separate from a workflow admission. Entering the improvement flow requires its own confirmation. |
| Action | `workflow.execution.authorized` / owner workflow admission and Grant | Definition, inputs, model roles, source, budget | Launch requires the exact plan hash, section confirmation where applicable, model allowlist and budget confirmation. |
| Write | None in 02B | — | No manuscript write, no apply, no overwrite. A decision records judgement only (`applied: false`). |

Additional rules:

- A reading session does not authorize a workflow run.
- A workflow decision does not authorize a source write.
- `accepted_with_edits` is not exposed in 02B because it requires an already-approved edited file.
- Revocation, expiry, source change and budget exhaustion stop further model calls; completed steps are
  retained, not replayed.
- The Mission gateway never receives an ALIVE database credential or a filesystem path it can write.

---

## 7. Semantic mediation design

### 7.1 Intent envelope

`living-book-improvement-intent.v1` is built deterministically by Mission. It is not generated by a
model.

```json
{
  "schema": "living-book-improvement-intent.v1",
  "project_id": "distillation",
  "book_id": "72b95337-795f-5327-87c6-ad67e4246086",
  "workspace_id": "9a992443-ee5f-4a30-a52d-6760e584baf1",
  "chapter": {
    "chapter_id": "14-chapter.md",
    "path": "content/books/distillation/14-chapter.md",
    "title": "Synthetic Data Generation",
    "sha256": "ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05"
  },
  "source": {
    "binding_ref": "bdaefced-4d88-4b62-ad20-ffe044c73d89",
    "approval_ref": "abc83294-fe42-4473-b4dc-643feac9a8ad",
    "capture_ref": "dc7dda14-cb81-4c97-9514-32aa0746c545",
    "status": "current"
  },
  "focus": "economy",
  "evidence": [
    {
      "ref": "mission:quality:mission.prose.manuscript-prose-v1:14-chapter.md:2026-11-16T21:47:33Z",
      "kind": "model_judgment",
      "status": "CURRENT",
      "measure_id": "mission.prose.manuscript-prose-v1",
      "rubric": "manuscript-prose-v1",
      "observed_at": "2026-11-16T21:47:33.820969Z",
      "chapter_revision": "b974aa1cfdab1b5b1ed063969765731094fd69817b86f74eeb54da64cf79f3f7",
      "quote": "a rejection audit that discards its rejects is advertising",
      "quote_validated": false,
      "value": {"overall": 3, "economy": 2},
      "limitations": [
        "Single-run model judgment; repeatability not established by one observation.",
        "The quoted evidence is not independently verified merely because it is quoted."
      ]
    }
  ],
  "excluded": [
    {"ref": "mission:technical:mission.technical.claims", "reason": "NOT_RUN"},
    {"ref": "mission:writer:mission.writer.readability", "reason": "NOT_RUN"},
    {"ref": "mission:publication:mission.publication.readiness", "reason": "NOT_RUN"}
  ],
  "author_note": "",
  "criteria": "<=600-char deterministic brief>",
  "criteria_sha256": "sha256 of criteria",
  "intent_sha256": "sha256 of the canonical envelope without this field"
}
```

The quality-system `chapter_revision` is deliberately different from the ALIVE source-file SHA-256.
They describe different systems and are never compared as if they were the same hash.

### 7.2 Brief construction

1. The author selects one focus. 02B offers `economy` only.
2. Use only `CURRENT` evidence for that focus. `STALE`, `NOT_RUN`, `UNAVAILABLE` and `ERROR` are
   excluded with a visible reason; they are never converted to zero.
3. Require `status: CURRENT`; retain the measure’s `chapter_revision` as quality-system
   provenance. It is **not** the ALIVE source-file SHA-256 and must not be compared to it. Both
   hashes are shown. A missing revision is blocked; a different hash is not by itself evidence of
   staleness because the two systems hash different things.
4. Preserve exact quotes, measure id, rubric, observation time and limitations in the envelope.
5. Compose a fixed-template brief of at most 600 characters. If it does not fit, require the author to
   shorten the note or select fewer evidence items. Never silently truncate.
6. State that quoted Mission evidence is not chapter text and is not verified. The workflow's review
   stage must quote the chapter, not the brief.
7. The brief is sent as `criteria`; the envelope, full evidence and `intent_sha256` stay in Mission and
   are shown in the preview.
8. The run detail is labelled: "Brief supplied by the author; quality measures are Mission evidence.
   The model assessment is not an independent evaluation."

Chapter-14 example brief (about 530 characters):

```text
Improve economy in "Synthetic Data Generation" without dropping technical claims, source citations or uncertainty. Mission prose evidence (CURRENT, observed 2026-11-16): overall 3.0; economy 2.0; quoted evidence "a rejection audit that discards its rejects is advertising" (evidence_validated=false; not chapter text). Preserve the chapter's argument, technical qualifications, examples and references. Keep each section's full substance and approximate length; do not omit material. Return a complete proposal; do not write the source.
```

### 7.3 What is excluded from the model

- Chat transcripts and living notes: conversations are not learning and are not evidence of quality.
- Reader annotations unless the author explicitly selects one; an annotation is a reader observation,
  not an evaluation.
- `NOT_RUN` technical, Writer, publication and Artifact Load measures.
- Any full quality JSON or arbitrary source file.
- Model-written feedback or rationales as instructions.
- A source that is not currently approved.

### 7.4 Abstention

The preview is not eligible when:

- the chapter is missing, changed or not in the approved capture;
- the selected focus has no `CURRENT` evidence;
- the workspace attachment is stale and the owner declines refresh;
- the plan returns no executable workflow family;
- the model is not on the owner allowlist or Pi is unavailable;
- the owner does not confirm the exact plan and budget.

Abstention is a valid result and must be displayed with the reason. Do not fabricate a brief or force a
run.

---

## 8. Minimal 02B specification

### 8.1 Goal

On Distillation chapter 14 (“Synthetic Data Generation”), let the author turn current economy evidence
into one retained Chapter Improvement proposal, inspect it, record a decision, and see whether a
second run can retrieve that decision as experience. No source write and no claim of measured quality
improvement.

The measurable result is concrete and bounded: the run reaches `COMPLETED`, the proposal artifact and
actual-text diff are retained, the `evaluate` stage result is recorded as `model_assessment`, the
author’s decision is append-only with `applied: false`, and the chapter SHA-256 is unchanged. If the
second run is performed, the additional result is `experience.supplied: verified` or an explicit
abstention. Editorial quality improvement is not part of the 02B result.

### 8.2 User journey

1. **Open chapter 14.** The reading room shows the existing quality rail and a new “Improve this
   chapter” action only when the chapter is readable and current.
2. **Preview.** Mission shows:
   - book, chapter, path, SHA-256 and source binding/approval/capture;
   - the selected economy evidence, quote, observation time and limitations;
   - the generated 600-character brief and its hash;
   - excluded `NOT_RUN` measures with reasons;
   - the exact ALIVE plan: mode, workflow version, sections, model calls, output tokens, wall time,
     plan SHA-256;
   - the experience preview: eligible candidate count and selected items (initially 0);
   - the authority statement: read, model data use, action, no write;
   - the model and endpoint.
3. **Source reconciliation, if needed.** If the workspace attachment is stale, the preview explains
   the mismatch and offers an explicit “Refresh source and re-plan” action. The owner must confirm.
   If the chapter hash changes, the preview stops and asks the owner to read the new revision.
4. **Confirm plan and budget.** The owner confirms the exact plan hash, estimated calls/tokens/time and
   the model. No launch without this confirmation.
5. **Run.** Mission launches the workspace workflow. The UI shows the run timeline and keeps polling a
   scoped run detail. No model call is made by Mission.
6. **Review.** The UI shows:
   - original and proposal hashes, artifact id, coverage and limitations;
   - a line-level diff from the retained texts, truncated visibly if necessary;
   - the chapter `evaluate` stage result, labelled `model_assessment`, never “independent”;
   - Pi/model invocation receipts and the exact experience supplied (if enabled);
   - source version at review time, with `current` / `earlier_version` / `unverifiable`.
7. **Decide.** The author records `accepted` or `rejected` with an optional comment. The request carries
   the exact `proposal_sha256` the author saw. The decision is append-only and `applied: false`.
   `accepted_with_edits` is not shown in 02B.
8. **Experience preview (optional).** The second preview shows the first decision as an eligible
   experience item, with its bounded excerpt and source-approval status. The owner may launch a second
   run with `use_experience=true`. This is the experiment in §9.

### 8.3 Non-goals

- no manuscript edit, apply, overwrite or publication;
- no batch, cross-chapter or cross-book run;
- no full-book improvement;
- no new memory, experience, evaluation or workflow engine;
- no automatic model choice or strategy generation;
- no transfer/quality-improvement claim;
- no change to the reading room’s existing ask/note behavior.

### 8.4 Model and budget

- Use the ALIVE-configured owner-approved model (`muse-spark-1.3-contributor` at audit time), through
  Pi. Mission does not accept a free-text model or endpoint.
- Whole-chapter plan: 3 model calls, 24,576 output tokens, 900 s (for a short chapter).
- Chapter 14 is sectioned: the offline plan on the exact file is 6 sections, 8 model calls, 12,288
  output tokens, 900 s. The live plan is authoritative and must be confirmed after refresh.
- The run has its own workflow admission; it does not reuse the reading session budget.
- The UI shows the budget before launch and the actual usage after.

---

## 9. Experience-experiment plan

**Question:** when an author has decided one Chapter Improvement proposal, does the same workspace’s
next run retrieve that decision and supply it to the Improve step, and does the dispatch receipt prove
it?

This is a two-run case study, not a powered experiment. It measures retrieval and delivery, not
learning or quality improvement.

### 9.1 Design

| Arm | Run | `use_experience` | Preconditions | Observation |
| --- | --- | --- | --- | --- |
| A (control) | First chapter-14 run | `false` | Current source/chapter and plan; no prior decision | Proposal, evaluation, decision, usage |
| B (treatment) | Second chapter-14 run | `true` | Same chapter, criteria, model and plan; A has a decision | Experience preview, supplied items, dispatch match, usage |

Both runs use the same chapter hash, criteria hash and model. If the chapter or criteria changes, it is
a new case, not a comparison.

### 9.2 Expected retrieval

A’s decision is eligible for B if:

- A’s run has complete provenance (authorization, saved proposal artifact, original);
- A has an explicit latest decision;
- the source approval used by A’s proposal is still authorized;
- the criteria overlap ranks it within the 5-item / 4,000-character bound.

B’s preview must show the selected item with `improvement_id`, decision, decision event, criteria
overlap, same-chapter bonus, owner comment if any, and `source_text_included`. B’s run detail must show
`experience.supplied: verified` and the Improve invocation’s context hash matching the supplied
experience. If the source is no longer authorized, the item may remain with a withheld notice; the
withheld source text must not be sent.

### 9.3 Claims

| Claim | Established by | 02B statement |
| --- | --- | --- |
| `retrieval_succeeded` | B preview has at least one selected item | Report yes/no |
| `experience_supplied` | B run’s Improve invocation context matches the supplied item and `experience_retrieval.context_sha256` | Report verified/partial/mismatch |
| `experience_applied` | No record links a proposal outcome to a specific experience item | **Not established** |
| `quality_improved` | No independent, frozen evaluation of A versus B | **Not established** |
| `transfer_demonstrated` | No held-out document and same frozen key | **Not established** |

### 9.4 Stop rules

- If A is rejected with a critical failure, B may retrieve a caution; do not present it as a strategy.
- If no item is eligible, B records `abstained` and runs without experience only if the owner chooses;
  it must not force an item into context.
- If the source approval is withdrawn, B stops before the model call.
- If the model or plan changes, the comparison is invalid; label it a new case.
- Negative results are retained and reported.

### 9.5 What would justify a later experiment

Only after 02B has real A/B records, one could design a controlled comparison on a held-out chapter
with a frozen rubric and an independent evaluator. That is a separate commission. It is not part of
02B, and no “learning” claim is made before it.

---

## 10. API and data contracts

### 10.1 Mission routes (DESIGN_ONLY)

All routes are under `/api/living-book/projects/{project_id}` and use the existing loopback-only
`AliveClient`.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/improvement/preview?chapter_id=…&focus=economy` | Build intent, read book/plan/experience, return eligibility and blockers |
| `POST` | `/improvement` | Launch one confirmed run |
| `GET` | `/improvement/{run_id}` | Scoped run, proposal, diff, evaluation, receipts, decision |
| `POST` | `/improvement/{run_id}/decision` | Record `accepted` or `rejected` |
| `POST` | `/refresh` | Existing source-refresh route; used only after explicit confirmation |

No generic ALIVE proxy is added. The client methods are exact:

| ALIVE route | Use |
| --- | --- |
| `GET /api/v1/living-books/{book_id}` | Book, workspace, chapter index, source view |
| `GET /api/v1/workspaces/{workspace_id}` | Workspace metadata and source attachments for the stale-attachment check |
| `POST /api/v1/living-books/{book_id}/refresh` | Explicit source reconciliation |
| `GET /api/v1/workspaces/{workspace_id}/workflows/plan` | Exact plan, version, budget, source |
| `GET /api/v1/workspaces/{workspace_id}/experience` | Bounded prior-decision preview |
| `POST /api/v1/workspaces/{workspace_id}/workflows` | Launch `Launch` request |
| `GET /api/v1/workspaces/{workspace_id}/workflows/{run_id}` | Run status and stage detail |
| `GET /api/v1/workspaces/{workspace_id}/workflows/{run_id}/improvement` | Proposal, diff, evaluation, state |
| `POST /api/v1/workspaces/{workspace_id}/workflows/{run_id}/improvement/decisions` | Append-only decision |
| `GET /api/v1/workspaces/{workspace_id}/improvements` | Optional recent-proposal summary |
| `GET /api/v1/workflow-runs/{run_id}/stages/{attempt_id}/pi-receipt` | Model receipt when the run detail points to it |

### 10.2 `ImprovementPreview`

```json
{
  "schema": "living-book-improvement-preview.v1",
  "eligible": true,
  "blocked": [],
  "intent": {"schema": "living-book-improvement-intent.v1", "...": "..."},
  "plan": {
    "mode": "sections",
    "workflow_version": 806,
    "definition_sha256": "...",
    "binding_sha256": "...",
    "sections": 6,
    "model_calls": 8,
    "output_tokens": 12288,
    "wall_seconds": 900,
    "plan_sha256": "...",
    "chapter_sha256": "ad89a4e9..."
  },
  "experience": {
    "enabled": false,
    "eligible_candidates": 0,
    "selected": [],
    "abstained": true
  },
  "authority": {
    "read": "approved source, exact capture",
    "model": "separate workflow admission and budget confirmation",
    "action": "workspace Chapter Improvement, proposal only",
    "write": "none"
  },
  "model": {"name": "muse-spark-1.3-contributor", "transport": "pi", "ready": true},
  "source": {
    "binding_ref": "...",
    "approval_ref": "...",
    "capture_ref": "...",
    "chapter_current": true,
    "workspace_attachment_current": true
  }
}
```

`blocked` codes include `chapter_missing`, `chapter_changed`, `quality_not_current`,
`source_attachment_stale`, `source_refresh_required`, `plan_unavailable`, `workflow_family_unavailable`,
`model_unavailable`, `budget_not_confirmed`, `consent_expired`, and `alive_unavailable`.

### 10.3 `ImprovementLaunch`

```json
{
  "chapter_id": "14-chapter.md",
  "focus": "economy",
  "intent_sha256": "...",
  "plan_sha256": "...",
  "criteria": "<=600 chars, exactly the brief shown>",
  "model": "muse-spark-1.3-contributor",
  "use_experience": false,
  "confirmed": true,
  "idempotency_key": "mission-02b-…"
}
```

Mission re-reads the chapter/source/quality, rebuilds the intent, and rejects the launch if
`intent_sha256`, `plan_sha256`, `criteria`, model or chapter hash changed. Mission then sends ALIVE’s
`Launch` body:

```json
{
  "chapter_path": "content/books/distillation/14-chapter.md",
  "criteria": "<=600 chars>",
  "model": "muse-spark-1.3-contributor",
  "use_experience": false,
  "plan_sha256": "...",
  "confirmed": true,
  "idempotency_key": "mission-02b-…"
}
```

### 10.4 `ImprovementRun`

```json
{
  "schema": "living-book-improvement-run.v1",
  "book_id": "...",
  "workspace_id": "...",
  "run_id": "...",
  "improvement_id": "...",
  "status": "COMPLETED",
  "status_label": "Proposal retained; awaiting author decision",
  "intent_sha256": "...",
  "plan": {"workflow_version": 806, "plan_sha256": "...", "model_calls": 8},
  "source": {"chapter_sha256": "ad89a4e9...", "source_version": "current"},
  "proposal": {
    "artifact_id": "...",
    "sha256": "...",
    "coverage": "complete",
    "limitations": "...",
    "change": {"lines_added": 0, "lines_removed": 0, "blocks": [], "truncated": false}
  },
  "evaluation": {
    "status": "evaluated",
    "kind": "model_assessment",
    "verdict": "promising|mixed|not_improved|undetermined",
    "limitations": "...",
    "model": "muse-spark-1.3-contributor"
  },
  "experience": {
    "enabled": false,
    "supplied": "not_dispatched",
    "items": [],
    "retrieval": {}
  },
  "decision": {"state": "pending", "decision": null, "comment": null, "applied": false},
  "receipts": {"stages": [], "pi_runs": []}
}
```

### 10.5 `DecisionRequest`

```json
{
  "decision": "accepted",
  "proposal_sha256": "exact hash shown to the author",
  "comment": "economy: tightened the rejected-audit example without dropping the claim",
  "acknowledge_earlier_version": false,
  "idempotency_key": "mission-02b-decision-…"
}
```

`accepted_with_edits` is rejected in 02B with `decision_not_available_without_write_authority`.
Mission forwards only the allowed fields and never writes `final_path`.

If the retained proposal was generated from an earlier chapter version, the UI must show that fact
and require a second, explicit acknowledgement before Mission sets `acknowledge_earlier_version: true`.
It is never defaulted to true.

### 10.6 Error translation

| ALIVE refusal | Mission response | UI action |
| --- | --- | --- |
| `conversation_source_not_in_workspace` | `source_attachment_stale` | Offer explicit refresh and re-plan |
| `workspace_workflow_source_changed` | `source_changed` | Re-read chapter; stop |
| `source_withdrawn` / `source_approval_expired` | `source_unavailable` | Stop; show approval state |
| `project_file_changed_since_capture` | `chapter_changed` | Refresh/re-read; stop |
| `Validate and confirm this exact section plan…` | `plan_confirmation_required` | Re-preview; do not launch |
| `Select an owner-approved model through Pi` | `model_unavailable` | Show model readiness |
| `workspace_workflow_authority_changed` | `consent_changed` | Stop; new confirmation |
| `standing_budget_exhausted` | `budget_exhausted` | Stop; no automatic renewal |
| `evaluation_quotes_not_in_versions` | `evaluation_invalid` | Keep proposal; show failure |
| decision hash/version conflicts | `proposal_changed` | Reload; show current proposal |
| ALIVE timeout/unreachable | `alive_unavailable` | 503; preserve reading room |

---

## 11. Acceptance tests

### 11.1 Mission backend

| Test | Expected |
| --- | --- |
| `test_preview_uses_only_current_quality` | `CURRENT` economy evidence selected; `STALE`/`NOT_RUN` excluded with reasons |
| `test_preview_brief_is_bounded_and_exact` | `<=600` chars; `criteria_sha256` matches; no silent truncation |
| `test_preview_reports_source_attachment_stale` | `eligible: false`, `blocked` includes `source_attachment_stale` |
| `test_refresh_requires_explicit_confirmation` | No refresh without the owner action |
| `test_preview_maps_plan_without_trusting_it` | Plan hash/version/model_calls/output_tokens preserved |
| `test_launch_requires_intent_and_plan_hashes` | 409/422 before any ALIVE launch |
| `test_launch_rejects_changed_quality_or_chapter` | Stops before the workflow |
| `test_launch_is_idempotent` | Same key returns the same run; different settings conflict |
| `test_run_detail_labels_model_assessment` | `kind: model_assessment`; never “independent” |
| `test_decision_forwards_exact_proposal_sha` | Mismatch is rejected; no decision recorded |
| `test_decision_is_append_only_and_applied_false` | History retained; no file write |
| `test_decision_accept_with_edits_is_refused` | `decision_not_available_without_write_authority` |
| `test_no_manuscript_write_routes` | No Mission route writes a chapter or source file |
| `test_alive_unavailable_preserves_reading` | 503/blocked state; reading still available |

### 11.2 ALIVE integration

| Test | Expected |
| --- | --- |
| `test_refresh_reattaches_workspace_then_plan_succeeds` | Workspace approval becomes current; plan returns an executable family |
| `test_plan_returns_exact_family_not_a_legacy_fallback` | v6/801–806 or the active repaired family; no silent v5 fallback |
| `test_launch_without_experience_records_disabled` | `experience.enabled: false`, no items sent |
| `test_launch_with_experience_verifies_supplied` | Improve invocation context matches supplied item and retrieval hash |
| `test_experience_source_revocation_stops_before_model` | Refusal; no further call |
| `test_decision_does_not_change_chapter_hash` | Chapter bytes unchanged before/after decision |
| `test_run_and_decision_keep_receipts` | Stage/model/Pi references resolve |
| `test_session_revocation_and_expiry_stop_calls` | Later calls refused; completed work retained |
| `test_source_change_marks_proposal_earlier_version` | Decision requires acknowledgment; no silent current claim |

### 11.3 Frontend

| Test | Expected |
| --- | --- |
| `test_improvement_action_hidden_when_not_eligible` | No action for `NOT_RUN`, stale source or missing chapter |
| `test_preview_shows_evidence_authority_and_budget` | Measure, quote, limitations, read/model/action/write, calls/tokens/time |
| `test_stale_source_requires_explicit_refresh` | Clear mismatch message and owner confirmation |
| `test_run_timeline_and_diff_are_visible` | Stages, proposal, diff, coverage, limitations |
| `test_decision_labels_no_write` | “Records judgement only; does not change the book” |
| `test_experience_preview_shows_abstention` | Empty selection is a valid result |
| `test_quality_scores_are_not_publication_verdicts` | No composite or release claim |

### 11.4 Real acceptance

`REAL-02B-01` must record, for one authorized chapter-14 run:

- project/book/workspace ids, binding/approval/capture, chapter path and SHA-256;
- the selected quality measure, observation time, quote, limitations and brief;
- live plan mode/version/sections/model calls/output tokens/wall time/plan hash;
- model, endpoint and Pi receipts;
- run id, status, stage outcomes and proposal artifact id/hash;
- proposal diff summary and evaluation verdict with `kind: model_assessment`;
- exact experience preview before the second run, if run;
- decision event id, decision, comment, `source_version_at_decision`, `applied: false`;
- evidence that the chapter file hash did not change.

A scripted/fixture run may prove wiring, but it must be labelled as such. It is not real-model evidence
and must not be counted as `REAL-02B-01`.

---

## 12. Activation and approval gate

02B should not start until the owner decides these four points:

1. **Source refresh.** Accept that refreshing the Distillation book source will reconcile the workspace
   to the current binding (`abc83294-…`, 1,260 files) from the old attachment (`bd77a514-…`, 1,273
   files). Chapter 14’s hash is unchanged, but the whole-source edition used by the companion changes.
   Recommended: yes, with the exact mismatch shown before confirmation.
2. **Workflow family.** Activate the repaired informed family (v6/801–806) with a normal ALIVE restart
   and verify that planning returns an executable version before any run. Recommended: yes. Do not
   launch against v5/701–706 based only on `integrity.verified`.
3. **Model spend.** Authorize one real chapter-14 run through Meta/Pi: 8 model calls, 12,288 output
   tokens, 900 s (live plan is authoritative). A second `use_experience=true` run is optional and
   separately budgeted.
4. **Decision scope.** Approve `accepted`/`rejected` only; hide `accepted_with_edits` until a separate
   write phase exists. Approve the experience experiment as a case study with no quality-improvement
   claim.

If any of these is declined, 02A remains a valid audit but 02B cannot produce verified live evidence.
The correct next action is to stop and record the blocker, not to simulate the journey.

---

## 13. Do-not-build list

- Do **not** build a Mission source store, capture system or hash verifier. ALIVE owns custody.
- Do **not** add a Mission model client, Pi call, prompt loop or conversation engine.
- Do **not** build a parallel memory, experience, embedding, vector store or evaluation system.
- Do **not** add a new database table or migration for 02B.
- Do **not** treat a conversation, living note or reader annotation as learning.
- Do **not** convert a model score into a verified fact or a publication verdict.
- Do **not** average incompatible rubrics or turn `NOT_RUN` into zero.
- Do **not** auto-approve, auto-launch, auto-renew, auto-retry or auto-decide.
- Do **not** write, apply or overwrite a manuscript; do not expose `accepted_with_edits` in 02B.
- Do **not** add a generic ALIVE proxy or accept a browser-supplied URL/model/endpoint.
- Do **not** batch chapters, cross books or claim transfer in 02B.
- Do **not** depend on `alive/experience_memory/` until it is registered, tested and given a
  chapter-relevant evidence source. Today it is unwired and documentation-only.
- Do **not** call the chapter `evaluate` stage an independent evaluation.
- Do **not** use a fixture or scripted gateway as real-model acceptance.
- Do **not** hide a source refresh inside a preview or launch transaction.
- Do **not** claim “quality improved” from a proposal, a diff or a model verdict.

---

## 14. Related records

- `docs/MC-LIVING-BOOK-01.md` — reading-room architecture and quality contract.
- `docs/acceptance/mc-living-book-01/README.md` — real reading-room acceptance.
- `docs/acceptance/mc-living-book-02a/README.md` — this audit’s reproducible probes.
- `C:\Projects\alive\docs\living-book\ALIVE-LIVING-BOOK-01.md` — engine contract.
- `C:\Projects\alive\docs\intelligence\ALIVE-AI-01A-WORKFLOW-BINDING-REPAIR.md` — informed-family
  repair report; local evidence, not yet live.
- `C:\Projects\alive\docs\memory\ALIVE-MEMORY-03.md` — experience-memory design; not wired.
