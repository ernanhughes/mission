# UI smoke evidence

Date: 23 October 2026

Environment: production frontend build served by Mission Control at `http://127.0.0.1:8790`, Chromium via the local browser harness and headless Chrome screenshots.

## Pages and data

| Page | Rendered data | Console errors |
| --- | --- | --- |
| Today | 3 priority books, Language focus, Math resume checkpoint, 4 pending review items, 9 applications, outcomes, activity | none |
| Books | 3 priority books with selection, editable state, milestones, paths, continuity and honest publishing limitation | none |
| Projects | Language, Inference, Math and discovered/unpinned projects; filters and controls | none |
| Math workspace | checkpoint, next action, 4 MATH01 recommendations, adapters, repositories and Git state | none |
| Applications | Next, CoCoder, Work, Writer, Improve, BookBuilder, Worker, Stephanie, Workbench with statuses and disabled-action reasons | none |
| Activity | persisted activity with provenance badges and filters | none |
| Settings | roots, exclusions, real discovery counts, candidates, editor/browser, process limits, AI, startup profile, retention | none |

Screenshots:

- `home.png`
- `books.png`
- `projects.png`
- `applications.png`
- `project-math.png`
- `settings.png`
- `activity.png`

## Interactions performed

1. **Priority reorder:** clicked “Move Math up” on Today, confirmed the toast and API order became Language, Math, Inference; clicked “Move Math down” to restore.
2. **Checkpoint through the UI:** on Math, entered summary, completed action, next action, blocker, milestone and evidence; saved. The checkpoint immediately rendered with “Saved checkpoint” provenance. The server returned 201.
3. **Focus change:** navigated to Language and clicked **Set focus**; the current focus became Language while the Math checkpoint remained visible as Resume last work.
4. **Backend restart:** stopped the backend with `scripts/stop.ps1`, started it again with `scripts/start.ps1`, reloaded the Math workspace. Checkpoint content, next action, milestone, blocker and evidence were intact. `/api/resume` reported focus Language.
5. **UI launch (isolated instance port 8791):** registered a safe fixture application, clicked **Launch** in the Applications dashboard, saw Running with PID 2808, opened **Logs** and read real fixture output including `fixture-arg=ui-acceptance`. The data directory and port were isolated from the real workspace.
6. **Logs:** modal displayed the log path, redaction notice and captured output.
7. **Theme:** toggled dark → light; `data-theme` and local storage updated. The evidence screenshots use a separate headless profile with a forced dark theme so they remain comparable.
8. **Briefing:** clicked **Generate** on Today; a deterministic briefing was created and displayed without a provider. No AI button was shown because AI was not configured.
9. **Discovery:** ran a real scan from Settings; 98 candidates, counts and errors rendered; candidates include generated classification evidence and remain advisory.

## API/status observations

- `/api/health`: `status=ok`, `database=ok`, `schema_version=1`, `ai_enabled=false`.
- Work was shown as unavailable/blocked after the health-monitoring policy was corrected to only monitor enabled definitions. A transient earlier observation proved why a responding port must not be treated as proof of ownership.
- Worker adapter unavailable because no server was listening at 7317.
- CoCoder adapter unavailable because no review artifact path was configured.
- Next adapter read a local SQLite snapshot and explicitly did not claim production/PostgreSQL truth.

## Screenshot method

Headless Chrome, 1440×1100, forced dark theme, `--virtual-time-budget=7000` to allow API rendering. The interactive smoke used the harness browser against the live server; its DOM text and network/API results were inspected directly. No console errors were reported.
