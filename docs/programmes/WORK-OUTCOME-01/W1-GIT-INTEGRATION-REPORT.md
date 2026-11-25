# W1-GIT-INTEGRATION-REPORT — Reuse, no second history

- Identity: `git/history.resolve_identity()` (read-only plumbing). `None`
  (nonexistent/non-repo) → recorded `unresolvable` error, never an exception
  (fixed `top_level`→`toplevel` bug found by test).
- Facts: existing `git_repositories`/`git_commits` index. `C:/Projects/ai`
  resolves (`repo_uid git-78e0d72b…`) and is indexed in operational PG as
  `gitrepo-b98edf97f18ab61c` (branch `main`, 75 commits, `backfill_complete`);
  12,779 commits across 110 indexed repos total.
- SHA linkage (pilot proof): 6/8 sampled candidate SHAs from frozen ai
  sessions exist in the indexed ai history (incl. AI-CORE-08C implementation
  and its independent review); 2 absent → unverified candidates, correctly
  unresolved at W1.
- Merge/squash/rebase/cherry-pick/worktree/uncommitted handling: inherited
  from the existing index with its documented limits (W0-EXISTING-ACTIVITY-ARCHITECTURE
  §4); W1 adds no new Git reader and represents unavailable data explicitly
  (`indexed: False`, error strings). Cross-repo aggregation and alias
  resolution are W2.
