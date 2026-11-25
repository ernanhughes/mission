# Preservation snapshot

Captured before H0/H1 source inspection on 2026-11-24. All entries below were read-only Git queries. Every reported modified/deleted/untracked state was **unstaged**; no staged entries were observed. Git required a per-command `safe.directory` override for repositories owned by the interactive user; no persistent Git config was changed.

## Repository heads

| Repository | Branch | HEAD |
|---|---|---|
| `C:\Projects\mission` | main | `a6a358a0181b03dc868b76686356057cb1114f68` |
| `C:\Projects\worker` | main | `2bb8a8dcb6aaba2e36ec1c94618e3b7bab1640e0` |
| `C:\Projects\writer` | main | `aaeb66e1c8ebf83ab005dfa2ee50b00b2fa8d4f3` |
| `C:\Projects\workbench` | main | `dd0c440bcedb6046c79e04ef06a472c8b96c66fb` |
| `C:\Projects\praxis` | main | `9cbc59038d38bc37d1093c4f236497fdb3f22715` |
| `C:\Projects\stephanie` | main | `0ada120a5e0a393ca94a127af94c031332c58a78` |
| `C:\Projects\ai` | main | `a8c4199d93d2a20c92af05df0d7662edb60a1b87` |
| `C:\Projects\inspect` | main | `af123189b29a78059f564bedd149f65f5dc96c5d` |
| `C:\Projects\next` | main | `d8208b0a8e0648c576f8128d55f9d1942950d867` |
| `C:\Projects\work` | main | `853314316d3cb61379bc82d627e833a08c09918a` |
| `C:\Projects\cocoder` | main | `511d28c83ea1cc073b493600bf73d3e903b841b6` |
| `C:\Projects\alive` | main | `811230d46559ed7897d64621239e86b2c15bccb1` |
| `C:\Projects\aitest` | main | `dfffe2e021a9c759285e07fdf6ca4a6783fd56c7` |
| `C:\Projects\verity` | main | `2d2760acad8c0c574151c19b24dd84ec3a373967` |
| `C:\Projects\evidence-repair` | main | `430a330ffe45bcf1c5c1fb2d6598435f439b0b62` |
| `C:\Projects\improve` | main | `717ce2b5f1fd0fc38e59c71305bdbcc9b4113727` |
| `C:\Projects\bookbuilder` | main | `4f482ca5819130a78e4dbc36f1f84088b662b858` |
| `C:\Projects\sidecar` | main | `b5b61e4524d8f0d6a31c72f221df45b83cae5715` |
| `C:\Projects\steward` | main | `5cfc9224ad34027757ab3907e4f19bee4d0314a3` |
| `C:\books\harness` | main | `66d0485bfe05b6a647704747a18ef442e2319c42` |

## Pre-existing unstaged work (preserved)

- **Mission:** modified `backend/mission_control/main.py`, `models.py`, `backend/tests/test_migrations_and_seed.py`, three `docs/programmes/publication/*` files, and `frontend/src/pages/ActivityPage.tsx`, `frontend/src/types/api.ts`; untracked `.aitest/`, `.inspect/`, `PROJECT-INTELLIGENCE.md`, Work Outcome APIs for episodes/evaluation/intent/observation, migrations 041–045 (SQLite/PostgreSQL pairs), `work_observation/`, Work Outcome tests, `frontend/src/features/work-evaluation/`, `docs/programmes/WORK-OUTCOME-01/`, and `pyproject.toml.aitest-bak`.
- **Worker:** untracked `.inspect/`, `PROJECT-INTELLIGENCE.md`.
- **Writer:** deleted `.cocoder/config.toml`, `.opencode/opencode.json`, and `.pi` agent/skill files; modified `.vscode/settings.json`, `README.md`, `docs/cli/INDEX.md`, `packages/writer-cli/writer_cli/main.py`; untracked `.aitest/`, `.inspect/`, `PROJECT-INTELLIGENCE.md`, four `docs/cli/*` directories, three new CLI command modules, ECK evidence/publication analysis modules, their tests/fixtures, and `pytest.ini.aitest-bak`.
- **Inspect:** modified `README.md`, `inspect_cli.py`; untracked `schemas/stamp.schema.json`, `tests/test_stamp.py`.
- **Alive:** modified `alive/living_book/quality_history.py`; untracked one integration report and three tests.
- **Aitest:** untracked `.inspect/`, `PROJECT-INTELLIGENCE.md`.
- **BookBuilder:** untracked `fine-tuning.toml`.
- **Harness book (`C:\books\harness`):** modified chapter files 01–06 and 10–30 where present, `_index.md`, chapter concepts across 03–30, and `metadata/01-chapter.yaml` through `30-chapter.yaml`; untracked research folders `HARNESS-BOOK-FIX-02/`, `FIX-03/`, `FIX-04/`, `HARNESS-BOOK-REVIEW-03/`, `REVIEW-03B/`, `REVIEW-04/`, and `HARNESS-BOOK-WRITE-06/`.
- **Clean at capture:** Workbench, Praxis, Stephanie, AI, Next, Work, CoCoder, Verity, Evidence Repair, Improve, Sidecar, and Steward.

