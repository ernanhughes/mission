# H3 Reproduction Guide

From `C:\Projects\mission\docs\programmes\HARNESS-EVOLUTION-01\h3-fixtures` with Node 25+ and the Mission virtual environment available:

1. Run `node --experimental-transform-types --loader ./worker-ts-loader.mjs ./run-worker-baseline.mjs C:/Projects/worker`. The runner validates the pinned fixture and evaluator before dispatch and prints a fresh artifact directory.
2. Pass that directory to `C:\Projects\mission\.venv\Scripts\python.exe .\resolve-mission-episode.py <run-directory>`. This creates and reads only a run-local SQLite Mission fixture.
3. Verify with `C:\Projects\mission\.venv\Scripts\python.exe .\evaluate.py <run-directory> .\task-manifest.json`.
4. Run short evaluator tests with `C:\Projects\mission\.venv\Scripts\python.exe -m unittest test_evaluate.py -v`.

No network, model provider, executable transport, operational Mission DB, or migration is needed. Worker’s Bun unit tests require Bun and were not run in this environment.
