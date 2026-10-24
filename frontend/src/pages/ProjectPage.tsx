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
  Checkpoint,
  IntegrationRecord,
  ProjectDetail,
  Recommendation,
  Task,
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

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const project = useApi<ProjectDetail>(`/api/projects/${projectId}`, { pollMs: 60000 });
  const applications = useApi<Application[]>("/api/applications?enabled_only=true");
  const integrationContext = useApi<IntegrationRecord[]>(
    `/api/projects/${projectId}/integration-context`,
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