No `C:\Projects\pi` or `C:\Projects\opencode-runtime` repository was present. `opencode-runtime`, Remembering and Relate are Worker workspace packages, not separate current checkouts. No commit, stash, reset, clean, checkout, install, test, migration, database write, model call, service launch, or manuscript edit was performed by H0/H1. Programme documentation under this directory is the only write.


## H2/H3 exit refresh (2026-11-24)

Repository HEADs remain unchanged from the capture above. No commit, stash, reset, clean, checkout, push, deployment, migration, model call, or manuscript edit was performed.

Authorized H3 changes are confined to this programme's `docs/programmes/HARNESS-EVOLUTION-01/` evidence and fixtures plus the following Worker source/test additions: `src/core/execution-summary.ts`, `src/core/execution-ledger.ts`, edits to `src/core/worker.ts`, `src/factory.ts`, `src/schema/request.ts`, `src/server/server.ts`, and `tests/execution-ledger.test.ts`. Worker pre-existing untracked `.inspect/` and `PROJECT-INTELLIGENCE.md` remain untouched.

Mission Work Outcome and publication WIP listed in the original snapshot remains pre-existing and untouched by implementation; the only Mission additions are under this programme directory. Praxis' pre-existing modified `pyproject.toml` and untracked `pyproject.toml.aitest-bak` remain untouched. Writer, Inspect, and Harness book work listed above was not edited.

## H4/H5 preservation refresh (2026-11-25)

The programme worked only in `C:\Projects\mission\docs\programmes\HARNESS-EVOLUTION-01\`; Worker changes are the explicitly authorized strategy/runtime/ledger/config/tests and related H3 evidence sources. No Mission operational data or service was changed. No commit, stash, reset, clean, migration, deployment, or manuscript edit occurred.

Observed repository HEADs at this checkpoint: Mission `fd11db64...`, Worker `a2e881c...`, Writer `8e23bdead...`, Praxis `9cbc590...`, AI `a8c4199...`, Workbench `dd0c440...`; `C:\Projects\hugo-bookkit` at `c64dcc...` was clean. These repositories contain substantial pre-existing dirty/untracked work; the programme did not clean, stage, or commit it. Final git status remains available in the shared worktrees. H4Q qualification source identity was captured immediately before H5 Worker edits and is intentionally historical relative to the final Worker tree.

## H6 exit refresh (2026-11-25)

Repository heads remained Mission `9d6d2c55e826be7d1a439eec4d99c5ba283c43ce` and Worker `a2e881c810c388fa2ce286a0b5169d4c93e791c5`. No branch/HEAD changes, stage operations, commit, push, cleanup, reset, operational database access, migration, deployment, or manuscript edit occurred. The H6 implementation remains uncommitted in the shared worktrees. Worker strategy work under `src/strategies/` is untracked within the H4/H5 working tree; H6 adds only a descriptive catalogue projection there, with strategy digest stability verified in source/tests.

H6 Mission files are the new Harness adapter/test and frontend feature/test plus changes to `backend/mission_control/config.py`, `backend/mission_control/main.py`, `frontend/src/app/App.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/features/project/projectTabs.tsx`, `frontend/src/pages/ProjectPage.tsx`, `frontend/src/styles.css`, and the working-tree portion of `frontend/src/test/ProjectPage.test.tsx`. Programme docs and synthetic fixtures are under this directory. `ProjectPage.tsx` and several shared Mission files already contained concurrent work; H6 additions were layered without staging or resolving inherited index state.

At exit, Mission still reports inherited unmerged index entries for `backend/mission_control/models.py`, `backend/tests/test_migrations_and_seed.py`, and `frontend/src/test/ProjectPage.test.tsx` (`UU`). Mixed staged/unstaged (`MM`/`M `) and untracked Work Outcome, publication, AITest, and other concurrent work remains. Worker still has the pre-existing dirty H3/H4/H5 strategy/runtime/config/test set. No status entry was staged or reverted by H6. `npm ci --ignore-scripts` installed lockfile-pinned frontend dependencies into ignored `frontend/node_modules`; `package-lock.json` was not changed.

Key implementation hashes at this checkpoint:

| File | SHA-256 |
|---|---|
| `backend/mission_control/api/harness.py` | `F8CCAE4A15ED9934981C62E1DD3A9B0A881504DD453319CCF5E3ABB563BD1495` |
| `frontend/src/features/harness/HarnessPage.tsx` | `DE39D96F3AC012EDFB2B76C68F313E46E0B886AA6CA68D58BFECE51A86F82384` |
| `backend/tests/test_harness_api.py` | `444FA584A14C645F1EF0505508A30F64A8745164576C8303135CCC1FBA23D28E` |
| `frontend/src/test/HarnessPage.test.tsx` | `49FB6E14A3BAB8EBB8ECD9E1B2B51FE27279B790E975B266CB24DA602E8890D7` |
| `C:\Projects\worker\src\strategies\catalog.ts` | `2DC2B6AB7D1558666A08A16B26CD25A335D40C06464F91CC253C0BE6FDBC0A3F` |

Isolated run evidence is retained under `h6-fixtures/runs/`; successful run `e2e-20261125-b` uses only its own SQLite file and fixture ledgers. No live provider inference occurred. The isolated Mission/Worker processes are stopped at turn completion. Operational Mission port 8790 and Worker port 7317 were not restarted or modified.
