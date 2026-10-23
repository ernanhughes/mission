# MC01 — Repository inventory and qualification

Verified: 23 October 2026, read-only, on the local Windows machine.

## Actual repository root

The expected path in the brief was `C:\Projects\mission-control`. That directory does not exist. The repository prepared for this project is:

```text
C:\Projects\mission
```

It was already a Git repository on branch `main`, containing `README.md`. Mission Control was implemented here. No second Git repository was created.

## Environment observed

| Tool | Observed |
| --- | --- |
| Python | 3.13.15 (`python`), with Python 3.11 also installed |
| Node.js | v25.8.2 |
| npm | 11.21.1 |
| Git | 2.48.1.windows.1 |
| uv | installed |
| Bun | installed |
| VS Code | installed as `code.cmd` and native `Code.exe` |
| Discovery roots | `C:\Projects`, `C:\books` |

The application uses Python 3.12+ APIs and was exercised on 3.13. The frontend was exercised on Node 25.

## Discovery result

A real read-only scan of both roots discovered **98 directory candidates** in 3.2–5.3 seconds depending on Git cache state:

| Classification | Count |
| --- | ---: |
| Book | 41 |
| Executable application | 14 |
| Library/package | 14 |
| Supporting repository | 12 |
| Research project | 8 |
| Unknown | 4 |
| Background service | 2 |
| Publishing site | 1 |
| Experiment | 1 |
| Generated artifact | 1 |

84 candidates were unlinked at the time of the last scan; 14 were already associated with registered applications or projects. Six top-level directories were excluded during the scan, plus generated directories encountered by name/pattern. Exclusions include `.git`, `node_modules`, virtual environments, caches, build output, review packs, bundles and smoke directories. The full counts are visible in Settings.

The classification is **advisory**. For example, many manuscript repositories mention a "book" in their README, so the book count is intentionally broad. Every candidate records its confidence and evidence. None of the 98 candidates was automatically given an application or launch command.

The canonical evidence snapshot is stored at [docs/acceptance/discovery-summary.json](acceptance/discovery-summary.json). Pre-existing dirty states are recorded in [docs/acceptance/PRE-EXISTING-REPO-STATES.md](acceptance/PRE-EXISTING-REPO-STATES.md).

## Priority books

| Book | Repositories | Evidence found | Relationship |
| --- | --- | --- | --- |
| **Language: When Intelligence Enters the Channel** | `C:\Projects\language`, `C:\Projects\project-language` | 37-chapter Hugo manuscript; `planning/STATUS.md` records a completed reader pass and five author-review checkpoints; `project-language` is the runnable companion | Manuscript and implementation are distinct; both linked to the Language project. The implementation is supporting evidence, not the book. |
| **Inference From First Principles** | `C:\books\inference` | README identifies a 45-chapter book and Inference Lab; `content/books/inference` contains 45 numbered chapter files; README publishes a dated status claim | Located outside `C:\Projects`; discovered only because `C:\books` is a configured root. |
| **Adversarial Mathematics From First Principles** | `C:\Projects\math`, `C:\Projects\math-r1` | `artifacts/math01/report.json` contains 4 claim assessments and 10 result records; Lean 4 and Rocq kernel checks, SymPy/Z3 computational checks, missing Isabelle/Sage recorded as not installed; `book/` planning files exist | `math-r1` is associated as a supporting experiment, not a duplicate application. MATH01 evidence is not manuscript completion and not physical confirmation. |

The three books are pinned with explicit display order: Language, Inference, Math. The user can reorder them.

## Core applications inspected

