# W2-RECONSTRUCTION-ARCHITECTURE — Deterministic pipeline

```
W1 wo_signals (PG) ──┐
OpenCode sessions ───┼──► EpisodeService.run_reconstruction ──► wo_episodes
git index + diff-tree ┘    (bounded, read-only, zero model calls)  wo_episode_associations
                                                                     wo_recon_runs
```

Pure engine (`reconstruct.py`, no I/O) over assembled records; service
(`episodes.py`) assembles inputs, persists with upsert + supersession, exposes
queries; API (`api/work_episodes.py`) offers list/get/unresolved/associations/
coverage + one bounded POST. No Activity UI changes.

## Rules (R1–R7, each independently testable; see W2-CORRELATION-RULES)

R1 task/stage/programme seeds (explicit ids; artefacts rejected) → R2 chain
seeds (parent links, strongest structural signal) → R6 hierarchy (co-mention
parent links, cycle-checked) → R3 commit resolution (repo-scoped existence;
same-repo explicit, other-repo candidate, absent rejected/unresolved, ambiguous
prefix abstains) → R4 file overlap (+ temporal support; common files excluded)
→ R7 review_of (review-tool invocation + shared task; resolution never
inferred) → leftovers to the per-project unresolved bucket. R5: time alone
never links (enforced by construction — no rule consumes bare timestamps).

## Key behaviours

- Many-to-many throughout: sessions span episodes, episodes span sessions,
  commits attach to several episodes (18/75 in pilot — recorded, not merged).
- Abstention is a first-class outcome (126/147 pilot sessions unresolved —
  mostly 2–6 message probe/READY sessions with no corroboration).
- Incremental: new sessions join existing episodes by stable id; replays add
  nothing; supersession retires vanished same-scope episodes without deletion.
- Historical vs current: `first/last_seen_ms` (event time) vs
  `created_at/updated_at` + `recon_version` (observation time); merge/split
  provenance in run stats + association validity flags.
