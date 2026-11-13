import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Circle,
  Crosshair,
  ExternalLink,
  FolderOpen,
  GitBranch,
  Pencil,
  Pin,
  PinOff,
  Play,
  Plus,
  RefreshCw,
  Save,
  X,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  ActionButton,
  EmptyState,
  ErrorState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PathText,
  ProvenanceBadge,
  Section,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import {
  activityLabel,
  formatDateTime,
  projectLabel,
  shortCommit,
  timeAgo,
  titleCase,
  truncate,
} from "../lib/format";
import type {
  Adapter,
  Application,
  ArtifactLoadChapter,
  ArtifactLoadWorkspace,
  Checkpoint,
  IntegrationRecord,
  ProjectDetail,
  ProjectEvidenceTimeline,
  QualityCampaign,
  QualityChapter,
  QualityDiscovery,
  QualityEvaluation,
  QualityReview,
  QualityWorkspace,
  Recommendation,
  Task,
  TechnicalChapterAssessment,
  TechnicalClaim,
  TechnicalCompleteness,
  TechnicalGap,
  TechnicalObjective,
  TechnicalRequirement,
  WriterDecisionQueueItem,
  WriterWorkspace,
} from "../types/api";

function CheckpointForm({ projectId, onSaved }: { projectId: string; onSaved: () => void }) {
  const toast = useToast();
  const [summary, setSummary] = useState("");
  const [lastCompleted, setLastCompleted] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [blockers, setBlockers] = useState("");
  const [milestone, setMilestone] = useState("");
  const [evidence, setEvidence] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/checkpoints", {
        project_id: projectId,
        summary,
        last_completed: lastCompleted,
        next_action: nextAction,
        blockers,
        milestone,
        evidence_refs: evidence
          .split(/\r?\n|,/)
          .map((item) => item.trim())
          .filter(Boolean),
      });
      toast.push("success", "Checkpoint saved", "This project is now the current focus.");
      setSummary("");
      setLastCompleted("");
      setNextAction("");
      setBlockers("");
      setMilestone("");
      setEvidence("");
      onSaved();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form-stack checkpoint-form" onSubmit={(event) => void save(event)}>
      <InlineError message={error} />
      <label className="field">
        <span>What happened?</span>
        <textarea
          rows={3}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="A plain summary of where the work stopped."
          required
        />
      </label>
      <div className="form-grid two">
        <label className="field">
          <span>Last completed action</span>
          <input value={lastCompleted} onChange={(event) => setLastCompleted(event.target.value)} />
        </label>
        <label className="field">
          <span>Next intended action</span>
          <input value={nextAction} onChange={(event) => setNextAction(event.target.value)} />
        </label>
      </div>
      <div className="form-grid two">
        <label className="field">
          <span>Blockers</span>
          <input value={blockers} onChange={(event) => setBlockers(event.target.value)} />
        </label>
        <label className="field">
          <span>Milestone (optional)</span>
          <input value={milestone} onChange={(event) => setMilestone(event.target.value)} />
        </label>
      </div>
      <label className="field">
        <span>Evidence references (one per line)</span>
        <textarea
          rows={2}
          value={evidence}
          onChange={(event) => setEvidence(event.target.value)}
          placeholder="artifacts/math01/report.json"
        />
      </label>
      <div className="form-actions">
        <button className="button button-primary" type="submit" disabled={saving || !summary.trim()}>
          <Save size={15} /> {saving ? "Saving checkpoint…" : "Save checkpoint"}
        </button>
      </div>
    </form>
  );
}

