# WRT-EDIT-02A — Registry audit

Date: 2026-10-25

Status: **FAILED to validate the relocation premise.** Writer’s registry still
points at `C:\Projects\*`, not `C:\books\*`. No path was rewritten or guessed.

## Registry facts

| Item | Result |
| --- | --- |
| Registry | `C:\Projects\writer\config\web\projects.yaml` |
| Registry SHA-256 | `0B8FD97816E1A42E48EF356777111F3B6416360E654F9A8F8F2BAF932FCBB886` |
| Last write (UTC) | `2026-10-15T23:23:51Z` |
| Git state of registry at audit | clean; Writer HEAD `ea34f68b3` |
| Active registered projects | 29 |
| Configured content paths under `C:\books` | **0** |
| Editing-eligible books | **7** |
| Editing-eligible chapters | **222** |
| Blocked by absent configured content path | **21** |
| No manuscript | **1** (`writer`, a Python project) |
| `C:\books` top-level directories | 37 |
| `C:\books` Markdown count (read-only inventory) | 15,721 |
| `C:\books` scan errors | 1 broken/inaccessible nested path (ignored) |

The registry was not updated after the books were relocated. The only
`C:\books` evidence is the directory inventory; no Writer project references it.

## Project-by-project audit

`Chapters (edit)` means Markdown chapters that Editing v1 would accept:
Markdown extension, non-underscore control file, registry exclusion prefixes
applied. `BLOCKED` means the configured content directory does not exist.

| Project | Repository path | Content path | Exists | Chapters (edit) | Status | Reason |
| --- | --- | --- | --- | ---: | --- | --- |
| `language` | `C:\Projects\language` | `C:\Projects\language\content\books\language` | True | 38 | READY |  |
| `pi` | `C:\Projects\pi` | `C:\Projects\pi\content\books\pi` | False | 0 | BLOCKED | configured content_dir does not exist |
| `context` | `C:\Projects\context` | `C:\Projects\context\content\books\context` | False | 0 | BLOCKED | configured content_dir does not exist |
| `memory` | `C:\Projects\memory` | `C:\Projects\memory\content\books\memory` | False | 0 | BLOCKED | configured content_dir does not exist |
| `applied-ai` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\applied-ai` | False | 0 | BLOCKED | configured content_dir does not exist |
| `debugging-ai` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\debugging-ai` | False | 0 | BLOCKED | configured content_dir does not exist |
| `embeddings-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\embeddings-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `browser-ai-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\browser-ai-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `dspy-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\dspy-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `hallucination-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\hallucination-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `pytorch-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\pytorch-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `agents-from-first-principles` | `C:\Projects\new-books` | `C:\Projects\new-books\content\books\agents-from-first-principles` | False | 0 | BLOCKED | configured content_dir does not exist |
| `digital-life` | `C:\Projects\digital-life` | `C:\Projects\digital-life\content\books\digital-life` | False | 0 | BLOCKED | configured content_dir does not exist |
| `latent` | `C:\Projects\latent` | `C:\Projects\latent\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `coin` | `C:\Projects\coin` | `C:\Projects\coin\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `softwear` | `C:\Projects\softwear` | `C:\Projects\softwear\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `axiom_zero` | `C:\Projects\axiom-zero` | `C:\Projects\axiom-zero\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `becoming_alice` | `C:\Projects\becoming-alice` | `C:\Projects\becoming-alice\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `collapse` | `C:\Projects\collapse` | `C:\Projects\collapse\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `goblins` | `C:\Projects\goblins` | `C:\Projects\goblins\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `techno_prophet` | `C:\Projects\techno-prophet` | `C:\Projects\techno-prophet\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `programmer_ie` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\digital-life` | True | 19 | READY |  |
| `writer` | `C:\Projects\writer` | `C:\Projects\writer` | True | 0 | NO_MANUSCRIPT | no editing-eligible Markdown chapters; pattern is `*.py` |
| `projection` | `C:\Projects\projection` | `C:\Projects\projection\chapters` | False | 0 | BLOCKED | configured content_dir does not exist |
| `advanced-agents-from-first-principles` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\advanced-agents-from-first-principles` | True | 46 | READY |  |
| `agent-architectures` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\agent-architectures` | True | 16 | READY |  |
| `cellular-automata-from-first-principles` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\cellular-automata-from-first-principles` | True | 59 | READY |  |
| `freestyle-cognition` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\freestyle-cognition` | True | 32 | READY |  |
| `models-from-first-principles` | `C:\Projects\programmer.ie` | `C:\Projects\programmer.ie\content\books\models-from-first-principles` | True | 12 | READY |  |

## Stale path references

All 21 blocked projects have stale configured paths:

- `C:\Projects\new-books` — 8 projects
- `C:\Projects\pi` — 1
- `C:\Projects\context` — 1
- `C:\Projects\memory` — 1
- `C:\Projects\digital-life` — 1
- `C:\Projects\latent` — 1
- `C:\Projects\coin` — 1
- `C:\Projects\softwear` — 1
- `C:\Projects\axiom-zero` — 1
- `C:\Projects\becoming-alice` — 1
- `C:\Projects\collapse` — 1
- `C:\Projects\goblins` — 1
- `C:\Projects\techno-prophet` — 1
- `C:\Projects\projection` — 1

`C:\books` contains book-like directories and a substantial `new-books` tree,
but **no registry entry points into it**. Candidate relocation is therefore
unverified. Mapping `C:\Projects\...` to `C:\books\...` must be an explicit,
reviewed registry change; WRT-EDIT-02A does not infer it.

## Effect on the audit

The full-library objective was not achieved. The actual coverage is identical
to the previous baseline:

```text
before: 7 audited, 21 blocked, 1 no manuscript
after:  7 audited, 21 blocked, 1 no manuscript
```

The 7 accessible books and 222 chapters were audited read-only. They are the
registered `C:\Projects` copies, not confirmed copies under `C:\books`; the two
locations were not compared. Their results are in
[WRT-EDIT-02A-CROSS-BOOK-BASELINE.md](WRT-EDIT-02A-CROSS-BOOK-BASELINE.md).

## Recommendation

**Do not calibrate against the relocated collection yet.** First perform a
separate, explicit registry-relocation change with a reviewed mapping and then
rerun `writer editing audit --all`. Until then, any cross-book conclusion applies
only to the seven projects still reachable under `C:\Projects`.

## Evidence

Raw evidence is under
`C:\Projects\mission\docs\acceptance\wrt-edit-02a\`:

- `registry-audit.json`
- `c-books-inventory.json`
- `summary-before.json`
- `audit-all.json`
- `summary-after.json`
- `manuscript-hashes-before.json`
- `manuscript-hashes-after.json`
