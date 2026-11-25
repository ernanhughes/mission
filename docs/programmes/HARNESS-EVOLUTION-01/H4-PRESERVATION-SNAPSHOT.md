# H4 preservation snapshot

Captured before H4 implementation on 2026-11-24. Recheck before H4 closes. Repositories were not cleaned, reset, stashed, or committed.

| Repository | HEAD | Branch | Initial tree state / known concurrent work |
|---|---|---|---|
| `C:\Projects\mission` | `fd11db64a45f7d2c881c350d85a9ea45ff61be32` | `main` | Dirty: Mission Work Outcome WIP (API modules, `work_observation`, migrations 041–050, tests and frontend); publication/book UI and docs; `.aitest`, `pub06`, `pyproject.toml.aitest-bak`. H4 edits are confined to `docs/programmes/HARNESS-EVOLUTION-01/`. |
| `C:\Projects\worker` | `a2e881c810c388fa2ce286a0b5169d4c93e791c5` | `main` | Dirty H3/H3Q changes in Worker core, model executor/provider/runtime/request/server and focused tests, plus untracked execution ledger/summary. H4 edits are limited to explicit strategy support, the named local route, focused tests and docs in H4 program evidence. |
| `C:\Projects\writer` | `8e23bdead5dcd110898d775c1d2041bb527f9fc1` | `main` | Dirty CLI/publication analysis work, deleted local configs and added tests/fixtures. H4 is read-only in Writer. |
| `C:\Projects\praxis` | `9cbc59038d38bc37d1093c4f236497fdb3f22715` | `main` | Dirty `pyproject.toml`, `.aitest`, backup. H4 is read-only in Praxis. |
| `C:\Projects\ai` | `a8c4199d93d2a20c92af05df0d7662edb60a1b87` | `main` | Dirty before H4. H4 is read-only in AI. |
| `C:\Projects\workbench` | `dd0c440bcedb6046c79e04ef06a472c8b96c66fb` | `main` | Dirty before H4. H4 is read-only in Workbench. |
| `C:\books\harness` | `66d0485bfe05b6a647704747a18ef442e2319c42` | `main` | Dirty before H4. No manuscript changes in H4. |

No production DB, running service, user project, book, or adjacent repository was modified during the snapshot. No H5, deployment, migration, commit, or push work is authorized.

## H4 exit check — 2026-11-25

HEADs and branches remain unchanged from the pre-H4 snapshot above. Mission edits are confined to this programme's H4 reports, frozen local task/evaluator, run-local request/result/ledger artifacts, and post-run verifier. Worker edits are confined to H4 strategy composition, the named local comparison/reviewer routes, strategy-aware H3 evidence, and focused tests, alongside pre-existing dirty H3/H3Q work. Writer, Praxis, AI, Workbench, and the Harness book received no H4 writes. No operational Mission database was accessed and no service was restarted.

The three Worker comparison invocations briefly appended three usage rows and four call rows to the default Worker ledgers. Those exact seven rows were removed by their H4 request IDs under exclusive file handles; all other records were preserved byte-for-byte. The isolated H3 execution artifacts remain under `h4-fixtures/live-local/runs/`. The failed Mistral reviewer invocation used the isolated H3 ledger and had Worker usage/call/evidence ledgers disabled.

