# PUB-09 Reuse and Integration Matrix

Authoritative inputs: `writer/.../capabilities/catalog.py` (167 manifests, 15 pilot runtimes
with real adapters), Mission `api/*.py` + pages (surveyed 2026-11-25, read-only).
Rule: reuse before inventing; read by reference; no duplicate registry, gateway,
mutation path, or execution architecture.

## 1. Publication capabilities — callable today vs CLI/library-only

| Need (PUB-09 §11 stage) | Callable today (adapter + operations registry) | CLI/library-only (deterministic) | Missing |
|---|---|---|---|
| Objectives / preservation constraints | `metadata` adapter (DEFINE_OBJECTIVE, RETRIEVE, STRUCTURE) | — | — |
| Evidence claim extract / verify | — | `evidence_reconciliation` + `jev_evidence` inventory; `reconcile resolve` consumes PUB-02 JSON (`reconcile` CLI) | `evidence` domain: pipeline but no adapter |
| Cruft / complexity / pedagogy findings | — | `publication_cruft` (`cruft review`), `publication_complexity` (`complex review/scan/compare`), `publication_pedagogy` (`pedag plan/validate`) | No runtimes (prepared payloads never dispatched) |
| Candidate generation (bounded) | `sentence_repair` (GENERATE), `review` COTMOE (GENERATE/COMPARE/DECIDE), `improvement` (ORCHESTRATE/DECIDE) | `transform automate` (1 package → 1 editorial + 1 review; `--dry-run` zero dispatch) | Whole-chapter reconstruction: no engine (PUB-08 hypothesis, unproven) |
| Candidate validation | `artifact` (OBSERVE/EVALUATE/COMPARE/VERIFY), `sdd`, `scoring`, `qc` (VERIFY/EVALUATE) | `transform check/package/verify/surgical` (deterministic); `quality` CLI (evaluate/campaign/verify) | — |
| Semantic preservation / grounding | — (mediated_read claims RETRIEVE/RESEARCH/STRUCTURE/ORCHESTRATE only) | eval fabric (`eval` CLI benchmarks); mediated_read experiment/evaluate/divergence | `reader_study` does not exist; human judgments in mediated-read DB |
| Feedback / training signal | `training` + feedback adapters (CAPTURE_FEEDBACK, TRAIN) | — | — |
| Book production | — | validation preflight profile (Pandoc/Hugo/EPUB guards); `novel_formatter` export; EPUB import only | No bookbuilder; no in-repo EPUB/PDF renderers (external Hugo/Pandoc) |

## 2. Mission surfaces to reuse (no new top-level page — ADR-007)

| PUB-09 need | Existing surface | Reuse |
|---|---|---|
| Publication section home | `BookPublishingPage` (`/projects/:projectId/publishing`) + project `publishing` tab (`PublishingPanel` summary) | Extend in place with tabs |
| Chapter inventory | `BookTab` (living-book chapters, discovery), pipeline `ChapterMatrix`, quality discovery | Project discovery + living-book API by reference |
| Assessments / gates / blockers | `/api/publication` (assessments, publishing/overview, gates, evidence, blockers, dossiers) | Direct reuse; add per-chapter gate breakdown read-projection only |
| Findings grouping | Quality/technical chapter cards (`ACCEPT/REJECT/DEFER/INVESTIGATE` + portable requests, never auto-apply) | Copy pattern, separate publication decision store (existing `PublicationIssue` review) |
| Review + approval UI | `POST /approvals` (`PublicationApprovalCreate`: assessment + decision + rationale + accepted-limitation ids + reviewer), `POST /issues/:id/review` | Wire UI (currently API-only) — no new endpoint |
| Candidate staging | `PublicationFollowup` (provenance + recheck/close) + pub06/pub07 retained artifacts by reference | Reference only; no new store |
| Authoritative mutation | Workbench `chapter_apply` (PUB-06/07 bridge, staged + QC + fingerprint checks) | Sole path; Mission never mutates manuscript |
| Execution launch | Harness envelope pattern (`actor` 2–80 + note + digest + idempotent submission) + Worker typed-task seam | Same authorization shape for any model-backed publication run |
| Cost / usage | `/api/cost` (read-only) + per-run usage records | Read-only roll-up per assessment; no new metering |
| Objectives / proposals / findings | Work Outcome APIs (episodes, objectives, findings, proposals, envelopes) | Link, don't duplicate |

## 3. Gaps requiring genuine implementation

1. **Per-chapter publication gate breakdown** — gates are book-level (`PublicationGateResult`); chapters need gate state. Read-projection over living-book chapters × gate results; no new table.
2. **Candidate inventory** — retained pub06/pub07 candidates + Workbench staged proposals referenced by digest; read-projection only.
3. **Review/approval forms** — wire existing endpoints (reviewer + rationale + fingerprint + accepted limitations); block on missing verification per existing policy.
4. **Reading + comparison views** — reuse ALIVE/LivingBook rendering + PUB-08 blinded package pattern; no new renderer.
5. **Publication-scoped authorization** — bind Work Envelope (episode + objective + digest) to a manuscript fingerprint for "publish this exact snapshot"; approval remains separate from application.
6. **Whole-chapter reconstruction investigation** — no engine exists; PUB-09 investigates via existing GENERATE adapters + verification loop, reports honestly, proves nothing yet.

## 4. Explicitly not built

New registry, model gateway, mutation path, SQLite/parallel persistence, production migrations, bulk manuscript writes, bookbuilder/EPUB/PDF renderer, paid inference without authorization, PUB-10 work, commits/pushes.
