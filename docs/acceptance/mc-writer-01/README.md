# MC-WRITER-01 evidence

Generated 2026-10-24 against the real Writer Editing runtime and a live Mission
Control server. The acceptance server used a separate synthetic registry
(`acceptance-registry.yaml`) containing the real `language` project plus three
fixtures. No production manuscript was modified.

## Browser run

`browser-e2e.json` records 8 passed steps:

1. four Writer books visible;
2. fragmented fixture finding;
3. dense fixture paragraph-load finding;
4. uniform-cadence fixture finding;
5. Language chapter table with all six subdimensions;
6. `STALE` after the fragmented fixture fingerprint changed;
7. restored fixture returns to current;
8. Language manuscript tree hash unchanged.

Browser console errors: **0**. Page errors: **0**.

Screenshots:

| File | Scenario |
| --- | --- |
| `01-writer-books.png` | Queue, book table, pipeline states, selected book |
| `02-fragmented-fixture.png` | Fragmentation finding and raw metrics |
| `03-dense-fixture.png` | Paragraph density and long-sentence findings |
| `04-uniform-fixture.png` | Uniform-cadence finding; independent scores |
| `05-language-chapters.png` | Language chapter table and drill-down |
| `06-stale-fixture.png` | `STALE` plus source-fingerprint detail |
| `07-live-writer-real.png` | Final live `8790/writer` against the real Writer registry |

## Machine-readable evidence

| File | Contents |
| --- | --- |
| `writer-audit-all.json` | Writer CLI audit summary for the acceptance registry |
| `writer-language-chapter-03.json` | One-chapter read-only report |
| `writer-fingerprint-recheck.json` | Repeated audit, identical canonical fingerprint |
| `writer-report-retrieval.json` | Stored report retrieval and current status |
| `writer-live-execution.json` | Durable Mission Control audit execution `exec-42b9...` |
| `runtime-state.json` | Live/acceptance workspace summaries and source repository state |
| `source-repositories.txt` | Source repository dirty-state preservation |
| `browser-e2e.json` | Full browser trace and before/after hashes |

## Test outputs

- `writer-focused-tests.txt`
- `writer-focused-ruff.txt`
- `writer-docs-cli-tests.txt` (2 pre-existing docs failures)
- `writer-full-tests.txt` (collection blocked by a pre-existing test syntax error)
- `mission-backend-tests.txt`
- `mission-frontend-tests.txt`
- `mission-frontend-build.txt`
- `mission-ruff.txt`

## Reproduction

```powershell
# Writer
cd C:\Projects\writer
venv\Scripts\writer.exe editing audit --all --json

# Mission Control
cd C:\Projects\mission
.\scripts\start.ps1
# http://127.0.0.1:8790/writer
```

The acceptance server was on `127.0.0.1:8791` with
`WRITER_PROJECTS_CONFIG=C:\Projects\mission\docs\acceptance\mc-writer-01\acceptance-registry.yaml`
and a separate Mission Control data directory. It was stopped after the run.

The fixture files are synthetic. The real Language project was audited read-only.
