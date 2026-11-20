# Integration and reuse map — MC-LIVING-BOOK-02D-R2 → MC-LIVING-BOOK-02C

## ALIVE capabilities reused unchanged

| Capability | Used for | Evidence |
| --- | --- | --- |
| Approved versioned source access + exact capture | chapter reads, plan, experience excerpts | capture `a632c716…` live-verified; stale-chapter refusal tested |
| Living Book reading state, notes, conversations | reading room; 02C generation path | `ask` with bounded session (50 calls / 1M tokens), citations, revocable |
| Workflow discovery + execution | chapter-improvement v1006, chapter-evaluation v1 | definition hashes recomputed from tree and matched to freezes |
| Informed chapter-improvement family v8/1001–1006 | PILOT-2 arms | `informed_definitions.py`; experience reaches only `*_improve` stages |
| Experience retrieval (`chapter_experience.build/validate_supplied`) | Arm B context; quality `evaluation_failed` stays `quality_unverified`, promotion `context_only` | context `e5993c62…` verified in run |
| Independent evaluation (`chapter.independent_evaluate`, rubric `chapter-evaluation-v1`, 7 mechanical checks) | Arm A evaluation (benefit) | eval `e7fd68df` |
| Append-only evidence + execution receipts | all runs, Pi runs, evaluations | retained under `docs/acceptance/mc-living-book-02d-r2/` |
| Provider request identity + terminal ambiguity | B failure forensics | `upstream_ref`, `Generation.request_id`, UNKNOWN handling |
| Cancellation + revocation | containment | offline suites 40/40; session revoke path intact |
| Pi/process supervision, one-request ceiling | transport | `MAX_PROVIDER_REQUESTS=1` code-enforced; 13 calls, 0 ambiguous, 0 retries |
| Mechanical preservation checks | 02C obligations + validation | `evaluation_preservation.checks` reused for passage→rendering |
| Conversation `verification` field, message citations | 02C standing + span anchors | surfaced in UI |

## ALIVE code added (additive, no modified cognition)

- `alive/living_book/semantics.py` — deterministic obligations, span validation, standing, fixture, instruction builder.
- `alive/living_book/service.py` — `represent/representations/representation/reject_representation` (+ `_parse_candidate`); reuses `ask`, custody, ledger.
- `alive/living_book/contracts.py` — `RepresentRequest`; `api.py` — 4 routes.

## Mission capabilities reused unchanged

Reading room, chapter/book navigation, notes, quality panel + evidence,
improvement preview/launch/history, proposal diffs, decision recording,
experience-context visibility, comparison endpoint + UI (pair rules
`benefit/harm/no_benefit/inconclusive`), source mapping. The R2 pair renders
in the existing comparison view with zero changes.

## Mission code added

- Proxy `represent/representations/representation/reject_representation`
  (client + service + API routes) — forwards only; owns no cognition.
- `ExplorePanel.tsx` + Explore tab wiring; rendering via existing
  `BookMarkdown` (mermaid/KaTeX already vendored); types in `living-book.ts`.

## Found unsuitable / rejected

- Sharing one retained review across arms: would need new launch/Grant plumbing
  → registered as complete-pipeline comparison instead.
- New model capability for mediation: would need a new typed dispatch binding
  (Phase-A `authority_refused` lesson) → reused the conversation path.
- Global timeout raise: rejected → process-scoped `ALIVE_META_TIMEOUT=90`.
- New memory/workflow/model-gateway/ranking/quality systems: none built.
- Irrelevant-experience arm: blocked (only one genuine eligible item); H2 untested.

## Environment repairs (not research)

- Pi 1.5.0 bundle vanished (auto-updater); installed repo-pinned Pi 1.4.0 via
  `npm ci` from the committed lockfile. The committed bundle-sha pin matches
  no file in the faithful install (stale pin) → check skipped process-scoped,
  version enforced, digest recorded per receipt. Re-pin is future ALIVE work.
