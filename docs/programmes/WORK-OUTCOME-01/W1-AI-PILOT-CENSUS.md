# W1-AI-PILOT-CENSUS — Seven frozen cases (`C:/Projects/ai`, 147 sessions)

Genuine history, read-only census 2026-11-24. Full session ids frozen below
(display prefixes elsewhere are truncated). Classifications are **candidates**
for W2+ evaluation, not verdicts: W1 freezes identifiers + observed signals.

| # | Case | Frozen id | Observed signals |
| - | ---- | --------- | ---------------- |
| 1 | Evidence-rich (completed-candidate) | `ses_e4a7bb7f5ffeFdI2zSoOS6EAgI` | 4,277 msgs; 88 distinct SHA candidates, 3 verified present in indexed ai history (`03614a1` AI-CORE-08C implementation, `0756ac4` independent review, `0973ae7`); tasks AI-CORE-01…05; 7 completion claims; files incl. `ai/experience/service.py` |
| 2 | Incomplete-candidate | `ses_e47dfff00ffeTwrXVz0CEjBJ4Y` | 2 msgs; probe request ("Return the single word READY"); 0 tool invocations, 0 SHAs, 0 task ids — request clear, no execution observed |
| 3 | Multi-commit | `ses_e01c78c9cffegYHL5mjmUWQh3y` | 9 distinct SHA candidates (`0274296`, `0a0b7bc`, `49d89821`, …); 2 verified present (`0274296` infer upgrade, `0a0b7bc` WEB-01B record) |
| 4 | Multi-session | `ses_e48a16fc4ffeVAkWepbPb7N673` | parent with 14 ai children (`ses_e48829d7…`, `ses_e47d55e3…` ×2, `ses_e475ebd3…` ×2, `ses_e4533708…` ×2, `ses_e452c0437…`, `ses_e3edd311…`, `ses_e3edd310…`, `ses_e3e6b1f1…`, `ses_e3e6b1f0…`, `ses_e3e1ea920…`, `ses_e3e1ea91…`); 1,040 msgs, 29 SHAs, 2 claims |
| 5 | Claim without SHA evidence | `ses_e342f0944ffeA8puoI7qklwtpP` | 3 msgs; 1 completion claim; 0 SHA candidates, 0 task ids |
| 6 | Legitimate non-code | `ses_e33d68988ffec0ZSyT2HSd3U7b` | 3 msgs; attached-file instruction task (`opencode-prompt-dv2lbr2x.md` + CONSTRAINTS); no code/file/SHA signals |
| 7 | Ambiguous | `ses_e47f053b3ffezpzYYzP1RNsWHv` | 2 msgs; user text not classifiable beyond `REQUEST:` prefix; 0 tools/SHAs/tasks — weak-only, abstain |

## Coverage notes

- ai worktree: 147 sessions, all with ≥1 message; 5,917 assistant messages scanned.
- SHA-bearing sessions: 14; ≥2 SHAs: 7; task ids: 10 sessions; file paths: 23;
  completion claims: 4; no-SHA/no-file sessions: 119 (non-code pool).
- Zero-message sessions in ai: 0 (ambiguity defined by signal weakness, not absence).
- SHA verification: 6/8 sampled candidates present in `gitrepo-b98edf97f18ab61c`
  (75 commits, `backfill_complete`, branch `main`); 2 absent
  (`0ada120a…`, `49d89821`) — recorded as unverified candidates, correctly
  unresolvable at W1 (abbreviation collision, foreign repo, or rewritten history).
- No case fabricated; every id above is a live `session_v2` row.