function TaskRow({
  task,
  onChanged,
}: {
  task: Task;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  async function toggle() {
    setBusy(true);
    try {
      await api.patch(`/api/tasks/${task.id}`, {
        status: task.status === "done" ? "open" : "done",
      });
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not update task", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveTitle() {
    if (!title.trim() || title.trim() === task.title) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      await api.patch(`/api/tasks/${task.id}`, { title: title.trim() });
      toast.push("success", "Task updated");
      setEditing(false);
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not update task", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`task-row ${task.status === "done" ? "done" : ""}`}>
      <button
        className="task-check"
        onClick={() => void toggle()}
        disabled={busy}
        aria-label={task.status === "done" ? `Reopen ${task.title}` : `Complete ${task.title}`}
      >
        {task.status === "done" ? <CheckCircle2 size={17} /> : <Circle size={17} />}
      </button>
      <div className="task-copy">
        {editing ? (
          <span className="task-edit">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              aria-label={`Edit title for ${task.title}`}
              autoFocus
              onKeyDown={(event) => {
                if (event.key === "Enter") void saveTitle();
                if (event.key === "Escape") {
                  setTitle(task.title);
                  setEditing(false);
                }
              }}
            />
            <button className="icon-button" onClick={() => void saveTitle()} aria-label="Save task title">
              <Save size={14} />
            </button>
            <button
              className="icon-button"
              onClick={() => {
                setTitle(task.title);
                setEditing(false);
              }}
              aria-label="Cancel task edit"
            >
              <X size={14} />
            </button>
          </span>
        ) : (
          <strong>{task.title}</strong>
        )}
        {task.description ? <span>{task.description}</span> : null}
      </div>
      <div className="task-row-actions">
        <SimpleStatusBadge state={task.status} />
        {!editing ? (
          <button
            className="icon-button"
            onClick={() => setEditing(true)}
            aria-label={`Edit ${task.title}`}
            disabled={busy}
          >
            <Pencil size={13} />
          </button>
        ) : null}
      </div>
    </li>
  );
}

function RecommendationRow({
  recommendation,
  onChanged,
}: {
  recommendation: Recommendation;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  async function review(state: string) {
    setBusy(state);
    try {
      await api.patch(`/api/recommendations/${recommendation.id}`, {
        review_state: state,
        note: state === "accepted" ? "Accepted from the project workspace." : "",
      });
      toast.push("success", `Recommendation ${state}`);
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not review recommendation", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }
  return (
    <li className="recommendation-card">
      <div className="recommendation-head">
        <div>
          <strong>{recommendation.title}</strong>
          <div className="inline-meta">
            <ProvenanceBadge value={recommendation.provenance} />
            <span>{recommendation.source_application ?? "Workspace"}</span>
            <span>{timeAgo(recommendation.created_at)}</span>
          </div>
        </div>
        <SimpleStatusBadge state={recommendation.review_state} />
      </div>
      <p>{truncate(recommendation.rationale, 500)}</p>
      {recommendation.evidence.length ? (
        <details className="evidence-list">
          <summary>Evidence ({recommendation.evidence.length})</summary>
          <ul>
            {recommendation.evidence.map((item) => (
              <li key={item}>
                <code>{item}</code>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {recommendation.review_state === "pending" ? (
        <div className="button-row">
          <button
            className="button button-primary button-small"
            disabled={busy !== null}
            onClick={() => void review("accepted")}
          >
            Accept
          </button>
          <button
            className="button button-secondary button-small"
            disabled={busy !== null}
            onClick={() => void review("deferred")}
          >
            Defer
          </button>
          <button
            className="button button-ghost button-small"
            disabled={busy !== null}
            onClick={() => void review("rejected")}
          >
            Reject
          </button>
        </div>
      ) : null}
    </li>
  );
}

function AdapterCard({ adapter, projectId, onChanged }: { adapter: Adapter; projectId: string; onChanged: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true);
    try {
      await api.post(`/api/adapters/projects/${projectId}/refresh`);
      toast.push("success", "Adapter refreshed");
      onChanged();
    } catch (caught) {
      toast.push("error", "Adapter refresh failed", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="adapter-card">
      <div className="adapter-head">
        <div>
          <strong>{titleCase(adapter.adapter)}</strong>
          <span className="adapter-status">
            <SimpleStatusBadge
              state={adapter.available ? (adapter.stale ? "stale" : "running") : "unavailable"}
              label={adapter.available ? (adapter.stale ? "Stale" : "Available") : "Unavailable"}
            />
          </span>
        </div>
        <button className="icon-button" onClick={() => void refresh()} disabled={busy} aria-label="Refresh adapter">
          <RefreshCw size={14} className={busy ? "spin" : ""} />
        </button>
      </div>
      <p>{adapter.detail}</p>
      {adapter.error ? <p className="warn-text small">{adapter.error}</p> : null}
      <div className="adapter-meta">
        <span>{adapter.last_checked_at ? timeAgo(adapter.last_checked_at) : "Never checked"}</span>
        {adapter.capabilities.length ? <span>{adapter.capabilities.join(" · ")}</span> : null}
      </div>
    </div>
  );
}

const QUALITY_DIMENSIONS = ["clarity", "argument", "precision", "economy", "voice", "structure"];
const QUALITY_DIM_SHORT: Record<string, string> = {
  clarity: "Clar.",
  argument: "Arg.",
  precision: "Prec.",
  economy: "Econ.",
  voice: "Voice",
  structure: "Struc.",
};

function freshnessTone(state: string): "accent" | "danger" | "default" {
  if (state === "current") return "accent";
  if (state === "stale" || state === "outdated") return "danger";
  return "default";
}

function invalidQuoteCount(evaluation: QualityEvaluation): number {
  return Object.values(evaluation.dimensions ?? {}).filter((dim) => !dim.evidence_validated).length;
}

function QualityEvaluationCard({ evaluation }: { evaluation: QualityEvaluation }) {
  const toast = useToast();
  const invalid = invalidQuoteCount(evaluation);
  const execution = evaluation.execution ?? {};
  const writerFindings = Array.isArray(evaluation.findings) ? evaluation.findings : [];
  const reviews = useApi<QualityReview[]>(`/api/quality/evaluations/${evaluation.id}/reviews`);
  const [reviewBusy, setReviewBusy] = useState<string | null>(null);
  const reviewByFinding = new Map((reviews.data ?? []).map((r) => [r.finding_id, r]));

  async function recordReview(findingId: string, decision: string) {
    setReviewBusy(findingId + decision);
    try {
      await api.post(`/api/quality/evaluations/${evaluation.id}/reviews`, {
        evaluation_id: evaluation.id,
        finding_id: findingId,
        decision,
        reason: "",
        reviewer: "author",
      });
      reviews.reload();
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    } finally {
      setReviewBusy(null);
    }
  }

  function downloadImprovementRequest(finding: Record<string, any>) {
    const review = [...(reviews.data ?? [])]
      .filter((r) => r.finding_id === String(finding.finding_id ?? ""))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];
    const spans = Array.isArray(finding.evidence) ? finding.evidence : [];
    const starts = spans.map((s) => s.start_line).filter((n) => typeof n === "number");
    const ends = spans.map((s) => s.end_line).filter((n) => typeof n === "number");
    const payload = {
      contract_version: "portable-improvement-v1",
      request_id: null as string | null,
      book_id: evaluation.book_id,
      chapter_id: evaluation.chapter_id,
      source_fingerprint:
        (evaluation.execution as Record<string, any>)?.source_fingerprint ?? "",
      finding: {
        finding_id: finding.finding_id,
        family: finding.family,
        dimension: finding.dimension,
        claim: finding.claim,
        evidence_ids: finding.evidence_ids ?? [],
        evidence: finding.evidence ?? [],
        verification: finding.verification ?? null,
      },
      verdict: null,
      policy: null,
      review: review
        ? {
            decision: review.decision,
            reviewer: review.reviewer,
            at: review.created_at,
            source_digest: review.source_digest,
            source_status: review.source_status,
          }
        : null,
      objective: "",
      scope: {},
      note: "Fill objective, then run: writer quality prepare-request. Requires an ACCEPT review.",
      chapter_improvement_snapshot: {
        selections:
          starts.length && ends.length
            ? [
                {
                  start_line: Math.min(...starts),
                  end_line: Math.max(...ends),
                  paragraph_ids: [],
                  paragraphs: [],
                  note: String(finding.claim ?? "").slice(0, 500),
                },
              ]
            : [],
        external_rows: spans.map((span: Record<string, any>) => ({
          evidence_id: span.evidence_id ?? finding.finding_id,
          provider: "writer-quality",
          family: finding.family,
          finding_type: finding.dimension,
          severity: "",
          region: { start_line: span.start_line, end_line: span.end_line },
          freshness: "CURRENT",
          chapter_id: evaluation.chapter_id,
          source_revision:
            (evaluation.execution as Record<string, any>)?.source_fingerprint ?? "",
          finding_id: finding.finding_id,
          verification: finding.verification ?? null,
        })),
        profile: "technical",
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `improvement-request-${String(finding.finding_id ?? "finding")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  return (
    <article className="writer-finding" id={`eval-${evaluation.id}`}>
      <div className="writer-finding-head">
        <div>
          <Tag tone={freshnessTone(evaluation.derived_state)}>
            {titleCase(evaluation.derived_state)}
          </Tag>
          {evaluation.status !== "CURRENT" ? <Tag>{evaluation.status}</Tag> : null}
          <Tag>{evaluation.strategy ?? "direct"}</Tag>
          {evaluation.findings?.length ? (
            <strong>
              {evaluation.findings.length} finding{evaluation.findings.length === 1 ? "" : "s"} · no scores
            </strong>
          ) : (
            <strong>{evaluation.overall ?? "—"} / 6 · Prose quality</strong>
          )}
          <span className="writer-decision-count">
            {evaluation.chapter_revision.slice(0, 12)} · {evaluation.actual_model ?? "model unknown"}
          </span>
        </div>
        <code className="writer-locator">{formatDateTime(evaluation.created_at)}</code>
      </div>
      <div className="writer-mini-scores">
        {QUALITY_DIMENSIONS.map((id) => {
          const dim = evaluation.dimensions[id];
          return (
            <span key={id} title={dim ? `${id}: ${dim.evidence}` : `${id}: no score`}>
              {QUALITY_DIM_SHORT[id]}: {dim ? dim.score : "—"}
              {dim && !dim.evidence_validated ? " ⚠" : ""}
            </span>
          );
        })}
      </div>
      {evaluation.section_title ? (
        <p className="muted small">Section: {evaluation.section_title}</p>
      ) : null}
      <p className="muted small">
        Rubric {evaluation.rubric_id} v{evaluation.rubric_version} · prompt v{evaluation.prompt_version}
        {evaluation.previous_evaluation_id ? ` · after ${evaluation.previous_evaluation_id.slice(0, 14)}` : ""}
      </p>
      {execution.transport || execution.input_tokens != null ? (
        <p className="muted small">
          Transport {execution.transport ?? "unknown"}
          {execution.input_tokens != null ? ` · ${execution.input_tokens} in / ${execution.output_tokens ?? "?"} out` : " · usage unknown"}
        </p>
      ) : null}
      {invalid > 0 ? (
        <p className="warn-text small">
          {invalid} quotation{invalid === 1 ? "" : "s"} did not verify against the source and {invalid === 1 ? "is" : "are"} flagged, not repaired.
        </p>
      ) : null}
      {writerFindings.length ? (
        <ul className="plain-list">
          {writerFindings.map((finding, index) => {
            const findingId = String(finding.finding_id ?? `finding-${index}`);
            const existing = reviewByFinding.get(findingId);
            const judgment = (execution.decisions ?? []).find(
              (d: Record<string, any>) => d.finding_id === findingId,
            );
            const judgmentLabel = judgment
              ? ` · judgment: ${judgment.outcome?.status ?? "unknown"} (${judgment.outcome?.policy?.source ?? "?"})`
              : "";
            return (
              <li key={findingId}>
                <strong>{String(finding.family ?? "finding")}</strong>
                {" · "}
                <span className="muted small">{String(finding.claim ?? "")}</span>
                <br />
                <span className="muted small">
                  {(finding.evidence_ids ?? []).length} source span(s)
                  {finding.verification ? ` · ${finding.verification}` : ""}
                  {judgmentLabel}
                  {existing ? ` · reviewed: ${existing.decision} (${existing.source_status})` : " · unreviewed"}
                </span>
                {(finding.quotation_check as Record<string, unknown> | undefined)?.status === "unsupported" ? (
                  <span title="Quoted text was not found in the cited evidence. The finding is retained for review, not verified."><Tag tone="danger">quote unverified</Tag></span>
                ) : null}
                {(finding.quotation_check as Record<string, unknown> | undefined)?.status === "elsewhere" ? (
                  <span title="Quoted text found in the chapter but outside the cited spans."><Tag tone="accent">quote outside cited spans</Tag></span>
                ) : null}
                {(finding.numbers_check as Record<string, unknown> | undefined)?.status === "needs_semantic_review" ? (
                  <span title="Numbers in the claim need a comparability check (units, denominator, condition)."><Tag tone="accent">numbers need review</Tag></span>
                ) : null}
                {(finding.evidence ?? []).slice(0, 2).map((span: Record<string, any>, spanIndex: number) => (
                  <blockquote key={spanIndex} className="muted small">
                    {String(span.file ?? "")}:{span.start_line ?? "?"}–{span.end_line ?? "?"} —{" "}
                    {String(span.excerpt ?? "").slice(0, 280)}
                  </blockquote>
                ))}
                <br />
                {(["ACCEPT", "REJECT", "DEFER", "INVESTIGATE"] as const).map((decision) => (
                  <button
                    key={decision}
                    className="button button-secondary button-small"
                    disabled={reviewBusy !== null}
                    onClick={() => void recordReview(findingId, decision)}
                  >
                    {reviewBusy === findingId + decision ? "Saving…" : titleCase(decision.toLowerCase())}
                  </button>
                ))}
                {existing?.decision === "ACCEPT" ? (
                  <button
                    className="button button-secondary button-small"
                    title="Download a portable improvement request for this accepted finding. No manuscript is modified."
                    onClick={() => downloadImprovementRequest(finding as Record<string, any>)}
                  >
                    Prepare improvement
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {evaluation.workbench_link ? (
        <a className="text-link" href={evaluation.workbench_link} target="_blank" rel="noreferrer">
          Open chapter in Workbench <ExternalLink size={12} />
        </a>
      ) : null}
    </article>
  );
}

function QualityChapterCard({ chapter }: { chapter: QualityChapter }) {
  return (
    <article className="writer-decision-card" id={`quality-${chapter.chapter_id}`}>
      <div className="writer-decision-head">
        <strong>{chapter.chapter_id}</strong>
        <span className="writer-decision-count">
          {chapter.evaluations.length} evaluation(s)
          {chapter.sections.length ? ` · ${chapter.sections.length} section(s)` : ""}
        </span>
        {chapter.current ? (
          <Tag tone="accent">Current · {chapter.current.overall} / 6</Tag>
        ) : (
          <Tag>No current score</Tag>
        )}
      </div>
      {chapter.current ? <QualityEvaluationCard evaluation={chapter.current} /> : null}
      {chapter.evaluations.filter((item) => item.derived_state === "findings").length ? (
        <details className="history-list" open>
          <summary>
            Findings observations (
            {chapter.evaluations.filter((item) => item.derived_state === "findings").length}
            , no scores)
          </summary>
          {chapter.evaluations
            .filter((item) => item.derived_state === "findings")
            .map((item) => (
              <QualityEvaluationCard key={item.id} evaluation={item} />
            ))}
        </details>
      ) : null}
      {chapter.evaluations.filter(
        (item) => item.derived_state !== "current" && item.derived_state !== "findings",
      ).length ? (
        <details className="history-list">
          <summary>
            Earlier observations (
            {
              chapter.evaluations.filter(
                (item) => item.derived_state !== "current" && item.derived_state !== "findings",
              ).length
            }
            )
          </summary>
          {chapter.evaluations
            .filter(
              (item) => item.derived_state !== "current" && item.derived_state !== "findings",
            )
            .map((item) => (
              <QualityEvaluationCard key={item.id} evaluation={item} />
            ))}
        </details>
      ) : null}
      {chapter.sections.length ? (
        <details className="history-list">
          <summary>Section evaluations ({chapter.sections.length})</summary>
          {chapter.sections.map((item) => (
            <QualityEvaluationCard key={item.id} evaluation={item} />
          ))}
        </details>
      ) : null}
    </article>
  );
}

type MapRow = {
  chapter_id: string;
  title: string | null;
  dims: Record<string, number> | null;
  model: string | null;
  state: string;
  revision: string;
};

function QualityMap({ rows }: { rows: MapRow[] }) {
  const [sortKey, setSortKey] = useState<string>("chapter");
  const [showMissing, setShowMissing] = useState(true);
  const visible = rows.filter((row) => showMissing || row.dims !== null);
  const sorted = [...visible].sort((a, b) => {
    if (sortKey === "chapter") return a.chapter_id.localeCompare(b.chapter_id);
    const av = a.dims?.[sortKey] ?? -1;
    const bv = b.dims?.[sortKey] ?? -1;
    if (av !== bv) return av - bv;
    return a.chapter_id.localeCompare(b.chapter_id);
  });
  return (
    <div className="table-wrap">
      <div className="inline-meta">
        <label className="muted small">
          Sort by{" "}
          <select value={sortKey} onChange={(event) => setSortKey(event.target.value)} aria-label="Sort map rows">
            <option value="chapter">Chapter</option>
            {QUALITY_DIMENSIONS.map((dim) => (
              <option key={dim} value={dim}>{titleCase(dim)} (lowest first)</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          <input type="checkbox" checked={showMissing} onChange={(event) => setShowMissing(event.target.checked)} />{" "}
          Show unevaluated chapters
        </label>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Chapter</th>
            {QUALITY_DIMENSIONS.map((dim) => (
              <th key={dim}>{QUALITY_DIM_SHORT[dim]}</th>
            ))}
            <th>Model</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.chapter_id}>
              <td>
                <a className="text-link" href={`#quality-${row.chapter_id}`} title={row.title ?? row.chapter_id}>
                  {row.chapter_id.replace("-chapter.md", "")}
                </a>
              </td>
              {QUALITY_DIMENSIONS.map((dim) => (
                <td key={dim} className={row.dims && row.dims[dim] <= 3 ? "warn-text" : undefined}>
                  {row.dims ? row.dims[dim] : "—"}
                </td>
              ))}
              <td className="muted small">{row.model ? row.model.split("/").pop() : "—"}</td>
              <td>
                <Tag tone={freshnessTone(row.state)}>{titleCase(row.state)}</Tag>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type LoadRow = {
  chapter_id: string;
  title: string | null;
  prose_overall: number | null;
  mech: number | null;
  weighted_load: number | null;
  confirmed: number;
  high: number;
  unreviewed: number;
  coverage_mech: number;
  coverage_sem: number;
  assessment: string;
  workbench_link: string | null;
};

function assessmentLabel(state: string): string {
  switch (state) {
    case "assessed_findings":
      return "Assessed · findings";
    case "assessed_clean":
      return "Assessed · clean";
    case "partially_assessed":
      return "Partially assessed";
    case "not_assessed":
      return "Not assessed";
    case "stale":
      return "Stale";
    case "running":
      return "Running";
    case "blocked_failed":
      return "Blocked/failed";
    default:
      return "Not assessed";
  }
}

function ArtifactLoadMap({ rows }: { rows: LoadRow[] }) {
  const [sortKey, setSortKey] = useState<string>("assessment");
  const assessmentRank = (a: string): number =>
    ["not_assessed", "partially_assessed", "stale", "blocked_failed", "running"].includes(a)
      ? 0
      : 1;
  const sorted = [...rows].sort((a, b) => {
    if (sortKey === "chapter") return a.chapter_id.localeCompare(b.chapter_id);
    if (sortKey === "prose") return (a.prose_overall ?? 99) - (b.prose_overall ?? 99);
    if (sortKey === "high") return (b.high ?? 0) - (a.high ?? 0);
    if (sortKey === "assessment")
      return assessmentRank(a.assessment) - assessmentRank(b.assessment)
        || a.chapter_id.localeCompare(b.chapter_id);
    const av = a.weighted_load ?? -1;
    const bv = b.weighted_load ?? -1;
    return bv - av;
  });
  return (
    <div className="table-wrap">
      <div className="inline-meta">
        <label className="muted small">
          Sort by{" "}
          <select value={sortKey} onChange={(event) => setSortKey(event.target.value)} aria-label="Sort load rows">
            <option value="assessment">Unassessed first</option>
            <option value="load">Highest load first</option>
            <option value="high">Most high-severity first</option>
            <option value="prose">Lowest prose first</option>
            <option value="chapter">Chapter</option>
          </select>
        </label>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Chapter</th>
            <th>Prose / 5</th>
            <th>Pressure</th>
            <th>Load / 1k</th>
            <th>Confirmed</th>
            <th>High</th>
            <th>Unrev</th>
            <th>Coverage M/S</th>
            <th>Assessment</th>
            <th>Workbench</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.chapter_id}>
              <td title={row.title ?? row.chapter_id}>{row.chapter_id.replace("-chapter.md", "")}</td>
              <td>{row.prose_overall ?? "—"}</td>
              <td className="muted small">{row.mech ?? "—"}</td>
              <td className={(row.weighted_load ?? 0) > 0 ? "warn-text" : undefined}>
                {row.assessment === "not_assessed" ? "—" : (row.weighted_load ?? "—")}
              </td>
              <td>{row.assessment === "not_assessed" ? "—" : row.confirmed}</td>
              <td>{row.assessment === "not_assessed" ? "—" : row.high}</td>
              <td>{row.unreviewed}</td>
              <td className="muted small">
                {Math.round(row.coverage_mech * 100)}% / {Math.round(row.coverage_sem * 100)}%
              </td>
              <td>
                <Tag tone={row.assessment.startsWith("assessed") ? "accent" : "default"}>
                  {assessmentLabel(row.assessment)}
                </Tag>
              </td>
              <td>
                {row.workbench_link ? (
                  <a className="text-link" href={row.workbench_link} target="_blank" rel="noreferrer">
                    Open <ExternalLink size={12} />
                  </a>
                ) : (
                  <span className="muted small">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Pressure is deterministic screening (candidates); load is confirmed burden (higher means
        more confirmed problems). A chapter with no semantic review shows Not assessed, never a
        healthy zero. Both are independent from prose scores; disagreement between them is useful
        evidence, never merged.
      </p>
    </div>
  );
}

function TechnicalClaimCard({
  claim,
  onReview,
  onCandidates,
}: {
  claim: TechnicalClaim;
  onReview: (findingId: string, decision: string) => void;
  onCandidates: (claimId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showRequirements, setShowRequirements] = useState(false);
  const evidence = useApi<Array<Record<string, any>>>(
    expanded ? `/api/technical/claims/${claim.id}/evidence` : null,
  );
  const verifications = useApi<Array<Record<string, any>>>(
    expanded ? `/api/technical/claims/${claim.id}/verifications` : null,
  );
  const requirements = useApi<TechnicalRequirement[]>(
    showRequirements ? `/api/technical/claims/${claim.id}/requirements` : null,
  );
  return (
    <article className="writer-decision-card" key={claim.id}>
      <div className="writer-decision-head">
        <Tag tone={claim.quote_validated ? "accent" : "danger"}>{claim.claim_type}</Tag>
        <strong>{claim.epistemic_role}</strong>
        <span className="writer-decision-count">
          {claim.quote_validated ? "source-verified" : "quote unverified"} · {claim.extraction_method}
        </span>
      </div>
      <p>{claim.claim_text}</p>
      {claim.qualifications.length ? (
        <p className="muted small">Qualifiers: {claim.qualifications.join(" · ")}</p>
      ) : null}
      <blockquote className="writer-excerpt">{claim.source_excerpt}</blockquote>
      <div className="button-row">
        {(["ACCEPT", "REJECT", "DEFER", "INVESTIGATE"] as const).map((decision) => (
          <button
            key={decision}
            className="button button-secondary button-small"
            onClick={() => onReview(claim.id, decision)}
          >
            {decision}
          </button>
        ))}
        <button className="button button-secondary button-small" onClick={() => onCandidates(claim.id)}>
          Find related claims
        </button>
        <button className="button button-secondary button-small" onClick={() => setShowRequirements((v) => !v)} aria-expanded={showRequirements}>
          {showRequirements ? "Hide requirements" : "Evidence requirements"}
        </button>
        <button className="button button-secondary button-small" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
          {expanded ? "Hide evidence & checks" : "Evidence & checks"}
        </button>
      </div>
      {showRequirements ? (
        <div className="table-wrap">
          {requirements.loading ? <LoadingBlock label="Loading requirements" compact /> : null}
          {(requirements.data ?? []).map((item) => (
            <p key={item.id} className="muted small">
              <strong>{item.label}</strong> · {item.requirement_key} ·{" "}
              <Tag tone={item.applicability === "APPLICABLE" ? "accent" : "default"}>{item.applicability}</Tag>{" "}
              <Tag tone={item.satisfaction === "SATISFIED" ? "accent" : item.satisfaction === "WAIVED_WITH_RATIONALE" ? "default" : "danger"}>
                {item.satisfaction.replace(/_/g, " ")}
              </Tag>
              {item.satisfaction_detail ? ` — ${item.satisfaction_detail.slice(0, 160)}` : ""}
              {item.satisfaction === "WAIVED_WITH_RATIONALE" && item.waived_reason ? (
                <span> Waiver (not fulfillment): {item.waived_reason.slice(0, 200)}</span>
              ) : null}
            </p>
          ))}
          {requirements.data && requirements.data.length === 0 ? (
            <p className="muted small">No evidence requirements derived for this claim yet. Unassessed is not the same as satisfied.</p>
          ) : null}
        </div>
      ) : null}
      {expanded ? (
        <div className="table-wrap">
          {evidence.loading || verifications.loading ? <LoadingBlock label="Loading evidence" compact /> : null}
          {(evidence.data ?? []).map((item) => (
            <p key={String(item.id)} className="muted small">
              <strong>{String(item.evidence_type)}</strong> · {String(item.source_location)} ·{" "}
              {titleCase(String(item.verification_status).toLowerCase().replace(/_/g, " "))}
              {item.limitations ? ` — ${String(item.limitations).slice(0, 140)}` : ""}
            </p>
          ))}
          {(verifications.data ?? []).map((item) => (
            <p key={String(item.id)} className="muted small">
              <Tag tone={String(item.status).includes("CONTRADICTED") ? "danger" : "default"}>{String(item.method)}</Tag>{" "}
              {titleCase(String(item.status).toLowerCase().replace(/_/g, " "))} — {String(item.detail).slice(0, 160)}
              {item.spec_id ? ` · ${String(item.spec_id)}` : ""}
              {item.model_id ? ` · ${String(item.model_id).split("/").pop()}` : ""}
            </p>
          ))}
          {evidence.data && verifications.data && evidence.data.length === 0 && verifications.data.length === 0 ? (
            <p className="muted small">No evidence or checks recorded yet for this claim.</p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function TechnicalPanel({ projectId }: { projectId: string }) {
  const toast = useToast();
  const overview = useApi<Record<string, any>>(`/api/technical/overview?project_id=${projectId}`, { pollMs: 60000 });
  const discovery = useApi<QualityDiscovery[]>(`/api/quality/discovery?project_id=${projectId}`, { pollMs: 60000 });
  const campaigns = useApi<QualityCampaign[]>(`/api/quality/campaigns?project_id=${projectId}`, { pollMs: 15000 });
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("selected");
  const [model, setModel] = useState("opencode-go/deepseek-v4.1-flash");
  const [selected, setSelected] = useState<string[]>(["01-chapter.md", "39-chapter.md", "43-chapter.md"]);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [candidateFor, setCandidateFor] = useState<string | null>(null);

  const techCampaigns = (campaigns.data ?? []).filter((c) => (c.assessment_type ?? "prose") === "technical");
  const active = techCampaigns.find((c) => ["pending", "running", "cancelling"].includes(c.status)) ?? null;

  const assessment = useApi<TechnicalChapterAssessment | null>(
    chapterId ? `/api/technical/chapters/${chapterId}?project_id=${projectId}` : null,
  );
  const candidates = useApi<Array<Record<string, any>>>(
    candidateFor ? `/api/technical/claims/${candidateFor}/candidates` : null,
  );

  async function createCampaign() {
    setBusy(true);
    try {
      const created = await api.post<QualityCampaign>("/api/technical/campaigns", {
        project_id: projectId,
        mode,
        chapters: mode === "selected" ? selected : [],
        model: model || null,
      });
      await api.post(`/api/technical/campaigns/${created.id}/run`);
      toast.push("success", "Technical campaign started", `${created.chapter_selection.length} chapters selected.`);
      campaigns.reload();
    } catch (caught) {
      toast.push("error", "Could not start technical campaign", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submitReview(findingId: string, decision: string) {
    try {
      await api.post("/api/technical/reviews", {
        finding_id: findingId,
        decision,
        reviewer: "author",
        source_digest: assessment.data?.source_revision ?? "",
      });
      toast.push("success", `Recorded ${decision}`, findingId.slice(0, 20));
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    }
  }

  return (
    <>
      <Section
        title="Technical Confidence"
        description="Evidence-backed verification of technical claims. Separate from prose scores; no overall book score is computed."
        actions={
          overview.data ? (
            <Tag tone="accent">
              {overview.data.chapters_with_claims ?? 0} chapters · {overview.data.claims_total ?? 0} claims
            </Tag>
          ) : null
        }
      >
        {overview.error ? <InlineError message={overview.error.message} /> : null}
        {overview.data ? (
          <div className="writer-mini-scores">
            {Object.entries(overview.data.by_status ?? {}).map(([status, count]) => (
              <span key={status} title={status}>
                {titleCase(status.toLowerCase())}: {String(count)}
              </span>
            ))}
            {Object.entries(overview.data.by_method ?? {}).map(([method, count]) => (
              <span key={method} title={`verification method: ${method}`}>
                {method}: {String(count)}
              </span>
            ))}
          </div>
        ) : null}
        {overview.loading ? <LoadingBlock label="Loading technical overview" compact /> : null}
        {!overview.data && !overview.loading ? (
          <p className="muted small">No technical claims recorded yet. Start a campaign below.</p>
        ) : null}
        {overview.data && (overview.data.claims_unresolved ?? 0) > 0 ? (
          <p className="warn-text small">
            {overview.data.claims_unresolved} of {overview.data.claims_total} claims are unresolved, contradicted, or lack supporting evidence.
          </p>
        ) : null}
      </Section>

      <Section
        title="Technical campaign"
        description="Durable per-chapter claim extraction and verification. Progress persists; stop and resume never lose completed chapters."
      >
        {campaigns.error ? <InlineError message={campaigns.error.message} /> : null}
        {active ? (
          <div className="writer-decision-card">
            <div className="writer-decision-head">
              <strong>{active.id.slice(0, 14)} · {active.mode} · technical</strong>
              <span className="writer-decision-count">
                {active.completed} done · {active.failed} failed · {active.remaining} remaining
                {active.current_chapter ? ` · now: ${active.current_chapter}` : ""}
              </span>
              <Tag tone={active.status === "running" ? "accent" : "default"}>{titleCase(active.status)}</Tag>
            </div>
            {active.error ? <p className="warn-text small">{active.error}</p> : null}
            <div className="button-row">
              {["pending", "running"].includes(active.status) ? (
                <button className="button button-secondary button-small" onClick={() => void (async () => {
                  try {
                    await api.post(`/api/quality/campaigns/${active.id}/stop`);
                    campaigns.reload();
                  } catch (caught) {
                    toast.push("error", "Could not stop campaign", errorMessage(caught));
                  }
                })()}>
                  Stop after current chapter
                </button>
              ) : null}
              {["partial", "interrupted", "failed"].includes(active.status) ? (
                <button className="button button-secondary button-small" onClick={() => void (async () => {
                  try {
                    await api.post(`/api/quality/campaigns/${active.id}/resume`);
                    toast.push("success", "Campaign resumed", "Remaining chapters will be assessed.");
                    campaigns.reload();
                  } catch (caught) {
                    toast.push("error", "Could not resume campaign", errorMessage(caught));
                  }
                })()}>
                  Resume remaining chapters
                </button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="inline-form">
            <label className="muted small">
              Mode{" "}
              <select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="Technical campaign mode">
                <option value="missing">Evaluate missing</option>
                <option value="outdated">Evaluate outdated</option>
                <option value="selected">Evaluate selected</option>
                <option value="full">Re-evaluate entire book</option>
              </select>
            </label>
            <label className="muted small">
              Model{" "}
              <input value={model} onChange={(event) => setModel(event.target.value)} aria-label="Technical campaign model" size={32} />
            </label>
            <button className="button button-primary button-small" disabled={busy} onClick={() => void createCampaign()}>
              {busy ? "Starting…" : "Start technical campaign"}
            </button>
          </div>
        )}
        {mode === "selected" && !active ? (
          <div className="table-wrap">
            <p className="muted small">Tick chapters for a targeted run ({selected.length} selected).</p>
            {(discovery.data ?? []).map((row) => (
              <label key={row.chapter_id} className="muted small" style={{ display: "block" }}>
                <input
                  type="checkbox"
                  checked={selected.includes(row.chapter_id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, row.chapter_id]
                        : current.filter((id) => id !== row.chapter_id),
                    )
                  }
                />{" "}
                {row.chapter_id} — {row.title ?? "untitled"}
              </label>
            ))}
          </div>
        ) : null}
      </Section>

      <Section
        title="Chapter technical assessment"
        description="Claims, evidence and verification per chapter. Scores never imply correctness; read the evidence."
      >
        <div className="inline-form">
          <label className="muted small">
            Chapter{" "}
            <select
              value={chapterId ?? ""}
              onChange={(event) => { setChapterId(event.target.value || null); setCandidateFor(null); }}
              aria-label="Assessed chapter"
            >
              <option value="">Select a chapter…</option>
              {(discovery.data ?? []).map((row) => (
                <option key={row.chapter_id} value={row.chapter_id}>
                  {row.chapter_id} — {row.title ?? ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        {assessment.error ? <InlineError message={assessment.error.message} /> : null}
        {assessment.data ? (
          <div className="writer-decision-queue">
            <p className="muted small">
              {assessment.data.claims_total} claims · {assessment.data.claims_source_verified} source-verified ·{" "}
              {assessment.data.claims_unresolved} unresolved · revision {assessment.data.source_revision.slice(0, 12)}
            </p>
            {assessment.data.claims.map((claim) => (
              <TechnicalClaimCard
                key={claim.id}
                claim={claim}
                onReview={(findingId, decision) => void submitReview(findingId, decision)}
                onCandidates={(claimId) => setCandidateFor(claimId)}
              />
            ))}
          </div>
        ) : null}
        {candidateFor ? (
          <div className="table-wrap">
            <p className="muted small">Candidate related claims (shared terminology; compatibility judged separately).</p>
            {candidates.loading ? <LoadingBlock label="Finding related claims" compact /> : null}
            {(candidates.data ?? []).map((cand: Record<string, any>) => (
              <p key={cand.claim_id as string} className="muted small">
                <strong>{cand.chapter_id as string}</strong> — {String(cand.claim_text).slice(0, 140)}…{" "}
                <span>shared: {(cand.shared_terms as string[]).join(", ")}</span>
              </p>
            ))}
            {candidates.data && (candidates.data as unknown[]).length === 0 ? (
              <p className="muted small">No related claims found.</p>
            ) : null}
          </div>
        ) : null}
      </Section>
    </>
  );
}

function CompletenessPanel({ projectId }: { projectId: string }) {
  const toast = useToast();
  const discovery = useApi<QualityDiscovery[]>(`/api/quality/discovery?project_id=${projectId}`, { pollMs: 60000 });
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [gapFilter, setGapFilter] = useState("ALL");

  const completeness = useApi<TechnicalCompleteness | null>(
    chapterId ? `/api/technical/completeness/${chapterId}?project_id=${projectId}` : null,
  );
  const gaps = useApi<TechnicalGap[]>(
    chapterId ? `/api/technical/gaps?project_id=${projectId}&chapter_id=${chapterId}` : null,
  );
  const objectives = useApi<TechnicalObjective[]>(
    chapterId ? `/api/technical/objectives?project_id=${projectId}&chapter_id=${chapterId}` : null,
  );

  async function setGapStatus(gapId: string, status: string) {
    try {
      await api.post(`/api/technical/gaps/${gapId}/status`, { status });
      toast.push("success", `Gap ${status.toLowerCase()}`, gapId.slice(0, 20));
      gaps.reload();
    } catch (caught) {
      toast.push("error", "Could not update gap", errorMessage(caught));
    }
  }

  async function reviewGap(gapId: string, decision: string, reason: string) {
    try {
      await api.post("/api/technical/reviews", {
        finding_id: gapId,
        decision,
        reason,
        reviewer: "author",
        source_digest: completeness.data?.live_revision ?? "",
      });
      toast.push("success", `Recorded ${decision}`, `${gapId.slice(0, 20)} — ${reason}`);
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    }
  }

  const visibleGaps = (gaps.data ?? []).filter((gap) => gapFilter === "ALL" || gap.gap_type === gapFilter);
  const gapTypes = [...new Set((gaps.data ?? []).map((gap) => gap.gap_type))].sort();

  return (
    <>
      <Section
        title="Evidence Completeness"
        description="Coverage accounting, evidence obligations and gap analysis. Separate from prose scores and technical-confidence checks; no overall book score is computed."
        actions={
          completeness.data ? (
            <Tag tone={completeness.data.assessment === "COMPLETE" ? "accent" : "default"}>
              {completeness.data.assessment}
            </Tag>
          ) : null
        }
      >
        <div className="inline-form">
          <label className="muted small">
            Chapter{" "}
            <select
              value={chapterId ?? ""}
              onChange={(event) => { setChapterId(event.target.value || null); setGapFilter("ALL"); }}
              aria-label="Completeness chapter"
            >
              <option value="">Select a chapter…</option>
              {(discovery.data ?? []).map((row) => (
                <option key={row.chapter_id} value={row.chapter_id}>
                  {row.chapter_id} — {row.title ?? ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        {completeness.error ? <InlineError message={completeness.error.message} /> : null}
        {completeness.loading ? <LoadingBlock label="Loading completeness" compact /> : null}
        {!completeness.data && !completeness.loading ? (
          <p className="muted small">
            No chapter selected. Coverage states distinguish examined regions from material not yet examined;
            unexamined text is never treated as claim-free.
          </p>
        ) : null}
        {completeness.data ? (
          <div className="writer-decision-queue">
            <p className="muted small">
              Regions: {completeness.data.regions_processed}/{completeness.data.regions_total} processed ·{" "}
              {completeness.data.regions_capped} capped · {completeness.data.regions_failed} failed ·{" "}
              {completeness.data.regions_not_started} not started · {completeness.data.regions_stale} stale
            </p>
            <p className="muted small">
              Claims: {completeness.data.claims_total} discovered · {completeness.data.claims_source_verified} source-verified ·{" "}
              {completeness.data.claims_stale} stale · Claim recall: UNKNOWN where regions are capped or unprocessed
            </p>
            <p className="muted small">
              Requirements: {completeness.data.requirements_total} ({Object.entries(completeness.data.by_applicability).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(" · ") || "none"})
              {" — "}
              {Object.entries(completeness.data.by_satisfaction).map(([k, v]) => `${v} ${k.toLowerCase().replace(/_/g, " ")}`).join(" · ") || "none assessed"}
            </p>
            <p className="muted small">
              Open gaps: {completeness.data.open_gaps}
              {completeness.data.gap_types.length ? ` (${completeness.data.gap_types.join(", ")})` : ""}
            </p>
            {completeness.data.regions_capped > 0 || completeness.data.regions_not_started > 0 ? (
              <p className="warn-text small">
                Extraction hit a limit or left regions unprocessed. Absence of claims in unexamined regions means nothing;
                a further bounded pass is still eligible.
              </p>
            ) : null}
          </div>
        ) : null}
      </Section>

      {chapterId ? (
        <Section
          title="Chapter objectives"
          description="What the chapter sets out to establish. Inferred objectives are provisional until the author confirms them."
        >
          {objectives.loading ? <LoadingBlock label="Loading objectives" compact /> : null}
          {(objectives.data ?? []).map((objective) => (
            <article className="writer-decision-card" key={objective.id}>
              <div className="writer-decision-head">
                <Tag tone={objective.source === "explicit" ? "accent" : "default"}>{objective.source}</Tag>
                <Tag tone="default">{objective.status}</Tag>
              </div>
              <p>{objective.statement}</p>
            </article>
          ))}
          {objectives.data && objectives.data.length === 0 && !objectives.loading ? (
            <p className="muted small">No objectives recorded for this chapter yet.</p>
          ) : null}
        </Section>
      ) : null}

      {chapterId ? (
        <Section
          title="Evidence gaps"
          description="Missing, partial or unsearched evidence — not technical-defect verdicts. Waived limits stay visible without counting as fulfilled."
        >
          <div className="inline-form">
            <label className="muted small">
              Gap type{" "}
              <select value={gapFilter} onChange={(event) => setGapFilter(event.target.value)} aria-label="Gap type filter">
                <option value="ALL">All ({(gaps.data ?? []).length})</option>
                {gapTypes.map((type) => (
                  <option key={type} value={type}>
                    {type} ({(gaps.data ?? []).filter((gap) => gap.gap_type === type).length})
                  </option>
                ))}
              </select>
            </label>
          </div>
          {gaps.error ? <InlineError message={gaps.error.message} /> : null}
          {gaps.loading ? <LoadingBlock label="Loading gaps" compact /> : null}
          <div className="writer-decision-queue">
            {visibleGaps.map((gap) => (
              <article className="writer-decision-card" key={gap.id}>
                <div className="writer-decision-head">
                  <Tag tone={gap.status === "OPEN" ? "danger" : "default"}>{gap.gap_type}</Tag>
                  <span className="writer-decision-count">{gap.status}</span>
                </div>
                <p>{gap.title}</p>
                {gap.detail ? <p className="muted small">{gap.detail.slice(0, 400)}</p> : null}
                {gap.searched_scope ? (
                  <p className="muted small">Searched scope: {gap.searched_scope}</p>
                ) : null}
                {gap.priority_rationale ? (
                  <p className="muted small">Priority: {gap.priority_rationale.slice(0, 200)}</p>
                ) : null}
                <div className="button-row">
                  {(
                    [
                      ["OBTAIN EVIDENCE", "INVESTIGATE"],
                      ["RECHECK SOURCE", "INVESTIGATE"],
                      ["EXPAND CONTEXT", "INVESTIGATE"],
                      ["QUALIFY CLAIM", "INVESTIGATE"],
                      ["ACCEPT LIMITATION", "ACCEPT"],
                      ["DISMISS REQUIREMENT", "REJECT"],
                      ["DEFER", "DEFER"],
                    ] as const
                  ).map(([action, decision]) => (
                    <button
                      key={action}
                      className="button button-secondary button-small"
                      title={
                        action === "QUALIFY CLAIM"
                          ? "Records an editorial proposal; never modifies the claim"
                          : action === "ACCEPT LIMITATION"
                            ? "Stays visible; never counted as fulfilled"
                            : action
                      }
                      onClick={() => void reviewGap(gap.id, decision, action)}
                    >
                      {titleCase(action.toLowerCase())}
                    </button>
                  ))}
                  {gap.status === "OPEN" ? (
                    <button className="button button-secondary button-small" onClick={() => void setGapStatus(gap.id, "RESOLVED")}>
                      Resolve
                    </button>
                  ) : (
                    <button className="button button-secondary button-small" onClick={() => void setGapStatus(gap.id, "OPEN")}>
                      Reopen
                    </button>
                  )}
                </div>
              </article>
            ))}
            {gaps.data && visibleGaps.length === 0 && !gaps.loading ? (
              <p className="muted small">No gaps in this filter. No gaps shown is not proof of completeness — check coverage above.</p>
            ) : null}
          </div>
        </Section>
      ) : null}
    </>
  );
}

type PublicationGate = {
  id: string;
  gate_id: string;
  gate_version: number;
  gate_group: string;
  result: string;
  blocking: boolean;
  waivable: boolean;
  detail: string;
  evidence_refs: string[];
  limitations: string;
  created_at: string;
};

type PublicationIssue = {
  id: string;
  gate_id: string;
  issue_type: string;
  severity: string;
  verification_method: string;
  status: string;
  waiver_eligibility: string;
  author_review_status: string;
  source_refs: string[];
  evidence_refs: string[];
  rationale: string;
  created_at: string;
};

type PublicationApproval = {
  id: string;
  assessment_id: string;
  decision: string;
  rationale: string;
  manuscript_fingerprint: string;
  input_manifest_fingerprint: string;
  policy_version: string;
  accepted_limitation_ids: string[];
  freshness: string;
  reviewer: string;
  created_at: string;
};

type PublicationAssessment = {
  id: string;
  project_id: string | null;
  book_id: string;
  book_root: string;
  policy_version: string;
  technical_scope: string;
  manuscript_fingerprint: string;
  input_manifest_fingerprint: string;
  chapter_count: number;
  assessment_status: string;
  freshness: string;
  readiness_detail: string;
  preflight_id: string | null;
  gates: PublicationGate[];
  issues: PublicationIssue[];
  approvals: PublicationApproval[];
  created_at: string;
};

type CalibrationRun = {
  run_id: string;
  contract: string;
  sample_version: number;
  kind: string;
  sampled?: number;
  reviewed?: number;
  arm_A_target?: number;
  arm_B_target?: number;
  awaiting?: number;
  states?: Record<string, number>;
  disagreements?: number;
  seed?: number;
  provenance?: string;
  note?: string;
};

type CalibrationPacket = {
  calibration_case_id: string;
  sampling_arm: string;
  sample_reason: string;
  run_id: string;
  requirement_id: string;
  claim_id: string;
  book_id: string;
  chapter_id: string;
  source_revision: string;
  live_chapter_revision: string;
  claim_type: string;
  epistemic_role: string;
  claim_text: string;
  qualifications: string[];
  exact_manuscript_excerpt: string;
  surrounding_source_context: { text: string; char_span: [number, number]; excerpt_offset_in_context: [number, number] };
  requirement_template: string;
  requirement_type: string;
  requirement_description: string;
  requirement_acceptance_rule: string;
  current_applicability: string;
  applicability_reason: string;
  current_satisfaction: string;
  satisfaction_detail: string;
  existing_evidence: Array<Record<string, unknown>>;
  existing_verification_results: Array<Record<string, unknown>>;
  existing_gap: Array<Record<string, unknown>>;
  current_priority: string;
  integrity: Record<string, unknown>;
  review_state: string;
};

type CalibrationReview = {
  id: string;
  requirement_id: string | null;
  sample_version: number;
  sample_reason: string;
  claim_accurate: boolean;
  requirement_applicable: string;
  necessary: boolean;
  strictness_ok: boolean;
  satisfied_by_evidence: string;
  gap_justified: boolean;
  priority_proportionate: boolean;
  would_block: boolean;
  qualification_sufficient: boolean;
  duplicate_of: string;
  verdict: string;
  correction: string;
  reviewer: string;
  created_at: string;
};

function ReadinessPanel({ projectId }: { projectId: string }) {
  const toast = useToast();
  const assessments = useApi<PublicationAssessment[]>(`/api/publication/assessments?project_id=${projectId}`, { pollMs: 30000 });
  const calibration = useApi<Record<string, unknown>>("/api/publication/calibration/summary", { pollMs: 60000 });
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rationale, setRationale] = useState("");

  const selected = (assessments.data ?? []).find((a) => a.id === assessmentId)
    ?? (assessments.data ?? [])[0]
    ?? null;

  async function createAssessment(force: boolean) {
    setBusy(true);
    try {
      const created = await api.post<PublicationAssessment>(
        `/api/publication/assessments${force ? "?force=true" : ""}`,
        { project_id: projectId, technical_scope: "pilot" },
      );
      toast.push("success", "Release assessment created", `${created.id} · ${created.assessment_status}`);
      setAssessmentId(created.id);
      assessments.reload();
    } catch (caught) {
      toast.push("error", "Could not create assessment", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function refreshAssessment() {
    if (!selected) return;
    try {
      await api.post(`/api/publication/assessments/${selected.id}/refresh`, {});
      toast.push("success", "Freshness recomputed", selected.id.slice(0, 20));
      assessments.reload();
    } catch (caught) {
      toast.push("error", "Could not refresh assessment", errorMessage(caught));
    }
  }

  async function reviewIssue(issueId: string, decision: string) {
    try {
      await api.post(`/api/publication/issues/${issueId}/review`, {
        decision, rationale: rationale || undefined, reviewer: "author",
      });
      toast.push("success", `Recorded ${decision}`, issueId.slice(0, 20));
      assessments.reload();
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    }
  }

  async function approve(decision: string) {
    if (!selected) return;
    try {
      const accepted = (selected.issues ?? [])
        .filter((i) => i.author_review_status === "accepted_limitation")
        .map((i) => i.id);
      await api.post("/api/publication/approvals", {
        assessment_id: selected.id, decision, rationale, accepted_limitation_ids: accepted, reviewer: "author",
      });
      toast.push("success", `Recorded ${decision}`, selected.id.slice(0, 20));
      setRationale("");
      assessments.reload();
    } catch (caught) {
      toast.push("error", "Could not record approval", errorMessage(caught));
    }
  }

  const blockers = (selected?.issues ?? []).filter((i) => i.severity === "blocker" && i.status === "OPEN");
  const unknowns = (selected?.issues ?? []).filter((i) => i.severity === "unknown" && i.status === "OPEN");
  const latestApproval = (selected?.approvals ?? []).filter((a) => a.decision === "APPROVE_RELEASE_CANDIDATE").slice(-1)[0] ?? null;

  return (
    <>
      <Section
        title="Publication Readiness"
        description="Release decision for one exact manuscript snapshot under a versioned policy. Never an average of the other pillars; a missing check is never a passed check."
        actions={
          selected ? (
            <Tag tone={selected.assessment_status === "READY" ? "accent" : selected.assessment_status === "BLOCKED" ? "danger" : "default"}>
              {selected.assessment_status}
            </Tag>
          ) : null
        }
      >
        <div className="inline-form">
          <label className="muted small">
            Release candidate{" "}
            <select
              value={selected?.id ?? ""}
              onChange={(event) => setAssessmentId(event.target.value || null)}
              aria-label="Release candidate"
            >
              <option value="">Latest</option>
              {(assessments.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.id.slice(0, 14)} — {a.assessment_status} ({a.freshness})
                </option>
              ))}
            </select>
          </label>
          <button className="button button-primary button-small" disabled={busy} onClick={() => void createAssessment(false)}>
            {busy ? "Assessing…" : "New release assessment"}
          </button>
          <button className="button button-secondary button-small" disabled={!selected || busy} onClick={() => void createAssessment(true)}>
            Reassess
          </button>
        </div>
        {assessments.error ? <InlineError message={assessments.error.message} /> : null}
        {assessments.loading ? <LoadingBlock label="Loading release assessments" compact /> : null}
        {!selected && !assessments.loading ? (
          <p className="muted small">
            No release assessment yet. An assessment binds the current source snapshot, the Workbench preflight,
            a production build check and the three evidence pillars under policy publication-readiness-v1.
          </p>
        ) : null}
        {selected ? (
          <div className="writer-decision-queue">
            <p className="muted small">
              Snapshot {selected.manuscript_fingerprint.slice(0, 12)} · {selected.chapter_count} chapters ·{" "}
              policy {selected.policy_version} · scope {selected.technical_scope} · freshness {selected.freshness}
            </p>
            <p className="muted small">{selected.readiness_detail}</p>
            {selected.freshness === "STALE" ? (
              <p className="warn-text small">
                Source or evidence changed since this assessment. Gate results are no longer current.{" "}
                <button className="button button-secondary button-small" onClick={() => void refreshAssessment()}>
                  Recompute freshness
                </button>
              </p>
            ) : null}
            {blockers.length > 0 ? (
              <p className="warn-text small">
                {blockers.length} confirmed blocker(s). Resolve them before any approval can be recorded.
              </p>
            ) : null}
            {unknowns.length > 0 ? (
              <p className="warn-text small">
                {unknowns.length} mandatory check(s) still unknown — shown separately from blockers, hidden by neither.
              </p>
            ) : null}
          </div>
        ) : null}
      </Section>

      {selected ? (
        <Section
          title="Release gates"
          description="One result per gate with evidence references. Drill down for the acceptance rule and limitations."
        >
          <div className="writer-decision-queue">
            {selected.gates.map((gate) => (
              <details className="writer-decision-card" key={gate.id}>
                <summary className="writer-decision-head">
                  <Tag tone={gate.result === "PASS" ? "accent" : gate.result === "FAIL" ? "danger" : "default"}>{gate.result}</Tag>
                  <strong>{gate.gate_id}</strong>
                  <span className="writer-decision-count">
                    {gate.gate_group}{gate.blocking ? " · blocking" : ""}{gate.waivable ? " · waivable" : " · nonwaivable"}
                  </span>
                </summary>
                <p className="muted small">{gate.detail}</p>
                {gate.limitations ? <p className="muted small">Limits: {gate.limitations}</p> : null}
                {gate.evidence_refs.length ? (
                  <p className="muted small">Evidence: {gate.evidence_refs.slice(0, 8).join(" · ")}{gate.evidence_refs.length > 8 ? " · …" : ""}</p>
                ) : null}
              </details>
            ))}
          </div>
        </Section>
      ) : null}

      {selected && selected.issues.length ? (
        <Section
          title="Confirmed blockers and unknowns"
          description="Blocking classification comes from gate policy and verified facts. Waived limits stay visible without counting as fulfilled."
        >
          <div className="writer-decision-queue">
            {selected.issues.map((issue) => (
              <article className="writer-decision-card" key={issue.id}>
                <div className="writer-decision-head">
                  <Tag tone={issue.severity === "blocker" ? "danger" : "default"}>{issue.issue_type}</Tag>
                  <span className="writer-decision-count">{issue.status} · {issue.author_review_status.replace(/_/g, " ")}</span>
                </div>
                <p className="muted small">[{issue.gate_id}] {issue.rationale.slice(0, 400)}</p>
                <div className="button-row">
                  {["ACCEPT FINDING", "REJECT FINDING", "DEFER", "ACCEPT LIMITATION", "REQUEST RECHECK"].map((decision) => (
                    <button
                      key={decision}
                      className="button button-secondary button-small"
                      disabled={issue.status !== "OPEN" && decision !== "REQUEST RECHECK"}
                      title={
                        decision === "ACCEPT LIMITATION"
                          ? issue.waiver_eligibility === "waivable"
                            ? "Stays visible; never counted as fulfilled"
                            : "Not waivable"
                          : decision
                      }
                      onClick={() => void reviewIssue(issue.id, decision)}
                    >
                      {titleCase(decision.toLowerCase())}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </Section>
      ) : null}

      {selected ? (
        <Section
          title="Author approval"
          description="Approval binds one exact snapshot and policy version. It is not deployment and never carries across snapshots."
        >
          {latestApproval && latestApproval.freshness === "CURRENT" ? (
            <p className="muted small">
              Approved by {latestApproval.reviewer || "author"} at {latestApproval.created_at} — {latestApproval.rationale || "no rationale recorded"}
            </p>
          ) : (
            <p className="muted small">No current approval for this snapshot. A verified but unapproved candidate is not authorized.</p>
          )}
          <div className="inline-form">
            <label className="muted small">
              Rationale{" "}
              <input
                value={rationale}
                onChange={(event) => setRationale(event.target.value)}
                aria-label="Approval rationale"
                size={40}
                placeholder="Why is this snapshot releasable?"
              />
            </label>
            <button className="button button-primary button-small" onClick={() => void approve("APPROVE_RELEASE_CANDIDATE")}>
              Approve release candidate
            </button>
            <button className="button button-secondary button-small" onClick={() => void approve("REVOKE_APPROVAL")}>
              Revoke approval
            </button>
          </div>
          <p className="muted small">
            <a className="text-link" href={`/api/publication/assessments/${selected.id}/dossier.zip`}>Download dossier (zip)</a>
            {" · "}
            <a className="text-link" href={`/api/publication/assessments/${selected.id}/dossier.md`} target="_blank" rel="noreferrer">Readiness report (markdown)</a>
          </p>
        </Section>
      ) : null}

      <Section
        title="Requirement calibration"
        description="Human review of the 03C evidence-requirement sample. Unconfirmed priorities are advisory only and can never block."
      >
        {calibration.data ? (
          <p className="muted small">
            Reviewed {String(calibration.data.reviewed ?? 0)} of 475 obligations ·{" "}
            applicable {String(calibration.data.applicable ?? 0)} · false-positive obligations{" "}
            {String(calibration.data.false_positive_obligations ?? 0)} · would block{" "}
            {String(calibration.data.would_block ?? 0)}
          </p>
        ) : (
          <p className="muted small">Calibration evidence loads with the release assessments.</p>
        )}
      </Section>
    </>
  );
}

function provenanceOf(reviewer: string): string {
  if (reviewer === "deterministic") return "DETERMINISTIC";
  if (reviewer === "ai_assisted" || reviewer === "ai_assisted:secondary" || reviewer === "ai_assisted:adjudicator") return "AI-ASSISTED";
  if (reviewer.startsWith("human:")) return "HUMAN";
  return "AWAITING";
}

function CalibrationReviewCard({ packet, existing, onSaved }: {
  packet: CalibrationPacket;
  existing: CalibrationReview[];
  onSaved: () => void;
}) {
  const toast = useToast();
  const [claimAccurate, setClaimAccurate] = useState("VALID");
  const [applicability, setApplicability] = useState("APPLICABLE");
  const [necessity, setNecessity] = useState("REQUIRED");
  const [epistemic, setEpistemic] = useState("OK");
  const [relevance, setRelevance] = useState("unknown");
  const [independence, setIndependence] = useState("unknown");
  const [satisfaction, setSatisfaction] = useState("unknown");
  const [gapJustified, setGapJustified] = useState("unknown");
  const [gapCorrection, setGapCorrection] = useState("");
  const [priority, setPriority] = useState("proportionate");
  const [blocking, setBlocking] = useState("advisory");
  const [qualsOk, setQualsOk] = useState(true);
  const [duplicateOf, setDuplicateOf] = useState("");
  const [summary, setSummary] = useState("");
  const [reviewer, setReviewer] = useState("human:author");

  async function submit(state: "completed" | "draft" | "deferred" | "abstained") {
    const r1 = claimAccurate === "VALID" ? "R1:VALID" : claimAccurate === "PARTIAL" ? "R1:PARTIAL" : "R1:INVALID";
    const verdictCore = `${r1} R2:${applicability} R3:${necessity} R4:${epistemic} R5:${relevance} R6:${independence} R7:${satisfaction} R8:${gapJustified} R9:${priority} R10:${blocking} | ${summary}`.slice(0, 900);
    const verdict = state === "completed" ? verdictCore : `${state.toUpperCase()}: ${verdictCore}`;
    const correction = [
      gapCorrection ? `gap_correction:${gapCorrection}` : "",
      duplicateOf ? `duplicate_of:${duplicateOf}` : "",
    ].filter(Boolean).join(" ").slice(0, 900);
    try {
      await api.post("/api/publication/calibration", {
        requirement_id: packet.requirement_id,
        sample_version: 2,
        sample_reason: `run:CAL04A02-20261112|${packet.sampling_arm === "A" ? "A" : `B:${packet.sample_reason}`}`,
        claim_accurate: claimAccurate !== "INVALID",
        requirement_applicable: applicability,
        necessary: necessity === "REQUIRED",
        strictness_ok: epistemic === "OK",
        satisfied_by_evidence: satisfaction,
        gap_justified: gapJustified === "justified",
        priority_proportionate: priority === "proportionate",
        would_block: blocking === "blocker-candidate",
        qualification_sufficient: qualsOk,
        duplicate_of: duplicateOf,
        verdict,
        correction,
        reviewer,
      });
      toast.push("success", `Review ${state}`, packet.calibration_case_id);
      onSaved();
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    }
  }

  const integrity = packet.integrity as Record<string, unknown>;
  return (
    <article className="writer-decision-card" key={packet.calibration_case_id}>
      <div className="writer-decision-head">
        <Tag tone={packet.sampling_arm === "A" ? "accent" : "default"}>{packet.sampling_arm}</Tag>
        <strong>{packet.calibration_case_id} · {packet.requirement_template}</strong>
        <span className="writer-decision-count">
          {packet.current_applicability} · {packet.current_satisfaction}
          {integrity["stale_or_missing"] ? " · STALE SOURCE" : ""}
        </span>
      </div>
      <p className="muted small"><strong>Claim</strong> [{packet.claim_type}/{packet.epistemic_role}] {packet.chapter_id}: {packet.claim_text.slice(0, 300)}</p>
      <blockquote className="writer-excerpt">{packet.exact_manuscript_excerpt.slice(0, 400)}</blockquote>
      {packet.surrounding_source_context.text ? (
        <details><summary className="muted small">Surrounding source context ({packet.surrounding_source_context.char_span[1] - packet.surrounding_source_context.char_span[0]} chars)</summary>
          <p className="muted small">{String(packet.surrounding_source_context.text).slice(0, 1200)}</p>
        </details>
      ) : <p className="warn-text small">No source context: excerpt could not be anchored. Do not review as verified.</p>}
      <p className="muted small"><strong>Requirement</strong> ({packet.requirement_type}): {packet.requirement_description} Acceptance: {packet.requirement_acceptance_rule.slice(0, 200)}</p>
      <p className="muted small"><strong>System verdict</strong>: applicability {packet.applicability_reason.slice(0, 120)} · satisfaction: {packet.satisfaction_detail || packet.current_satisfaction}</p>
      {(packet.existing_gap as Array<Record<string, unknown>>).map((g) => (
        <p key={String(g["id"])} className="muted small">
          Gap <Tag tone={String(g["status"]) === "OPEN" ? "danger" : "default"}>{String(g["gap_type"])}</Tag> {String(g["priority_rationale"])} — {String(g["title"]).slice(0, 140)}
        </p>
      ))}
      {existing.length ? (
        <p className="muted small">Prior reviews: {existing.map((r) => `${provenanceOf(r.reviewer)}:${r.verdict.slice(0, 60)}`).join(" | ").slice(0, 300)}</p>
      ) : null}
      <div className="inline-form">
        <label className="muted small">R1 fidelity <select value={claimAccurate} onChange={(e) => setClaimAccurate(e.target.value)} aria-label="R1 claim fidelity"><option>VALID</option><option>PARTIAL</option><option>INVALID</option></select></label>
        <label className="muted small">R2 applicable <select value={applicability} onChange={(e) => setApplicability(e.target.value)} aria-label="R2 applicability"><option>APPLICABLE</option><option>NOT_APPLICABLE</option><option>UNDETERMINED</option></select></label>
        <label className="muted small">R3 necessary <select value={necessity} onChange={(e) => setNecessity(e.target.value)} aria-label="R3 necessity"><option>REQUIRED</option><option>OPTIONAL</option><option>REDUNDANT</option><option>UNJUSTIFIED</option><option>UNDETERMINED</option></select></label>
        <label className="muted small">R4 epistemic <select value={epistemic} onChange={(e) => setEpistemic(e.target.value)} aria-label="R4 epistemic fit"><option>OK</option><option>MISMATCH</option></select></label>
        <label className="muted small">R5 relevance <select value={relevance} onChange={(e) => setRelevance(e.target.value)} aria-label="R5 evidence relevance"><option value="unknown">unknown</option><option value="direct">direct</option><option value="partial">partial</option><option value="contextual">contextual</option><option value="unrelated">unrelated</option><option value="none">none</option></select></label>
        <label className="muted small">R6 independence <select value={independence} onChange={(e) => setIndependence(e.target.value)} aria-label="R6 evidence independence"><option value="unknown">unknown</option><option value="independent">independent</option><option value="restates">restates</option><option value="shared">shared</option><option value="circular">circular</option><option value="none">none</option></select></label>
        <label className="muted small">R7 satisfied <select value={satisfaction} onChange={(e) => setSatisfaction(e.target.value)} aria-label="R7 satisfaction"><option value="unknown">unknown</option><option value="yes">yes</option><option value="no">no</option><option value="partial">partial</option><option value="waived">waived</option></select></label>
        <label className="muted small">R8 gap <select value={gapJustified} onChange={(e) => setGapJustified(e.target.value)} aria-label="R8 gap classification"><option value="justified">justified</option><option value="misclassified">misclassified</option></select></label>
        <input value={gapCorrection} onChange={(e) => setGapCorrection(e.target.value)} aria-label="Gap correction type" placeholder="correct gap type if misclassified" size={24} />
        <label className="muted small">R9 priority <select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="R9 priority"><option value="proportionate">proportionate</option><option value="inflated">inflated</option><option value="deflated">deflated</option></select></label>
        <label className="muted small">R10 blocking <select value={blocking} onChange={(e) => setBlocking(e.target.value)} aria-label="R10 blocking potential"><option value="advisory">advisory</option><option value="blocker-candidate">blocker-candidate</option><option value="policy-decision">policy-decision</option><option value="na">na</option><option value="undetermined">undetermined</option></select></label>
        <label className="muted small"><input type="checkbox" checked={qualsOk} onChange={(e) => setQualsOk(e.target.checked)} /> qualifications preserved</label>
        <label className="muted small">Reviewer <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} aria-label="Reviewer identity" size={18} /></label>
      </div>
      <div className="inline-form">
        <input value={summary} onChange={(e) => setSummary(e.target.value)} aria-label="Review summary" placeholder="One-line verdict summary" size={50} />
      </div>
      <div className="button-row">
        <button className="button button-primary button-small" onClick={() => void submit("completed")}>Submit completed review</button>
        <button className="button button-secondary button-small" onClick={() => void submit("draft")}>Save draft</button>
        <button className="button button-secondary button-small" onClick={() => void submit("deferred")}>Defer</button>
        <button className="button button-secondary button-small" onClick={() => void submit("abstained")}>Abstain</button>
      </div>
    </article>
  );
}

function CalibrationPanel({ projectId }: { projectId: string }) {
  void projectId;
  const toast = useToast();
  const runs = useApi<CalibrationRun[]>("/api/publication/calibration/runs", { pollMs: 60000 });
  const sample = useApi<Record<string, unknown>>("/api/publication/calibration/sample", { pollMs: 60000 });
  const stats = useApi<Record<string, unknown>>("/api/publication/calibration/stats", { pollMs: 60000 });
  const reviews = useApi<CalibrationReview[]>("/api/publication/calibration", { pollMs: 30000 });
  const [arm, setArm] = useState("ALL");
  const [chapter, setChapter] = useState("ALL");
  const [template, setTemplate] = useState("ALL");
  const [state, setState] = useState("ALL");
  const [visible, setVisible] = useState(10);

  const packets = useApi<{ count: number; packets: CalibrationPacket[] }>(
    arm === "ALL" ? "/api/publication/calibration/packets?limit=140" : `/api/publication/calibration/packets?arm=${arm}&limit=140`,
  );

  async function refresh() {
    reviews.reload();
    stats.reload();
    packets.reload();
    toast.push("success", "Calibration reloaded", "Latest reviews and stats.");
  }

  const reviewedIds = new Set((reviews.data ?? []).filter((r) => !(r.verdict.startsWith("DRAFT:") || r.verdict.startsWith("DEFERRED:") || r.verdict.startsWith("ABSTAINED:") || !r.verdict.trim())).map((r) => r.requirement_id));
  const chapters = [...new Set((packets.data?.packets ?? []).map((p) => p.chapter_id))].sort();
  const templates = [...new Set((packets.data?.packets ?? []).map((p) => p.requirement_template))].sort();
  const filtered = (packets.data?.packets ?? []).filter((p) =>
    (chapter === "ALL" || p.chapter_id === chapter) &&
    (template === "ALL" || p.requirement_template === template) &&
    (state === "ALL" ||
      (state === "awaiting" && !reviewedIds.has(p.requirement_id)) ||
      (state === "reviewed" && reviewedIds.has(p.requirement_id)) ||
      (state === "integrity-flag" && p.integrity["stale_or_missing"])),
  );

  return (
    <>
      <Section
        title="Calibration"
        description="Evidence-requirement qualification: sampled obligations, source-grounded packets, explicit reviewer provenance. Provisional machine analysis is never ground truth."
      >
        {runs.error ? <InlineError message={runs.error.message} /> : null}
        {(runs.data ?? []).map((run) => (
          <p key={run.run_id} className="muted small">
            <strong>{run.run_id}</strong> ({run.kind}) — sampled {String(run.sampled ?? run.arm_A_target ?? 0)}
            {run.arm_B_target ? `+${String(run.arm_B_target)}` : ""} · reviewed {String(run.reviewed ?? 0)}
            {run.awaiting !== undefined ? ` · awaiting ${String(run.awaiting)}` : ""} · disagreements {String(run.disagreements ?? 0)}
            {run.seed !== undefined ? ` · seed ${String(run.seed)}` : ""}
          </p>
        ))}
        {stats.data ? (
          <p className="muted small">
            Human completed: {String((stats.data["human_completed"] as number) ?? 0)} ·
            AI-assisted: {String((stats.data["ai_assisted_completed"] as number) ?? 0)} ·
            deterministic: {String((stats.data["deterministic_completed"] as number) ?? 0)} ·
            agreement measured on independent dual reviews only (NOT_MEASURED until available)
          </p>
        ) : null}
        <div className="button-row">
          <button className="button button-secondary button-small" onClick={() => void refresh()}>Reload calibration</button>
        </div>
      </Section>

      <Section
        title="Calibration review queue"
        description="R1–R10 rubric per packet. Drafts, deferrals and abstentions are recorded, never silently completed."
      >
        <div className="inline-form">
          <label className="muted small">Arm <select value={arm} onChange={(e) => { setArm(e.target.value); setVisible(10); }} aria-label="Sampling arm"><option value="ALL">All</option><option value="A">A (probability)</option><option value="B">B (diagnostic)</option></select></label>
          <label className="muted small">Chapter <select value={chapter} onChange={(e) => { setChapter(e.target.value); setVisible(10); }} aria-label="Calibration chapter"><option value="ALL">All</option>{chapters.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
          <label className="muted small">Template <select value={template} onChange={(e) => { setTemplate(e.target.value); setVisible(10); }} aria-label="Requirement template"><option value="ALL">All</option>{templates.map((t) => <option key={t} value={t}>{t}</option>)}</select></label>
          <label className="muted small">State <select value={state} onChange={(e) => { setState(e.target.value); setVisible(10); }} aria-label="Review state"><option value="ALL">All</option><option value="awaiting">Awaiting</option><option value="reviewed">Reviewed</option><option value="integrity-flag">Integrity flag</option></select></label>
        </div>
        {packets.error ? <InlineError message={packets.error.message} /> : null}
        {packets.loading ? <LoadingBlock label="Loading review packets" compact /> : null}
        <div className="writer-decision-queue">
          {filtered.slice(0, visible).map((packet) => (
            <CalibrationReviewCard
              key={packet.calibration_case_id}
              packet={packet}
              existing={(reviews.data ?? []).filter((r) => r.requirement_id === packet.requirement_id)}
              onSaved={() => { reviews.reload(); stats.reload(); }}
            />
          ))}
        </div>
        {filtered.length > visible ? (
          <button className="button button-secondary button-small" onClick={() => setVisible((v) => v + 10)}>
            Show more ({filtered.length - visible} remaining)
          </button>
        ) : null}
        {packets.data && filtered.length === 0 && !packets.loading ? (
          <p className="muted small">No packets match these filters. Unreviewed packets stay awaiting — never counted as reviewed.</p>
        ) : null}
      </Section>
    </>
  );
}

function QualityPanel({ projectId }: { projectId: string }) {
  const toast = useToast();
  const quality = useApi<QualityWorkspace>(`/api/quality/workspace?project_id=${projectId}`, { pollMs: 60000 });
  const discovery = useApi<QualityDiscovery[]>(`/api/quality/discovery?project_id=${projectId}`, { pollMs: 60000 });
  const writer = useApi<WriterWorkspace>("/api/writer/books", { pollMs: 60000 });
  const campaigns = useApi<QualityCampaign[]>(`/api/quality/campaigns?project_id=${projectId}`, { pollMs: 15000 });
  const artifactLoad = useApi<ArtifactLoadWorkspace>(`/api/artifact-load/workspace?project_id=${projectId}`, { pollMs: 60000 });
  const [campaignBusy, setCampaignBusy] = useState(false);
  const [campaignMode, setCampaignMode] = useState("missing");
  const [campaignModel, setCampaignModel] = useState("opencode-go/deepseek-v4.1-flash");
  const [campaignStrategy, setCampaignStrategy] = useState("direct");
  const [selectedChapters, setSelectedChapters] = useState<string[]>([]);

  const writerFindings = (writer.data?.decision_queue ?? []).filter(
    (item) => item.project_id === projectId,
  );

  const evalByChapter = new Map((quality.data?.chapters ?? []).map((c) => [c.chapter_id, c]));
  const mapRows: MapRow[] = (discovery.data ?? []).map((d) => {
    const current = evalByChapter.get(d.chapter_id)?.current ?? null;
    return {
      chapter_id: d.chapter_id,
      title: d.title,
      dims: current
        ? Object.fromEntries(QUALITY_DIMENSIONS.map((dim) => [dim, current.dimensions[dim]?.score ?? null]))
        : null,
      model: current?.actual_model ?? null,
      state: current ? current.derived_state : d.eligibility === "missing" ? "not run" : d.eligibility,
      revision: d.revision,
    };
  });
  const currentEvals = (quality.data?.chapters ?? [])
    .map((c) => c.current)
    .filter((e): e is QualityEvaluation => e !== null && e !== undefined);
  const distinctModels = [...new Set(currentEvals.map((e) => e.actual_model ?? "unknown"))];
  const comparableNote =
    distinctModels.length <= 1
      ? `Comparable basis: ${distinctModels[0] ?? "no model"} · rubric manuscript-prose-v1 · ${currentEvals.length} observations.`
      : `Descriptive only: ${currentEvals.length} observations across mixed models (${distinctModels.join(", ")}); not a controlled comparison.`;

  function mean(values: number[]): number | null {
    if (!values.length) return null;
    return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100) / 100;
  }
  function median(values: number[]): number | string {
    const sorted = [...values].sort((a, b) => a - b);
    if (!sorted.length) return "—";
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  const activeCampaign = (campaigns.data ?? []).find((c) => ["pending", "running", "cancelling"].includes(c.status)) ?? null;
  const pastCampaigns = (campaigns.data ?? []).filter((c) => !["pending", "running", "cancelling"].includes(c.status));

  async function createCampaign(mode: string, chapters?: string[]) {
    setCampaignBusy(true);
    try {
      const created = await api.post<QualityCampaign>("/api/quality/campaigns", {
        project_id: projectId,
        mode,
        chapters: chapters ?? [],
        model: campaignModel || null,
        strategy: campaignStrategy,
      });
      await api.post(`/api/quality/campaigns/${created.id}/run`);
      toast.push("success", "Evaluation campaign started", `${created.chapter_selection.length} chapters selected.`);
      campaigns.reload();
      discovery.reload();
    } catch (caught) {
      toast.push("error", "Could not start campaign", errorMessage(caught));
    } finally {
      setCampaignBusy(false);
    }
  }

  async function stopCampaign(id: string) {
    try {
      await api.post(`/api/quality/campaigns/${id}/stop`);
      campaigns.reload();
    } catch (caught) {
      toast.push("error", "Could not stop campaign", errorMessage(caught));
    }
  }

  async function resumeCampaign(id: string) {
    try {
      await api.post(`/api/quality/campaigns/${id}/resume`);
      toast.push("success", "Campaign resumed", "Remaining chapters will be evaluated; completed work is kept.");
      campaigns.reload();
    } catch (caught) {
      toast.push("error", "Could not resume campaign", errorMessage(caught));
    }
  }

  const priorities: Array<{ title: string; detail: string; chapter_id: string | null }> = [];
  for (const chapter of quality.data?.chapters ?? []) {
    if (chapter.current?.dimensions) {
      for (const dim of QUALITY_DIMENSIONS) {
        const entry = chapter.current.dimensions[dim];
        if (entry && entry.score <= 3 && entry.evidence_validated) {
          priorities.push({
            title: `${chapter.chapter_id}: ${dim} ${entry.score}/5 with verified evidence`,
            detail: entry.evidence,
            chapter_id: chapter.chapter_id,
          });
        }
      }
    }
    for (const item of [...chapter.evaluations, ...chapter.sections]) {
      for (const [dim, entry] of Object.entries(item.dimensions ?? {})) {
        if (entry && !entry.evidence_validated && entry.evidence && entry.evidence !== "none") {
          priorities.push({
            title: `${chapter.chapter_id}: unverified ${dim} quotation`,
            detail: String(entry.evidence).slice(0, 120),
            chapter_id: chapter.chapter_id,
          });
        }
      }
    }
  }
  for (const row of discovery.data ?? []) {
    if (row.eligibility === "stale") {
      priorities.push({
        title: `${row.chapter_id}: source changed since evaluation`,
        detail: `Current revision ${row.revision.slice(0, 12)} no longer matches the evaluated source.`,
        chapter_id: row.chapter_id,
      });
    }
  }

  return (
    <>
      <Section
        title="Manuscript quality"
        description="Independent AI prose-quality observations. Hygiene, technical evidence and publication readiness are separate measurements, never folded into these scores."
        actions={
          quality.data?.chapters_current ? (
            <Tag tone="accent">{quality.data.chapters_current} current</Tag>
          ) : null
        }
      >
        {quality.loading ? <LoadingBlock label="Loading quality evaluations" compact /> : null}
        {quality.error ? <InlineError message={quality.error.message} /> : null}
        {quality.data && quality.data.chapters.length === 0 && discovery.data?.length ? (
          <EmptyState
            title="No quality evaluations yet"
            description="Use the evaluation campaign below to assess the missing chapters."
            icon={<Crosshair size={19} />}
          />
        ) : null}
        {discovery.data ? (
          <p className="muted small">
            Coverage: {quality.data?.chapters_current ?? 0} of {discovery.data.length} chapters current ·{" "}
            {comparableNote}
          </p>
        ) : null}
        {(() => {
          const stages: Record<string, number> = {};
          for (const chapter of quality.data?.chapters ?? []) {
            const latest = [...chapter.evaluations].sort((a, b) =>
              a.created_at < b.created_at ? 1 : -1,
            )[0];
            for (const unit of latest?.execution?.coverage?.units ?? []) {
              stages[unit.stage] = (stages[unit.stage] ?? 0) + 1;
            }
          }
          const parts = Object.entries(stages).map(([stage, count]) => `${stage}: ${count}`);
          if (!parts.length) return null;
          return (
            <p className="muted small">
              Unit stages (latest evaluation per chapter): {parts.join(" · ")}
            </p>
          );
        })()}
        {currentEvals.length ? (
          <div className="writer-mini-scores">
            {QUALITY_DIMENSIONS.map((dim) => {
              const values = currentEvals
                .map((e) => e.dimensions[dim]?.score)
                .filter((s): s is number => typeof s === "number");
              return (
                <span key={dim} title={`${dim}: mean and median over current chapter observations`}>
                  {QUALITY_DIM_SHORT[dim]}: mean {mean(values) ?? "—"} · median {median(values)}
                </span>
              );
            })}
          </div>
        ) : null}
      </Section>

      <Section
        title="Book Quality Map"
        description="Chapter by chapter across the six prose dimensions. Dashes mean no current observation; low values are review directions, not defect verdicts."
      >
        {mapRows.length ? <QualityMap rows={mapRows} /> : <LoadingBlock label="Loading chapter map" compact />}
      </Section>

      <Section
        title="Artifact Load"
        description="Independent burden measure: confirmed expository-overload concentration per chapter. Higher means more confirmed problems. Never merged into prose scores; disagreement between the two is useful evidence."
        actions={
          artifactLoad.data?.chapters_current ? (
            <Tag tone="accent">{artifactLoad.data.chapters_current} current</Tag>
          ) : null
        }
      >
        {artifactLoad.loading ? <LoadingBlock label="Loading artifact load" compact /> : null}
        {artifactLoad.error ? <InlineError message={artifactLoad.error.message} /> : null}
        {artifactLoad.data && artifactLoad.data.chapters.length === 0 ? (
          <EmptyState
            title="No artifact load observations yet"
            description="Record deterministic Writer findings per chapter; confirmed load appears here alongside prose scores."
            icon={<Crosshair size={19} />}
          />
        ) : null}
        {artifactLoad.data ? (
          <ArtifactLoadMap
            rows={(discovery.data ?? []).map((d) => {
              const chapter = (artifactLoad.data?.chapters ?? []).find(
                (c: ArtifactLoadChapter) => c.chapter_id === d.chapter_id,
              );
              const current = chapter?.current;
              const prose = evalByChapter.get(d.chapter_id)?.current?.overall ?? null;
              return {
                chapter_id: d.chapter_id,
                title: d.title,
                prose_overall: prose,
                mech: current?.mechanical_pressure ?? null,
                weighted_load: current?.weighted_load ?? null,
                confirmed: current?.confirmed ?? 0,
                high: current?.high ?? 0,
                unreviewed: current?.unreviewed ?? 0,
                coverage_mech: current?.coverage_mechanical ?? 0,
                coverage_sem: current?.coverage_semantic ?? 0,
                assessment: current?.assessment_state ?? "not_assessed",
                workbench_link: current?.workbench_link ?? null,
              };
            })}
          />
        ) : null}
        {artifactLoad.data?.limitations?.map((note: string) => (
          <p key={note} className="muted small">{note}</p>
        ))}
      </Section>

      <Section
        title="Evaluation campaign"
        description="One deliberate operation evaluates missing or outdated chapters. Progress persists per chapter; stopping and resuming never discards completed work."
      >
        {campaigns.error ? <InlineError message={campaigns.error.message} /> : null}
        {activeCampaign ? (
          <div className="writer-decision-card">
            <div className="writer-decision-head">
              <strong>{activeCampaign.id.slice(0, 14)} · {activeCampaign.mode} · {activeCampaign.strategy ?? "direct"}</strong>
              <span className="writer-decision-count">
                {activeCampaign.completed} done · {activeCampaign.failed} failed · {activeCampaign.remaining} remaining
                {activeCampaign.current_chapter ? ` · now: ${activeCampaign.current_chapter}` : ""}
              </span>
              <Tag tone={activeCampaign.status === "running" ? "accent" : "default"}>{titleCase(activeCampaign.status)}</Tag>
            </div>
            {activeCampaign.error ? <p className="warn-text small">{activeCampaign.error}</p> : null}
            <div className="button-row">
              {activeCampaign.status === "running" || activeCampaign.status === "pending" ? (
                <button className="button button-secondary button-small" onClick={() => void stopCampaign(activeCampaign.id)}>
                  Stop after current chapter
                </button>
              ) : null}
              {["partial", "interrupted", "failed"].includes(activeCampaign.status) ? (
                <button className="button button-secondary button-small" onClick={() => void resumeCampaign(activeCampaign.id)}>
                  Resume remaining chapters
                </button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="inline-form">
            <label className="muted small">
              Mode{" "}
              <select value={campaignMode} onChange={(event) => setCampaignMode(event.target.value)} aria-label="Campaign mode">
                <option value="missing">Evaluate missing</option>
                <option value="outdated">Evaluate outdated</option>
                <option value="selected">Evaluate selected</option>
                <option value="full">Re-evaluate entire book</option>
              </select>
            </label>
            <label className="muted small">
              Strategy{" "}
              <select value={campaignStrategy} onChange={(event) => setCampaignStrategy(event.target.value)} aria-label="Campaign strategy">
                <option value="deterministic">Deterministic checks</option>
                <option value="direct">Direct semantic review</option>
                <option value="bounded_judge">Bounded judgment (shadow)</option>
              </select>
            </label>
            <label className="muted small">
              Model{" "}
              <input
                value={campaignModel}
                onChange={(event) => setCampaignModel(event.target.value)}
                placeholder="opencode-go/deepseek-v4.1-flash"
                aria-label="Campaign model route"
                size={32}
              />
            </label>
            <button
              className="button button-primary button-small"
              disabled={campaignBusy}
              onClick={() => void createCampaign(campaignMode, campaignMode === "selected" ? selectedChapters : undefined)}
            >
              {campaignBusy ? "Starting…" : campaignMode === "full" ? "Confirm full-book re-evaluation" : "Start campaign"}
            </button>
          </div>
        )}
        {campaignMode === "selected" && !activeCampaign ? (
          <div className="table-wrap">
            <p className="muted small">Tick chapters for a targeted run ({selectedChapters.length} selected).</p>
            {(discovery.data ?? []).map((row) => (
              <label key={row.chapter_id} className="muted small" style={{ display: "block" }}>
                <input
                  type="checkbox"
                  checked={selectedChapters.includes(row.chapter_id)}
                  onChange={(event) =>
                    setSelectedChapters((current) =>
                      event.target.checked
                        ? [...current, row.chapter_id]
                        : current.filter((id) => id !== row.chapter_id),
                    )
                  }
                />{" "}
                {row.chapter_id} — {row.title ?? "untitled"} ({row.eligibility})
              </label>
            ))}
          </div>
        ) : null}
        {pastCampaigns.length ? (
          <details className="history-list">
            <summary>Past campaigns ({pastCampaigns.length})</summary>
            {pastCampaigns.map((c) => (
              <p key={c.id} className="muted small">
                {c.id.slice(0, 14)} · {c.mode} · {c.strategy ?? "direct"} · {c.status} · {c.completed} done, {c.failed} failed
                {c.error ? ` · ${c.error}` : ""}
              </p>
            ))}
          </details>
        ) : null}
      </Section>

      <Section
        title="Priority review"
        description="Review directions grounded in specific observations and verified evidence — never bare low scores, and never automatic rewrites."
      >
        {priorities.length === 0 ? (
          <p className="muted small">No grounded review items. Scores alone do not create findings.</p>
        ) : (
          <ul className="plain-list">
            {priorities.slice(0, 20).map((item, index) => (
              <li key={`${item.title}-${index}`}>
                <strong>{item.title}</strong>
                <br />
                <span className="muted small">{item.detail}</span>{" "}
                {item.chapter_id ? (
                  <a className="text-link" href={`#quality-${item.chapter_id}`}>
                    Open evaluation
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {writerFindings.length ? (
          <>
            <span className="eyebrow">Readability signals (Writer, deterministic)</span>
            <div className="writer-decision-queue">
              {writerFindings.slice(0, 5).map((item: WriterDecisionQueueItem) => (
                <article className="writer-decision-card" key={item.id}>
                  <div className="writer-decision-head">
                    <Tag tone={item.severity === "high" ? "danger" : item.severity === "medium" ? "accent" : "default"}>
                      {item.severity.toUpperCase()}
                    </Tag>
                    <strong>{item.code}</strong>
                    <span className="writer-decision-count">
                      {item.count} finding{item.count === 1 ? "" : "s"} · {item.chapter_title || item.chapter_name}
                    </span>
                  </div>
                  <p className="muted small">{item.reason}</p>
                </article>
              ))}
            </div>
            <p className="muted small">Deterministic readability signals; not AI judgments and not combined with the scores above.</p>
          </>
        ) : null}
      </Section>

      <Section title="Chapter evaluations" description="Scorecards with provenance, history and Workbench handoff.">
        {quality.data ? (
          <div className="writer-decision-queue">
            {quality.data.chapters.map((chapter) => (
              <QualityChapterCard key={chapter.chapter_id} chapter={chapter} />
            ))}
          </div>
        ) : null}
        {quality.data?.limitations.length ? (
          <ul className="plain-list writer-boundaries">
            {quality.data.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        ) : null}
      </Section>
    </>
  );
}

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const project = useApi<ProjectDetail>(`/api/projects/${projectId}`, { pollMs: 60000 });
  const applications = useApi<Application[]>("/api/applications?enabled_only=true");
  const integrationContext = useApi<IntegrationRecord[]>(
    `/api/projects/${projectId}/integration-context`,
    { pollMs: 60000 },
  );
  const experimentTimeline = useApi<ProjectEvidenceTimeline>(
    `/api/projects/${projectId}/evidence-timeline`,
    { pollMs: 60000 },
  );
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskError, setTaskError] = useState<string | null>(null);
  const [decisionTitle, setDecisionTitle] = useState("");
  const [decisionRationale, setDecisionRationale] = useState("");

  async function refreshProject() {
    project.reload();
  }

  async function setFocus() {
    setBusy(true);
    try {
      await api.post(`/api/projects/${projectId}/focus`);
      toast.push("success", `${project.data?.name ?? "Project"} is now the current focus`);
      project.reload();
    } catch (caught) {
      toast.push("error", "Could not set focus", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function togglePin() {
    if (!project.data) return;
    setBusy(true);
    try {
      await api.patch(`/api/projects/${projectId}`, { pinned: !project.data.pinned });
      toast.push("success", project.data.pinned ? "Project unpinned" : "Project pinned");
      project.reload();
    } catch (caught) {
      toast.push("error", "Could not update pin", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function openRepository() {
    try {
      await api.post(`/api/projects/${projectId}/open-repository`);
      toast.push("success", "Repository opened");
    } catch (caught) {
      toast.push("error", "Could not open repository", errorMessage(caught));
    }
  }

  async function launchApplication(app: Application) {
    if (app.control_policy.confirmation_required) {
      const confirmed = window.confirm(
        `${app.name} is configured to require confirmation. Launch it now?`,
      );
      if (!confirmed) return;
    }
    try {
      await api.post(`/api/applications/${app.id}/launch`, { confirm: true });
      toast.push("success", `${app.name} launch requested`);
      window.setTimeout(() => applications.reload(), 800);
    } catch (caught) {
      toast.push("error", `Could not launch ${app.name}`, errorMessage(caught));
      applications.reload();
    }
  }

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!taskTitle.trim()) return;
    setTaskError(null);
    try {
      await api.post("/api/tasks", { project_id: projectId, title: taskTitle });
      setTaskTitle("");
      toast.push("success", "Task added");
      project.reload();
    } catch (caught) {
      setTaskError(errorMessage(caught));
    }
  }

  async function addDecision(event: FormEvent) {
    event.preventDefault();
    if (!decisionTitle.trim()) return;
    try {
      await api.post("/api/decisions", {
        project_id: projectId,
        title: decisionTitle,
        rationale: decisionRationale,
        status: "accepted",
      });
      setDecisionTitle("");
      setDecisionRationale("");
      toast.push("success", "Decision recorded");
      project.reload();
    } catch (caught) {
      toast.push("error", "Could not record decision", errorMessage(caught));
    }
  }

  if (project.loading && !project.data) {
    return (
      <div className="page">
        <LoadingBlock label="Opening project workspace" />
      </div>
    );
  }
  if (project.error) {
    return (
      <div className="page">
        <ErrorState message={project.error.message} onRetry={project.reload} />
      </div>
    );
  }
  if (!project.data) return null;

  const data = project.data;
  const checkpoint = data.latest_checkpoint;
  const openTasks = data.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
  const doneTasks = data.tasks.filter((task) => task.status === "done");
  const pendingRecs = data.recommendations.filter((rec) => rec.review_state === "pending");

  return (
    <div className="page project-workspace">
      <Link className="back-link" to="/projects">
        <ArrowLeft size={14} /> All projects
      </Link>
      <PageHeader
        eyebrow={`${projectLabel(data.kind)} workspace`}
        title={data.name}
        description={data.description}
        actions={
          <>
            <button className="button button-secondary" onClick={() => void togglePin()} disabled={busy}>
              {data.pinned ? <PinOff size={15} /> : <Pin size={15} />}
              {data.pinned ? "Unpin" : "Pin"}
            </button>
            <button className="button button-secondary" onClick={() => void setFocus()} disabled={busy}>
              <Crosshair size={15} /> Set focus
            </button>
            <ActionButton
              action={data.repository_action ?? undefined}
              onClick={() => void openRepository()}
              variant="primary"
              icon={<FolderOpen size={15} />}
            >
              Repository
            </ActionButton>
          </>
        }
      />

      <div className="workspace-banner">
        <div>
          <span className="eyebrow">Current milestone</span>
          <p>{data.current_milestone || "No milestone recorded."}</p>
        </div>
        <div>
          <span className="eyebrow">Next action</span>
          <p>{data.next_action || "No next action saved."}</p>
        </div>
        <div>
          <span className="eyebrow">Last activity</span>
          <p>{timeAgo(data.last_activity_at)}</p>
        </div>
      </div>

      <div className="workspace-grid">
        <div className="workspace-main">
          <Section title="Checkpoint and resume" description="Persisted locally. Restarting Mission Control does not lose it.">
            {checkpoint ? (
              <div className="latest-checkpoint">
                <div className="latest-checkpoint-head">
                  <div>
                    <span className="eyebrow">Latest checkpoint</span>
                    <h3>{checkpoint.summary}</h3>
                  </div>
                  <ProvenanceBadge value="recorded_checkpoint" />
                </div>
                <div className="checkpoint-facts">
                  <div>
                    <span>Last completed</span>
                    <p>{checkpoint.last_completed || "Not recorded"}</p>
                  </div>
                  <div>
                    <span>Next intended action</span>
                    <p>{checkpoint.next_action || data.next_action || "Not recorded"}</p>
                  </div>
                  {checkpoint.blockers ? (
                    <div>
                      <span>Blocker</span>
                      <p>{checkpoint.blockers}</p>
                    </div>
                  ) : null}
                </div>
                <div className="inline-meta">
                  <span>{formatDateTime(checkpoint.created_at)}</span>
                  {checkpoint.milestone ? <span>{checkpoint.milestone}</span> : null}
                  {checkpoint.evidence_refs.map((reference) => (
                    <code key={reference}>{reference}</code>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                title="No checkpoint recorded"
                description="A checkpoint captures where the work stopped and what should happen next."
                icon={<Crosshair size={19} />}
              />
            )}
            <details className="checkpoint-composer" open={!checkpoint}>
              <summary>
                <Plus size={14} /> Save a new checkpoint
              </summary>
              <CheckpointForm projectId={projectId} onSaved={refreshProject} />
            </details>
            {data.checkpoints.length > 1 ? (
              <details className="history-list">
                <summary>Earlier checkpoints ({data.checkpoints.length - 1})</summary>
                <ul>
                  {data.checkpoints.slice(1).map((item: Checkpoint) => (
                    <li key={item.id}>
                      <strong>{formatDateTime(item.created_at)}</strong>
                      <span>{item.summary}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </Section>

          <Section
            title="Recommendations awaiting review"
            description="Adapter evidence and AI suggestions remain proposals until a person reviews them."
            actions={pendingRecs.length ? <Tag tone="accent">{pendingRecs.length} pending</Tag> : null}
          >
            {pendingRecs.length ? (
              <ul className="recommendation-list">
                {pendingRecs.map((rec) => (
                  <RecommendationRow key={rec.id} recommendation={rec} onChanged={refreshProject} />
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No pending recommendations"
                description="Math, Next and CoCoder evidence will appear here when adapters find something reviewable."
              />
            )}
          </Section>

          <Section
            title="Cross-application context"
            description="Next research, Work opportunities and CoCoder findings associated with this project. Source systems remain authoritative."
            actions={
              integrationContext.data?.length ? (
                <Tag tone="accent">{integrationContext.data.length} linked</Tag>
              ) : null
            }
          >
            {integrationContext.loading ? <LoadingBlock label="Loading linked context" compact /> : null}
            {integrationContext.error ? (
              <InlineError message={integrationContext.error.message} />
            ) : null}
            {integrationContext.data?.length ? (
              <div className="project-context-list">
                {integrationContext.data.map((record) => (
                  <Link
                    className="project-context-item"
                    key={record.id}
                    to={`/${record.application_id}?record=${record.id}`}
                  >
                    <div className="project-context-head">
                      <span className={`source-pill source-${record.application_id}`}>
                        {record.application_name ?? titleCase(record.application_id)}
                      </span>
                      <SimpleStatusBadge
                        state={record.stale ? "stale" : "running"}
                        label={record.state || titleCase(record.resource_type)}
                      />
                      <span className="project-context-time">
                        {timeAgo(record.source_timestamp || record.observed_at)}
                      </span>
                    </div>
                    <strong>{record.title}</strong>
                    <p>{truncate(record.summary || "No source summary.", 240)}</p>
                    <div className="project-context-meta">
                      <span>{titleCase(record.resource_type.replace(/_/g, " "))}</span>
                      {record.local_decision ? (
                        <span className="local-decision-pill">
                          {record.local_decision.decision} · local only
                        </span>
                      ) : null}
                      {record.stale ? <span className="warn-text">stale observation</span> : null}
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
            {integrationContext.data && integrationContext.data.length === 0 ? (
              <EmptyState
                title="No linked application records"
                description="Open a record in Next, Work or CoCoder and associate it with this project."
                icon={<Crosshair size={19} />}
              />
            ) : null}
          </Section>

          <Section
            title="Experiment evidence"
            description="Cross-application workflows and Language observations associated with this project. Observations never rewrite intentions or decisions."
            actions={
              experimentTimeline.data?.workflows.length ? (
                <Tag tone="accent">{experimentTimeline.data.workflows.length} workflows</Tag>
              ) : null
            }
          >
            {experimentTimeline.loading ? <LoadingBlock label="Loading experiment evidence" compact /> : null}
            {experimentTimeline.error ? <InlineError message={experimentTimeline.error.message} /> : null}
            {experimentTimeline.data?.workflows.length ? (
              <div className="workflow-list">
                {experimentTimeline.data.workflows.map((workflow) => (
                  <Link className="workflow-card" key={workflow.id} to={`/workflows/${workflow.id}`}>
                    <div className="workflow-card-head">
                      <div>
                        <span className="eyebrow">{workflow.template}</span>
                        <h2>{workflow.title}</h2>
                      </div>
                      <SimpleStatusBadge state={workflow.status === "decided" ? "running" : workflow.status === "cancelled" ? "cancelled" : "pending"} label={titleCase(workflow.status)} />
                    </div>
                    <div className="workflow-card-meta">
                      <span>{workflow.measurement?.passed ? "Measurement passed" : "Measurement not passed"}</span>
                      <span>{workflow.adverse_review ? "Adverse review" : "No adverse review"}</span>
                      {workflow.final_decision ? <Tag tone="accent">Decision: {workflow.final_decision}</Tag> : null}
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
            {experimentTimeline.data?.observations.length ? (
              <div className="project-observations">
                {experimentTimeline.data.observations.map((observation) => (
                  <div key={observation.id}>
                    <span className="eyebrow">{observation.schema}</span>
                    <strong>{observation.subject}</strong>
                    <span className={`tag ${observation.constraint_result === "pass" ? "tag-accent" : ""}`}>
                      Constraint {observation.constraint_result}
                    </span>
                    <ul className="plain-list">
                      {observation.properties.map((property) => (
                        <li key={property.id}>
                          {titleCase(property.id.replace(/_/g, " "))}: expected {JSON.stringify(property.expected)}, observed {JSON.stringify(property.observed)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : null}
            {experimentTimeline.data &&
            experimentTimeline.data.workflows.length === 0 &&
            experimentTimeline.data.observations.length === 0 ? (
              <EmptyState
                title="No experiment evidence"
                description="Approved experiment workflows associated with this project will appear here."
                icon={<Crosshair size={19} />}
              />
            ) : null}
          </Section>

          <QualityPanel projectId={projectId} />
          <TechnicalPanel projectId={projectId} />
          <CompletenessPanel projectId={projectId} />
          <ReadinessPanel projectId={projectId} />
          <CalibrationPanel projectId={projectId} />

          <Section title="Tasks" description="Explicit user actions. Evidence adapters do not create tasks automatically.">
            <form className="inline-form" onSubmit={(event) => void addTask(event)}>
              <input
                value={taskTitle}
                onChange={(event) => setTaskTitle(event.target.value)}
                placeholder="Add a task for this project"
                aria-label="New task"
              />
              <button className="button button-secondary" type="submit" disabled={!taskTitle.trim()}>
                <Plus size={14} /> Add task
              </button>
            </form>
            <InlineError message={taskError} />
            {openTasks.length ? (
              <ul className="task-list">
                {openTasks.map((task) => (
                  <TaskRow task={task} key={task.id} onChanged={refreshProject} />
                ))}
              </ul>
            ) : (
              <p className="muted small">No open tasks.</p>
            )}
            {doneTasks.length ? (
              <details className="history-list">
                <summary>Completed tasks ({doneTasks.length})</summary>
                <ul className="task-list">
                  {doneTasks.map((task) => (
                    <TaskRow task={task} key={task.id} onChanged={refreshProject} />
                  ))}
                </ul>
              </details>
            ) : null}
          </Section>

          <Section title="Decisions" description="Accepted, rejected or deferred choices stay visible with their rationale.">
            <form className="decision-form form-stack" onSubmit={(event) => void addDecision(event)}>
              <div className="form-grid two">
                <label className="field">
                  <span>Decision</span>
                  <input
                    value={decisionTitle}
                    onChange={(event) => setDecisionTitle(event.target.value)}
                    placeholder="What was decided?"
                  />
                </label>
                <label className="field">
                  <span>Rationale</span>
                  <input
                    value={decisionRationale}
                    onChange={(event) => setDecisionRationale(event.target.value)}
                    placeholder="Why?"
                  />
                </label>
              </div>
              <div className="form-actions">
                <button className="button button-secondary button-small" type="submit" disabled={!decisionTitle.trim()}>
                  Record decision
                </button>
              </div>
            </form>
            {data.decisions.length ? (
              <ul className="decision-list">
                {data.decisions.map((decision) => (
                  <li key={decision.id}>
                    <div>
                      <strong>{decision.title}</strong>
                      <p>{decision.rationale || "No rationale recorded."}</p>
                    </div>
                    <span>{formatDateTime(decision.decided_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No decisions recorded.</p>
            )}
          </Section>

          <Section title="Activity" description="Project-scoped history with provenance.">
            {data.activity.length ? (
              <ul className="activity-feed">
                {data.activity.map((event) => (
                  <li key={event.id}>
                    <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
                    <div>
                      <div className="activity-head">
                        <strong>{event.title}</strong>
                        <span className="activity-type">{activityLabel(event.type)}</span>
                      </div>
                      <span className="activity-meta">
                        {timeAgo(event.occurred_at)} · <ProvenanceBadge value={event.provenance} />
                      </span>
                      {event.detail ? <p className="activity-detail">{truncate(event.detail, 280)}</p> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No activity recorded for this project yet.</p>
            )}
          </Section>
        </div>

        <aside className="workspace-side">
          <section className="panel">
            <span className="eyebrow">Outcomes</span>
            <div className="outcome-stack">
              {data.outcomes.length ? (
                data.outcomes.map((outcome) => (
                  <div className="outcome-mini" key={outcome.id}>
                    <strong>{outcome.name}</strong>
                    <span>{outcome.status}</span>
                  </div>
                ))
              ) : (
                <p className="muted small">No outcome relationship configured.</p>
              )}
            </div>
          </section>

          {data.book ? (
            <section className="panel">
              <span className="eyebrow">Book</span>
              <h3>{data.book.title}</h3>
              <div className="inline-meta">
                <SimpleStatusBadge state={data.book.status} />
                <span>{data.book.quality_review_state.replace(/_/g, " ")}</span>
              </div>
              <div className="mini-block">
                <span>Next action</span>
                <p>{data.book.next_action || "Not recorded"}</p>
              </div>
              <Link className="button button-secondary button-small" to="/books">
                <BookOpen size={14} /> Open books view
              </Link>
            </section>
          ) : null}

          <section className="panel">
            <span className="eyebrow">Repositories</span>
            {data.repositories.length ? (
              <ul className="repo-list">
                {data.repositories.map((repository) => (
                  <li key={repository.id}>
                    <div className="repo-head">
                      <strong>{repository.name}</strong>
                      {repository.role ? <Tag>{repository.role}</Tag> : null}
                    </div>
                    <PathText>{repository.path}</PathText>
                    <div className="git-facts">
                      {repository.is_git ? <GitBranch size={13} /> : null}
                      {repository.is_git ? (
                        <>
                          <span>{repository.branch ?? "detached"}</span>
                          <span>{shortCommit(repository.commit_hash)}</span>
                          <span className={repository.dirty ? "warn-text" : "muted"}>
                            {repository.dirty ? "uncommitted changes" : "clean tracked tree"}
                          </span>
                        </>
                      ) : (
                        <span className="muted">Not a Git repository</span>
                      )}
                    </div>
                    <span className="muted small">
                      Observed {repository.last_observed_at ? timeAgo(repository.last_observed_at) : "not yet"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No repositories linked.</p>
            )}
          </section>

          <section className="panel">
            <span className="eyebrow">Supporting tools</span>
            {data.applications.length ? (
              <ul className="tool-list">
                {data.applications.map((summary) => {
                  const app = applications.data?.find((item) => item.id === summary.id);
                  return (
                    <li className="tool-row" key={summary.id}>
                      <div className="tool-copy">
                        <Link to="/applications" className="text-link">
                          {summary.name} <ExternalLink size={12} />
                        </Link>
                        <span>
                          {app ? <SimpleStatusBadge state={app.status.state} /> : titleCase(summary.category)}
                        </span>
                      </div>
                      {app ? (
                        <ActionButton
                          action={app.actions.launch}
                          onClick={() => void launchApplication(app)}
                          variant="secondary"
                          small
                          icon={<Play size={13} />}
                        >
                          Launch
                        </ActionButton>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted small">No applications associated.</p>
            )}
          </section>

          <section className="panel">
            <span className="eyebrow">Adapters</span>
            <div className="adapter-list">
              {data.adapters.length ? (
                data.adapters.map((adapter) => (
                  <AdapterCard
                    key={adapter.id}
                    adapter={adapter}
                    projectId={projectId}
                    onChanged={refreshProject}
                  />
                ))
              ) : (
                <p className="muted small">No adapter registered for this project.</p>
              )}
            </div>
          </section>

          {data.notes ? (
            <section className="panel">
              <span className="eyebrow">Notes</span>
              <p className="small">{data.notes}</p>
            </section>
          ) : null}

          <section className="panel">
            <span className="eyebrow">Workspace</span>
            <dl className="kv-list">
              <KeyValue label="Kind">{projectLabel(data.kind)}</KeyValue>
              <KeyValue label="Status">
                <SimpleStatusBadge state={data.status} />
              </KeyValue>
              <KeyValue label="Priority">{data.priority}</KeyValue>
              <KeyValue label="Created">{formatDateTime(data.created_at)}</KeyValue>
              <KeyValue label="Open tasks">{data.open_task_count}</KeyValue>
              <KeyValue label="Pending reviews">{data.pending_recommendation_count}</KeyValue>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}
