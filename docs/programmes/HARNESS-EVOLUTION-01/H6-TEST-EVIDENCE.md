# H6 focused test evidence

Executed in the shared worktrees on 2026-11-25. The ordinary pytest AITest supervisor exited before collection in this local setup; the documented native pytest escape hatch was used for the focused H6 backend file.

| Area | Command | Result |
|---|---|---|
| Mission backend | `$env:PYTHONPATH='backend'; pytest --aitest-mode=off -q backend/tests/test_harness_api.py` | 10 passed; 0.21s pytest time. One environment warning: installed pytest does not recognize configured `timeout`. |
| Mission frontend | `npm test -- --run src/test/HarnessPage.test.tsx src/test/ProjectTabs.test.tsx src/test/ProjectPage.test.tsx` from `frontend` | 22 passed across 3 files; 5.94s test process (startup/transform included). |
| Mission frontend build/typecheck | `npm run build` from `frontend` | Passed; Vite reports existing large chunks above 500 kB. |
| Worker strategy/server | `bun test ./tests/strategies.test.ts ./tests/server.test.ts` | 32 passed. |
| Worker typecheck | `bun run typecheck:worker` | Passed. |

The declared frontend lockfile was installed with `npm ci --ignore-scripts --no-audit --no-fund` because the existing `node_modules` directory had no packages. npm emitted Node engine warnings for dependencies requesting Node 22/24/26 while this host runs Node 25.8.2; focused tests and build passed. The Mission backend/frontend were not run as full suites. Long suites and the Worker-wide suite were deliberately deferred; the local provider/capability corpus was not needed for this synthetic integration gate.
