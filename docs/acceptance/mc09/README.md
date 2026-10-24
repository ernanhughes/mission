# MC09 browser and runtime evidence

This directory contains evidence generated against the live Mission Control
service at `http://127.0.0.1:8790` on 2026-10-24. It is not fixture data.

## Machine-readable

| File | Contents |
| --- | --- |
| `browser-e2e.json` | 17-step Chrome acceptance run, timings, screenshots, console/page error counts and security rejection results |
| `security-check.json` | Browser-originated invalid action attempts and execution counts before/after |
| `runtime-state.json` | Live integration configs, counts, inbox/search breakdowns, decisions, executions, migrations and CoCoder artifacts |
| `source-repositories.txt` | Read-only source repository state before/after, confirming no MC09 writes |

The `browser-e2e.json` file records four expected 422/409 console network
messages caused by the deliberate security tests. They are separated into
`expected_console_errors`; `console_errors` is empty.

## Screenshots

| File | Scenario |
| --- | --- |
| `01-next-overview.png` | Live Next workspace, 130 opportunities |
| `01b-next-candidates.png` | Searchable candidate list |
| `02-next-detail-local-decision.png` | Real candidate evidence + local Defer + Math association |
| `03-work-opportunity-detail.png` | Qualified Work opportunity + local shortlist + Math |
| `03b-work-local-decision.png` | Work Investigate decision recorded through the browser |
| `04-cocoder-finding-detail.png` | Real high CoCoder finding, repository/range/evidence |
| `04b-cocoder-local-decision.png` | CoCoder Investigate decision recorded through the browser |
| `05-cocoder-operations.png` | Registered review action and durable execution history |
| `06-unified-inbox.png` | Full unified inbox (45 items) |
| `06b-inbox-cocoder-filter.png` | Inbox filtered to CoCoder |
| `06c-inbox-viewport.png` | Readable first viewport of the inbox |
| `07-search-cross-source.png` | Full federated search results |
| `07b-search-viewport.png` | Cross-source search for `agent` |
| `08-command-palette-search.png` | `Ctrl+K` palette searching CoCoder findings |
| `09-project-shared-context.png` | Math project with Next + Work context |
| `10-integrations.png` | Connected integrations, diagnostics and actions |

## Reproduction

The browser run used Google Chrome through a temporary `puppeteer-core`
installation. The acceptance logic and assertions are described in
[../MC09-REPORT.md](../MC09-REPORT.md). Runtime configuration names (not values)
were `NEXT_DSN` and `WORK_DATABASE_URL`.

The production pages contain no illustrative fixture data. Fixtures are used only
by the automated unit/component suites.
