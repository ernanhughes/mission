# W3-UNRESOLVED-COVERAGE-BASELINE — Precise denominators (read-only)

## Reconciliation (live OpenCode DB, deterministic rescan 2026-11-24)

- Total ai sessions: **147**, all with ≥1 message (6,390 messages).
- Sessions with task/sha/file signals: **30**; in parent-child chains: **17**
  (all chained sessions also carry signals; union = 30).
- **Exclusively unresolved: 117** (no task/sha/file signals, no chain link).
- W2 bucket held 126 refs = 117 exclusive + 9 signal-bearing-but-homeless
  (e.g. SHA candidates that resolve nowhere, file signals with no commit
  overlap — e.g. frozen case 5). Consistent, not contradictory.
- Messages: 6,045/6,390 (**94.6%**) live in signal-bearing-or-chained
  sessions; only **345 messages (5.4%)** sit in the 117 exclusive sessions.
- Volume of the exclusive set: 110 sessions × 3–6 msgs, 7 × 1–2 msgs —
  predominantly short probe/instruction sessions (attached-file prompts,
  READY probes), not substantive work histories.
- 13 sessions carry completion claims; 25 invoke tools.

## Consequences

- "126 of 147 unresolved" is a session-count artefact. By message volume,
  observation coverage is ~95%. Triage priority must weight volume and
  signal density, never raw session counts.
- The unresolved bucket is NOT 126 manual tasks: ~110 are 3–6-message
  probes classifiable deterministically (TRIVIAL/INSUFFICIENT) without any
  model call. Semantic extraction budget goes to the ~9 homeless-but-
  signal-bearing sessions + research/design traffic, not the probes.
- Denominators for W3 coverage: sessions 147; messages 6,390; episodes 30;
  linked commits 73/75. Coverage-after-triage must keep the same denominators
  (§19: exclusions reported separately, never silently dropped).
