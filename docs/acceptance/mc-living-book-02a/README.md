# MC-LIVING-BOOK-02A — Audit evidence

**Date:** 2026-11-19

**Scope:** read-only capability audit and 02B design. No chapter workflow was launched, no model was
called during this audit, and no manuscript file was written.

**Design:** [MC-LIVING-BOOK-02A](../../MC-LIVING-BOOK-02A.md)

**Probe:** [live-probe.ps1](live-probe.ps1) writes [live-probe.json](live-probe.json). It reads Mission
and ALIVE, makes one plan request, does not call `POST /refresh`, launches no workflow and calls no
model. ALIVE may reconcile a live binding’s freshness during a read.

---

## 1. Services and book

| Item | Observed |
| --- | --- |
| ALIVE | `http://127.0.0.1:8000`, health `ok`, version `0.2.0` |
| Mission Control | `http://127.0.0.1:8790` |
| Distillation book | `72b95337-795f-5327-87c6-ad67e4246086` |
| Workspace | `9a992443-ee5f-4a30-a52d-6760e584baf1` |
| Model | `muse-spark-1.3-contributor`, transport `pi`, ready `true` |
| Reading state | `ready`; source current; 42 chapters |

Chapter 14:

| Item | Observed |
| --- | --- |
| Title | Synthetic Data Generation |
| Path | `content/books/distillation/14-chapter.md` |
| Live SHA-256 | `ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05` |
| Local file SHA-256 | same |
| Words / rendered characters | 4,067 / 27,034 |
| Local file bytes | 27,743 |

## 2. Quality evidence used by the design

Mission `GET /api/living-book/projects/distillation/quality?chapter_id=14-chapter.md` returned 200:

- prose `CURRENT`, rubric `manuscript-prose-v1`, model `opencode-go/deepseek-v4.1-flash`,
  observed `2026-11-16T21:47:33.820969Z`, overall `3`;
- economy score `2`, evidence
  `a rejection audit that discards its rejects is advertising`, `evidence_validated: false`;
- technical claims `NOT_RUN` (0 claims, `NOT_ASSESSED`);
- Writer readability `NOT_RUN`;
- publication readiness `NOT_RUN`;
- Artifact Load `NOT_RUN`.

Book coverage: 42/42 current prose observations, overall range 3.00–4.17, economy mean 2.90. The
quality record is evidence for choosing economy, not a verified fact.

The quality measure’s `chapter_revision` is `b974aa1c…`, a quality-system hash. It is not ALIVE’s
source-file SHA-256 `ad89a4e9…`. The audit keeps both as provenance and treats Mission’s `CURRENT`
status as the freshness authority; it does not compare the two hashes as if they described the same
thing.

## 3. The observed improvement-path blocker

The current source binding and the workspace attachment disagree:

| Item | Current binding / book | Workspace attachment |
| --- | --- | --- |
| Approval | `abc83294-fe42-4473-b4dc-643feac9a8ad` | `bd77a514-5ddd-4aac-b0d2-e6046157478a` |
| Capture | `dc7dda14-cb81-4c97-9514-32aa0746c545` | `c7b03373-211e-476d-808a-550dd0e81138` |
| Files | 1,260 | 1,273 |
| Bytes | 14,433,121 | 14,013,731 |

The live plan request returned:

```text
GET /api/v1/workspaces/9a992443-ee5f-4a30-a52d-6760e584baf1/workflows/plan
  ?chapter_path=content/books/distillation/14-chapter.md

409 conversation_source_not_in_workspace
```

Why reading still works: the Living Book `ask()` path calls `_source_for_registration()` and
`_ensure_workspace_attachment()` before preparing the session. The workflow plan path does not. This is
the precise gap 02B must close with an explicit source reattachment step.

The plan probe also caused ALIVE’s existing live-binding reconciliation to update `last_refresh_at` to
`2026-11-19T21:09:53Z`. It did not create a new capture and did not change the chapter hash. The
workspace attachment remained old. “Live-binding freshness” and “workspace reattachment” are separate
operations.

## 4. Workflow and experience state

| Check | Observed |
| --- | --- |
| Workflow catalogue versions | `706, 705, 704, 703, 702, 701, 606, 605, 604, 603, 602, 601, 506, 505, 504, 503, 502, 501, 5, 4, 3, 2, 1` |
| Repaired v6 / v801–v806 | **not present** |
| Workspace experience preview | 200; `eligible_candidates: 0`; `selected: []`; context hash present |
| Workspace improvements | 200; pending/accepted/rejected/accepted_with_edits all 0 |
| ALIVE-MEMORY-03 `/experience/relevant` | **404 Not found** |
| Offline chapter plan on the exact file | 6 sections, 8 model calls, 12,288 output tokens, 900 s, plan `642e479274374abd157c1eaf8b5a974f9a39caef584f0d65b2fa01c0f979f42b` |

The offline plan is a chapter-eligibility check, not a live plan. The live plan is blocked by the
source attachment. The local AI-01A report says v5/701–706 fail current informed-stage binding
rechecks; the live catalogue does not expose the repaired family. `integrity.verified` in the catalogue
is definition integrity, not current stage executability.

## 5. Focused tests

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/test_living_book.py -o addopts=""` (ALIVE) | **7 passed** in 28.32 s |
| `.\.venv\Scripts\python.exe -m pytest -q backend\tests\test_living_book.py` (Mission) | **6 passed** in 2.69 s |

An expanded ALIVE run including `tests/test_experience.py`, `tests/test_improvements.py` and
`tests/test_experience_memory.py` was stopped after the living-book tests completed and the remaining
process made no further progress. No pass or failure is claimed for those suites. They are not a 02B
dependency, and the audit does not rely on them.

## 6. Non-claims

This audit does **not** establish:

- that the Chapter Improvement workflow can currently run on Distillation;
- that any proposal improves chapter 14;
- that the economy score is a verified fact or that a re-run would reproduce it;
- that an experience item improves a later proposal;
- that MEMORY-03 is callable or that its retrieval applies to chapter improvement;
- that technical, Writer or publication coverage exists for this chapter;
- that a scripted/fixture test is real-model evidence.

It establishes the reusable capability boundaries, the live blocker, the exact chapter/quality
evidence and the narrow conditions under which 02B can produce a real proposal and decision.

## 7. Reproduce

```powershell
# Read-only live summary (no model, no workflow launch)
pwsh -NoProfile -File docs\acceptance\mc-living-book-02a\live-probe.ps1

# Focused tests
cd C:\Projects\alive
uv run pytest -q tests/test_living_book.py -o addopts=""

cd C:\Projects\mission
.\.venv\Scripts\python.exe -m pytest -q backend\tests\test_living_book.py
```

The probe is intentionally read-only from the caller’s perspective. It can still cause ALIVE’s existing
live-binding reconciliation to refresh `last_refresh_at`; it does not call `POST /refresh`, does not
launch a workflow and does not call a model.

**Post-audit activation:** 02B created and activated the immutable v7/901–906 family after the real run
exposed the old 100,000-token ceiling. The v6/801–806 family described above is historical. See
[the 02B acceptance record](../mc-living-book-02b/README.md).
