# Mission Control — agent guidance

## Test execution policy

- Run focused test files for the code you changed plus their immediate
  neighbours. Do not run the full backend or frontend suite as a default.
- Any test taking more than ~2 seconds wall-clock is a **long** test. Mark it
  `@pytest.mark.long` (backend) or the frontend equivalent and question whether
  it belongs in the routine loop.
- Do not run `long` tests during ordinary implementation, verification or
  review loops, and do not put them in stage prompts. Run them only when the
  change directly targets that corpus or a release/acceptance gate requires
  it; otherwise record them as deliberately deferred.
- Writer (`C:\Projects\writer`) excludes `long`, `slow`, `model` and
  `integration` tests in `pytest.ini`. The capability-resolution corpus
  (`test_capability_resolution_corpus`) is a ~2-minute `long` test and is not a
  per-stage smoke test. See `C:\Projects\writer\AGENTS.md`.
- A stage/verification report should name the short suites that ran and any
  long suite that was intentionally skipped.
