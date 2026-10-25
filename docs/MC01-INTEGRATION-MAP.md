# MC01 — Integration map

This map distinguishes what was **verified**, what is **inferred**, what is **not yet available**, and what is **blocked**. No command or API below is invented; each verified item points to documentation or code observed in the target repository.

## Summary

| System | Verified capability | Mission Control use | State |
| --- | --- | --- | --- |
| Next | Local SQLite database and opportunity tables; CLI; PostgreSQL option | Read-only snapshot observations | Verified (local snapshot), no recommendations auto-created |
| CoCoder | JSON review artifact with findings and evidence | Findings + high-severity review suggestions | Requires a configured artifact path |
| Work | PostgreSQL CLI/web dashboard | No records imported | Blocked: no verified read-only export configured |
| Writer | CLI, Editing runtime, versioned reports | Editing summary, book/chapter evidence, approved read-only audit | Integrated in MC-WRITER-01 (read-only) |
| Improve | Repository, tests, docs | Repository access | Not integrated |
| BookBuilder | `bookbuilder build --config` CLI | Disabled build template | Verified CLI shape, not enabled for a book |
| Worker | `/health` and `/v1/work` HTTP API | Health-only adapter | Verified health, not running; no work submitted |
| Stephanie | Python research runtime, Postgres/pgvector | Repository access | Not integrated |
| Workbench | FastAPI editing workbench | Repository/documentation access | Not integrated |
| Language book | Manuscript tree and planning status | Chapter/status observation | Verified |
| Inference book | 45 chapter files and README claim | Manuscript/status observation | Verified file observation; README is an external claim |
| Math book | MATH01 JSON report v1 | Claim assessments, tools, obligations | Verified artifact reading |
| Git | `git status`, `rev-parse`, `log` | Repository observation | Verified, read-only |

## Next

**Verified**
- `pyproject.toml` exposes a `next` console script and describes a "Level-Up Discovery Engine for Applied AI".
- `docs/DATABASE.md` documents SQLite (`data/next.db`) and PostgreSQL via `NEXT_DSN`.
- Local SQLite tables include `opportunities`, `decisions`, `items`, `sources`, `experiments` and others.
- Local snapshot observed 37 opportunities: 29 in the validated queue and 8 in the frontier queue.

**Inferred**
- PostgreSQL is the active store on this machine because `NEXT_DSN` is present. Mission Control cannot see its contents without explicit credentials and does not inspect it.
- A future stable export or read-only HTTP endpoint would be preferable to database reading.

**Not available / blocked**
- There is no verified JSON export command for recommendations.
- The local SQLite file may lag the PostgreSQL store.
- No Next recommendation is converted into work automatically.

**Implemented adapter**
- Reads up to 8 opportunity rows read-only from the configured SQLite file.
- Marks each as `external_claim` and states that the snapshot is not confirmed or production data.
- Never creates a coding task or changes an outcome.

## CoCoder

**Verified**
- The CLI supports `cocoder review --base main --head HEAD --format json --output FILE`.
- The review model has `schema_version`, `changed_files`, `symbols`, `evidence`, `findings`, `unknowns`, `analysis_limitations` and detector failure counts.
- Findings have `rule_code`, `category`, `title`, `statement`, `claim_type`, `severity`, `confidence`, evidence IDs and unknowns.

**Inferred**
- The team may already produce review artifacts outside the repository; Mission Control does not assume a location.

**Not available / blocked**
- No artifact was configured at acceptance time, so the adapter correctly reports unavailable.
- There is no persistent HTTP service verified for review queries.

**Implemented adapter**
- Requires `review_json_path` inside the CoCoder repository.
- Reads a review artifact read-only and surfaces the summary and findings with evidence.
- High-severity findings become pending review suggestions with `derived_observation` provenance. They do not become code work.
- A malformed or unsafe path fails in isolation with diagnostics.

## Work

**Verified**
- README documents a local-first commercial opportunity engine, PostgreSQL-only storage (`WORK_DATABASE_URL`), a substantial CLI and a local web dashboard on port 8765.
- Commands include `work opportunities`, `work shortlist`, `work report`, and JSON output options for some commands.
- The repository was clean of assumptions: no database was connected.

**Blocked**
- Work requires a live PostgreSQL database and credentials. Mission Control did not modify or inspect it.
- No verified machine-readable export contract was configured. The adapter therefore reports the block and displays **no** opportunities, readiness states or income. No hypothetical records are shown.

**Proposed future change (not implemented)**
- Add a supported read-only `work export --format json` contract or a documented local HTTP endpoint. Mission Control can then consume it with source attribution. This change belongs in Work and requires the owner's approval.

