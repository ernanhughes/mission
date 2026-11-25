# W6A-REQUIREMENT-RECOVERY — Why zero, what was recovered, what remains

## Why the pilot reported zero requirements (§4 investigation)

Verified against code + live data, in order of explanatory power:

1. **Deterministic extraction abstains by design** (`extract.py`
   `extract_episode_deterministic`: "Requirements need judgement and are
   explicitly abstained here"). The ai backfill ran the deterministic path
   for all 30 episodes → 0 requirements mechanically, 26 inferred
   objectives, 1,267 claims. This is the dominant cause.
2. **Semantic extraction produced nothing usable**: 6 episodes attempted
   via loopback mistral-small; outputs failed validation (paraphrase /
   vacuity / authority gates held). Correct abstention, not a bug.
3. **Requirements live outside OpenCode**: the richest intent artifacts
   for the ai pilot are repo documents (design/review/qualification),
   which the W3 evidence packet never sees (packet = session signals
   only). Even a perfect session model could not recover the R1 gates
   from chat history alone.
4. Episode segmentation, authority rules and validation gates are
   contributing but secondary: the gates correctly rejected weak output
   (see W6A-MODEL-CAPABILITY for the one calibration fix applied).

Authority/em-dash constraints were NOT weakened: manual recovery accepts
only explicit_user/accepted_proposal with digest + basis; the model
validator was tightened (explicit_user objectives now require a session
source), never loosened.

## Repository-artifact recovery (§5, deterministic + human-confirmed)

`req_sources.py` (read-only): episode key → filename scan over
docs/{design,reports,reviews,architecture,guides,evaluation,
qualification,programmes,plans} + `git log --grep` history + sibling
review detection. It never assigns authority; review siblings flag
accepted_proposal-*candidates*; a human confirms. New API:
GET /api/work-intent/source-candidates, GET /requirement-sources,
POST /requirements (provenance mandatory, vacuity/paraphrase rejected).

Resolved repos via linked commits, with project_key→repo fallback
(AI-CORE-05 has 0 linked commits; fallback matched Projects/ai →
C:\Projects\ai).

## Recovered for real episodes (§7)

| Episode | Candidates | Recovered | Authority |
| ------- | ---------- | --------- | --------- |
| AI-CORE-05 | qualification + R1 review | 7 requirements (6 R1 gates A–G + 1 anchored regression req) | accepted_proposal, digests 0784968e/278bfad0, rev a8c4199 |
| AI-CORE-08B-1 | 5 (RANKING + 2 reviews) | 1 (artifact integrity) | accepted_proposal, digest 68aa40ca |
| AI-CORE-08C | 14 (CONTRACTS + pre-change review 2026-11-09) | 1 (dimension identity/versioning) | accepted_proposal, digest 792eb321 |

All 9 carry source_digest + authority_basis + reviewer=w6a-human in
wo_requirement_sources. Nothing was fabricated: texts quote the
documents' gate criteria; a repo document alone never sufficed (review
sibling or commissioning message required).

## What remains

USE-01A (3 design/report candidates) and the remaining 20+ task episodes
are unrecovered: candidate scans exist via the API, human confirmation
pending. The zero is now 9, with a repeatable path for the rest — not a
blanket fix. Semantic re-extraction with the tightened validator is
available but unrun at scale (budget kept minimal).
