# WRT-EDIT-02A — Engineering health and integrity evidence

Date: 2026-10-25

## Repository state at task start

| Repository | Branch | HEAD | State |
| --- | --- | --- | --- |
| Writer | `main` | `ea34f68b3` | clean, synced with `origin/main` |
| Mission Control | `main` | `2900c31` | clean, synced with `origin/main` |
| Language | `main` | `c7e7953` | clean; read-only |

No pre-existing uncommitted code changes were present. WRT-EDIT-02A added only
untracked analysis/evidence paths; no implementation or threshold changes were
made.

## Registry integrity

| Check | Result |
| --- | --- |
| Registry path | `C:\Projects\writer\config\web\projects.yaml` |
| SHA-256 | `0B8FD97816E1A42E48EF356777111F3B6416360E654F9A8F8F2BAF932FCBB886` |
| Last write | `2026-10-15T23:23:51Z` |
| Git state | clean |
| Active projects | 29 |
| Registered content paths under `C:\books` | **0** |
| Editing-eligible books | 7 |
| Editing-eligible chapters | 222 |
| Blocked | 21 |
| No manuscript | 1 |

The relocation premise failed. Details:
[WRT-EDIT-02A-REGISTRY-AUDIT.md](WRT-EDIT-02A-REGISTRY-AUDIT.md).

## Tests

### Writer

| Check | Result | Evidence |
| --- | --- | --- |
| Focused Editing tests | **17 passed** | `engineering-health/writer-editing-tests.txt` |
| Focused Ruff | passed | `engineering-health/writer-editing-ruff.txt` |
| Docs architecture + CLI coverage | **17 passed, 2 failed** | `engineering-health/writer-docs-tests.txt` |
| Full Writer suite | **collection blocked** | `engineering-health/writer-full-tests.txt` |

Pre-existing failures, unchanged:

- `test_every_genuine_domain_has_docs_dir` and
  `test_every_genuine_domain_has_skill_or_justified_gap`: `metadata_generation`
  has no runtime docs dir/SKILL.
- Full-suite collection stops on
  `tests/runtime/domains/test_mri_semantic_adjudication.py:493` with an
  `IndentationError`.

### Mission Control

| Check | Result | Evidence |
| --- | --- | --- |
| Writer adapter/API tests | **5 passed** | `engineering-health/mission-writer-integration-tests.txt` |
| Full backend | **63 passed** | `engineering-health/mission-backend-tests.txt` |
| Frontend | **29 passed** | `engineering-health/mission-frontend-tests.txt` |
| Production build | passed | `engineering-health/mission-frontend-build.txt` |

## Live Mission Control refresh and view

`POST /api/writer/refresh` returned:

```text
available=true
29 registered books
7 with manuscript
7 audited
7 needs review
21 blocked
1 no manuscript
0 stale
0 not run
```

A real Chrome check of `http://127.0.0.1:8790/writer` found:

- 29 book rows;
- cross-book queue present;
- explicit `NEEDS_REVIEW` and `BLOCKED` states present;
- 0 console errors;
- 0 page errors.

Evidence: `browser-check.json`, `writer-live-after-audit.png`.

## Manuscript integrity

The audit was read-only. Registered accessible source trees were hashed before
and after the final whole-suite audit:

| Tree | Files | SHA-256 before/after |
| --- | ---: | --- |
| Language book | 39 | `e17a5a301ed412da9061245fb73d955f3ec3c8820f8cc3658cf6829df32ebaeb` |
| Programmer.ie books | 656 | `e2c2706f92917ae5b5f63715362274f5cb288c160c7e241fa86d0c7775c3dd80` |

Both digests were **identical** before and after. No manuscript was changed.

`C:\books` was inventoried read-only but was not an audit source: no registered
path points there. The inventory scan hit one broken/inaccessible nested path;
that path was not followed or repaired.

## Findings relevant to engineering health

- The Writer runtime and Mission Control adapter remain functional.
- The audit is deterministic in coverage and findings: three full audits produced
  the same 7 books / 222 chapters / 613 findings; source trees were unchanged.
- Current measured coverage is unchanged from MC-WRITER-01.
- The biggest risk to a trustworthy baseline is not test failure but **wrong
  scope**: the full collection lives under `C:\books`, while Writer audits
  `C:\Projects`.

## Recommended next action

1. Apply an explicit, reviewed registry relocation with exact
   `project_root` / `content_dir` / `repo.local_path` mappings.
2. Re-run `writer editing audit --all --json` and compare coverage.
3. Only then begin WRT-EDIT-02B calibration against the 44-passage sample.

No commit or push was made in WRT-EDIT-02A.