## Writer and Improve

**Verified Writer**
- Monorepo runtime + CLI (`writer <command>`), 28 top-level commands, writer-web server on 127.0.0.1:8010, contract and skill documentation.
- Working tree was already dirty; Mission Control did not run Writer tests or write anything.

**MC-WRITER-01 update**
- Writer now exposes `runtime.editing` and `writer editing summary|audit|... --json`
  plus `writer-editing-report-v1`. Mission Control consumes the CLI contract and
  does not parse manuscripts or calculate scores.
- The approved `audit_registered_books` action runs Writer's read-only audit and
  writes only Writer-owned `.writer/editing` artifacts.
- `NOT_RUN`/`CURRENT`/`STALE`/`PARTIAL`/`ERROR` are preserved; Metadata, MRI and
  Strengthen are explicitly `NOT_TRACKED` by Editing v1.
- See `docs/MC-WRITER-01-WRITER-INTEGRATION.md` and
  `docs/acceptance/MC-WRITER-01-REPORT.md`.

**Verified Improve**
- Repository with CLI/package and documentation. No stable status endpoint was established.

**Not available**
- No adapter. Repository/documentation access only.

## BookBuilder

**Verified**
- CLI command: `bookbuilder build --config PATH`.
- It builds EPUB (and optional PDF) by creating intermediate files and invoking Pandoc.
- The website/manuscript remains the source of truth; outputs are generated.

**Not available / policy**
- Each book requires its own verified working directory and `bookbuilder.toml`.
- Running a build can overwrite publishing artifacts, so the shipped definition is disabled and requires confirmation if enabled.
- No build was run during acceptance.

## Worker

**Verified**
- Documented health endpoint at `GET http://127.0.0.1:7317/health`.
- Work submission endpoint `POST /v1/work`.
- `worker health`/`worker serve` CLI exist; Bun is the runtime.

**Implemented adapter**
- Calls only `/health`, with a 2-second timeout.
- Does not submit work, execute code, or spend model tokens.
- At acceptance Worker was not listening, so the adapter reports unavailable with no invented status.

**Not enabled**
- The server launch definition remains disabled because starting Worker can execute model work and may incur cost. The user must verify and enable it deliberately.

## Stephanie

**Verified**
- Python research system, DSPy, Ollama/pgvector, Gradio/web-search dependencies, documented architecture.

**Not available**
- No stable local HTTP/CLI integration contract was established during inspection.
- No adapter, no launch, no database access.

## Workbench

**Verified**
- FastAPI app with chapter, settings, conversation, Writer-status and sidecar bridge endpoints; demo server port 7431; explicit human-owned context and apply/undo contract.

**Not integrated**
- It is registered as a supporting application with documentation links, but no launch definition or adapter. The demo server was not started.

## Books

### Language

**Verified**
- `content/books/language` contains a 37-chapter Hugo manuscript; `planning/STATUS.md` describes the editorial baseline, five author-review checkpoints and publication decision.
- `project-language` is the separate runnable companion repository, not a duplicate manuscript.
- Adapter reads chapter count and status heading/date. It does not infer completion or quality.

### Inference

**Verified**
- `C:\books\inference` contains 45 numbered chapter files under `content/books/inference`.
- README contains a dated status claim: chapters 01–28 starter manuscripts; 29–45 prompt-only; no chapter marked verified.
- Adapter exposes the chapter count and the README claim as `external_claim`, not as Mission Control verification.

### Math

**Verified**
- `artifacts/math01/report.json` has `schema_version = math-investigation-report-v1`, 4 claim assessments and 10 results.
- Lean 4 and Rocq kernel checks recorded; SymPy and Z3 computational checks; Isabelle/Sage not installed and explicitly not evaluated.
- `docs/research/MATH01-status.md` states what did not run and what remains open.
- Adapter surfaces assessments and unresolved obligations as evidence, with derived review suggestions. It does not alter book status.

## Generic repository observation

- `git status --porcelain=v1 --untracked-files=no --branch`
- `git rev-parse HEAD`
- `git log -1 --format=%cI`

No fetch, pull, reset, checkout, clean or write operation is issued. Git CLI output is bounded with timeouts and run with `shell=False`.

## Integration boundaries

- Mission Control does not import target application code or share their databases.
- Adapters read documented artifacts or endpoints only.
- No adapter creates tasks or runs work automatically.
- Recommendations remain pending until a person accepts, defers or rejects them.
- Publishing, repository mutation, applications and model spending require explicit user action.
