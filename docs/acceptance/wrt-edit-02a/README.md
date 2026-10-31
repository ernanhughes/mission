# WRT-EDIT-02A evidence

Status: **full audit completed.** The saved registry resolves 28 of 29 active
projects to manuscript content; 0 configured content directories are missing.
One project (`writer`) has no manuscript, and one manuscript (`digital-life`) is
registered twice (`programmer_ie` is the duplicate).

All report IDs in `audit-all.json`, `cross-book-analysis.json`,
`chapter-baseline.csv`, `finding-index.csv`, `high-risk-chapters.csv` and
`mission-writer-workspace.json` refer to the same final audit run
(2026-10-25T01:33–01:34Z).

## Coverage

| Metric | Registered entries | Distinct manuscripts |
| --- | ---: | ---: |
| Books | 28 | 27 |
| Chapters | 818 | 799 |
| Findings | 2,319 | 2,271 |
| High | 609 | 598 |
| Medium | 1,084 | 1,071 |
| Low | 598 | 575 |
| Info | 28 | 27 |
| High/medium | 1,693 | 1,669 |

Coverage change: **7 audited / 21 blocked / 1 no manuscript** →
**28 audited / 0 blocked / 1 no manuscript**. The 21 newly accessible projects
add 596 chapters and 1,706 findings.

## Registry

- Registry SHA-256: `21F40F876494286F485DD6DC3664B0B1DD1CEC0F75F9A452814B38E3EF3B2E10`
- Last write: `2026-10-25T01:30:57Z`
- Git state: `M config/web/projects.yaml` — preserved user change
- 21 projects under `C:\books`; 7 accessible projects still under `C:\Projects`
- 0 missing configured content directories

## Deliverables

Writer-owned analysis documents:

- `C:\Projects\writer\docs\analysis\WRT-EDIT-02A-REGISTRY-AUDIT.md`
- `C:\Projects\writer\docs\analysis\WRT-EDIT-02A-CROSS-BOOK-BASELINE.md`
- `C:\Projects\writer\docs\analysis\WRT-EDIT-02A-CALIBRATION-SAMPLE.md`
- `C:\Projects\writer\docs\analysis\WRT-EDIT-02A-ENGINEERING-HEALTH.md`

## Raw evidence

| File | Contents |
| --- | --- |
| `registry-audit.json` | All 29 active projects, paths, existence, chapters, status |
| `registry-change.diff` | Saved registry diff, preserved verbatim |
| `mission-runner.diff` | Mission Control 5 MB → 32 MB stdout-capture compatibility fix |
| `duplicate-content.json` | Digital Life duplicate chapter hashes and overlap |
| `c-books-inventory.json` | Read-only inventory of `C:\books` top-level directories |
| `summary-before.json` | Writer summary before the final audit |
| `audit-all.json` | Full Writer audit result and report IDs |
| `summary-after.json` | Writer summary after the final audit |
| `report-fingerprints.csv` | Per-book report IDs, canonical fingerprints, source revisions and dirty flags |
| `cross-book-analysis.json` | Rule counts, dimensions, genre split, duplicates, high-risk chapters, artefacts |
| `chapter-baseline.csv` | All 818 registered chapters with scores, bands and finding codes |
| `finding-index.csv` | All 2,319 registered findings with code, severity and locator |
| `high-risk-chapters.csv` | Top three chapters per book by weighted severity |
| `calibration-passages.json` | 50 real passages with source metadata and chapter diagnostics |
| `calibration-blind-passages.csv` | Text-only packet for independent review |
| `calibration-review-template.csv` | 50 blank assessment rows |
| `calibration-integrity.json` | Passage/category/strata counts, file hashes and consistency checks |
| `manuscript-hashes-before.json` / `after.json` | 818 chapter files; identical aggregate hash |
| `mission-writer-workspace.json` | Mission Control Writer refresh state |
| `browser-check.json` | Chrome check of `/writer` |
| `writer-live-after-audit.png` | Current live Writer view |
| `evidence-manifest.json` | SHA-256 manifest of every file in this evidence directory |
| `engineering-health/` | Focused/full test outputs |
| `scripts/` | Reproducible hash, cross-book analysis, duplicate detection and sampling scripts |
| `previous-baseline/` | Snapshot of the earlier 7-book baseline and its analysis docs |

## Summary

- Registry relocation: **applied by the user and validated**.
- Coverage: **28 registered / 27 distinct books**, 818 / 799 chapters.
- Findings: **2,319 registered / 2,271 distinct**; 1,693 / 1,669 high/medium.
- Dominant signals: fragmentation (503 distinct), heading density (375),
  uniform cadence (360), trivial sections (339), long sentences (288),
  paragraph density (194), long sections (153).
- Genre split: 9 fiction / 18 technical distinct books. Fiction has 92.4%
  high/medium findings versus 63.2% for technical; this is confounded by
  short-paragraph and heading conventions and must be calibrated.
- Calibration sample: **50 passages**, 30 technical / 20 fiction, 24 high /
  14 medium / 12 low, 27 distinct books.
- No thresholds, parser rules or manuscripts were changed.
- Five sources had pre-existing uncommitted changes; they were preserved and the
  audit measured the working tree.
- No commit or push was made.

## Engineering notes

- Mission Control's tool runner was truncating captured stdout at 5 MB; the
  expanded Writer summary is 11.4 MB. The bounded limit is now 32 MB in
  `backend/mission_control/integrations/runner.py`.
- Writer Editing: 17 passed; Ruff passed.
- Mission Writer integration: 5 passed; backend: 63 passed; frontend: 29 passed;
  build passed.
- Pre-existing Writer failures remain: two `metadata_generation` docs/SKILL
  tests and a full-suite collection `IndentationError`.
- Live `/writer`: 29 rows, 28 audited, 28 needs review, 0 blocked, 1
  no-manuscript, 0 console/page errors.
