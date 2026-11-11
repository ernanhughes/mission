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
  QualityWorkspace,
  Recommendation,
  Task,
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
  const invalid = invalidQuoteCount(evaluation);
  const execution = evaluation.execution ?? {};
  return (
    <article className="writer-finding" id={`eval-${evaluation.id}`}>
      <div className="writer-finding-head">
        <div>
          <Tag tone={freshnessTone(evaluation.derived_state)}>
            {titleCase(evaluation.derived_state)}
          </Tag>
          {evaluation.status !== "CURRENT" ? <Tag>{evaluation.status}</Tag> : null}
          <Tag>{evaluation.strategy ?? "direct"}</Tag>
          <strong>{evaluation.overall ?? "—"} / 6 · Prose quality</strong>
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
      {chapter.evaluations.filter((item) => item.derived_state !== "current").length ? (
        <details className="history-list">
          <summary>
            Earlier observations ({chapter.evaluations.filter((item) => item.derived_state !== "current").length})
          </summary>
          {chapter.evaluations
            .filter((item) => item.derived_state !== "current")
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