| Application | Observed contract | State |
| --- | --- | --- |
| **Next** | Python package `next` with a CLI; local SQLite `data/next.db`; `NEXT_DSN` environment present for PostgreSQL; 37 opportunities in the local snapshot (29 validated, 8 frontier); recent run artifacts | Application registered. Adapter reads the local SQLite snapshot read-only. No launch command enabled. No production PostgreSQL connection. |
| **CoCoder** | CLI entry point; `cocoder review --base ... --format json --output FILE`; documented review schema; no persistent HTTP API found; working tree already dirty (36 entries) on branch `cc-r06-p0-codeai-qualification` | Application registered. Adapter requires a configured review JSON artifact. No review artifact was configured during acceptance. |
| **Work** | Python CLI and local web dashboard; PostgreSQL required (`WORK_DATABASE_URL`); documented `--json` output for some commands; port 8765 | Application registered with a disabled, unverified launch definition. No verified read-only opportunity export was configured, so the Work adapter is blocked rather than inventing opportunities. |
| **Writer** | Python monorepo with CLI runtimes, writer-web on port 8010, skills/prompts; working tree dirty (3 entries) | Repository/documentation access only. No adapter or launch command enabled. |
| **Improve** | Python CLI/package; no machine-readable status endpoint established in the inspection | Repository access only. No adapter. |
| **BookBuilder** | Verified CLI shape: `bookbuilder build --config PATH`; generates EPUB/PDF via Pandoc | Disabled definition only. Publishing artifacts can be overwritten, so no build action is enabled by default. |
| **Worker** | HTTP health endpoint at `http://127.0.0.1:7317/health`; `POST /v1/work`; Bun runtime; working tree dirty (33 entries) | Health-only adapter; not running during acceptance. No work submission and no launch (cost/execution risk). |
| **Stephanie** | Python research system using DSPy, Ollama, PostgreSQL/pgvector; no verified stable local HTTP contract found | Repository access only. No adapter. |
| **Workbench** | FastAPI app, local editing/workbench API, demo port 7431; existing contract docs | Repository/documentation access only. Not launched automatically. |

Additional projects not pinned remain discoverable. Examples include `sidecar`, `youtube-videos`, `zeromodel`, `programmer.ie`, `tmy`, `HybridAgent`, `clipper-ai`, and many book/research directories. Discovery shows them; they do not become first-class applications automatically.

## Existing integration capabilities found

- **Git**: read-only branch, HEAD, last commit date and tracked status are available in every repository.
- **Next**: local SQLite tables including `opportunities`, `decisions` and `items`. The local snapshot is explicitly not assumed to be the active PostgreSQL store.
- **CoCoder**: documented JSON review schema (`schema_version`, `changed_files`, `findings`, `evidence`, `unknowns`) and Markdown/JSON output flags.
- **Math**: schema-versioned `math-investigation-report-v1` JSON with assessments, capabilities, results, limitations and unresolved obligations.
- **Language**: 37 chapter source files; `planning/STATUS.md`; Hugo manuscript tree; `project-language` package scripts.
- **Inference**: 45 numbered chapter files; README status claim; no stable machine-readable status object was found.
- **Worker**: documented `/health`; no health call was made to submit work.
- **Writer**: CLI and web runtime; no adapter contract was assumed.
- **Work**: PostgreSQL-backed CLI and web dashboard; no verified import contract configured.

## Exclusions and generated directories

The default scanner excludes, among others:

```text
.git, .hg, .svn, node_modules, .venv, venv, __pycache__,
.pytest_cache, .ruff_cache, .mypy_cache, .next, dist, build,
coverage, *.egg-info, *-review-pack, *-review-pack-v3,
*-bundles, p1-runs, worker-smoke, *.tmp, *.log
```

The scanner also refuses to follow symlinks/junctions, records inaccessible directories, bounds depth (default 1), caps candidate count (default 500) and supports cancellation. A repository root is not traversed further for nested worktrees.

## Repositories not modified

Mission Control did not write to any inspected repository. Tests and acceptance used temporary directories for fixture repositories; integration targets were read with Git status/log commands only. The snapshot in `PRE-EXISTING-REPO-STATES.md` lists dirty states that already existed.
