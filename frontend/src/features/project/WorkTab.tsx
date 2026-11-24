import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Crosshair, ExternalLink, GitBranch, Play, Plus } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import {
  EmptyState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PathText,
  ProvenanceBadge,
  Section,
  SimpleStatusBadge,
  Tag,
} from "../../components/ui";
import { InspectPanel } from "../inspect/InspectPanels";
import { AdapterCard, CheckpointForm, RecommendationRow, TaskRow } from "./shared";
import {
  activityLabel,
  formatDateTime,
  projectLabel,
  shortCommit,
  timeAgo,
  titleCase,
  truncate,
} from "../../lib/format";
import type {
  Application,
  Checkpoint,
  IntegrationRecord,
  ProjectDetail,
  ProjectEvidenceTimeline,
} from "../../types/api";

export function WorkTab({
  projectId,
  data,
  integrationContext,
  experimentTimeline,
  applications,
  onChanged,
  onLaunchApp,
}: {
  projectId: string;
  data: ProjectDetail;
  integrationContext: { data: IntegrationRecord[] | null; loading: boolean; error: { message: string } | null };
  experimentTimeline: { data: ProjectEvidenceTimeline | null; loading: boolean; error: { message: string } | null };
  applications: Application[] | null;
  onChanged: () => void;
  onLaunchApp: (app: Application) => void;
}) {
  const toast = useToast();
  const [taskTitle, setTaskTitle] = useState("");
  const [taskError, setTaskError] = useState<string | null>(null);
  const [decisionTitle, setDecisionTitle] = useState("");
  const [decisionRationale, setDecisionRationale] = useState("");
  const [subview, setSubview] = useState<"actions" | "continuity" | "connected" | "info">("actions");

  const checkpoint = data.latest_checkpoint;
  const openTasks = data.tasks.filter((t) => t.status !== "done" && t.status !== "cancelled");
  const doneTasks = data.tasks.filter((t) => t.status === "done");
  const pendingRecs = data.recommendations.filter((r) => r.review_state === "pending");
  const reviewedRecs = data.recommendations.filter((r) => r.review_state !== "pending");

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!taskTitle.trim()) return;
    setTaskError(null);
    try {
      await api.post("/api/tasks", { project_id: projectId, title: taskTitle });
      setTaskTitle("");
      toast.push("success", "Task added");
      onChanged();
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
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not record decision", errorMessage(caught));
    }
  }

  return (
    <div>
      <div className="button-row" role="tablist" aria-label="Work subgroups">
        {(["actions", "continuity", "connected", "info"] as const).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={subview === id}
            className={`button button-small ${subview === id ? "button-secondary" : "button-ghost"}`}
            onClick={() => setSubview(id)}
          >
            {id === "actions" ? "Actions and decisions" : id === "continuity" ? "Continuity" : id === "connected" ? "Connected capabilities" : "Project information"}
          </button>
        ))}
      </div>

      {subview === "actions" ? (
        <div>
          <Section
            title="Recommendations awaiting review"
            description="Adapter evidence and AI suggestions remain proposals until a person reviews them."
            actions={pendingRecs.length ? <Tag tone="accent">{pendingRecs.length} pending</Tag> : undefined}
          >
            {pendingRecs.length ? (
              <ul className="recommendation-list">
                {pendingRecs.map((rec) => (
                  <RecommendationRow key={rec.id} recommendation={rec} onChanged={onChanged} />
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No pending recommendations"
                description="Math, Next and CoCoder evidence will appear here when adapters find something reviewable."
              />
            )}
            {reviewedRecs.length ? (
              <details className="history-list">
                <summary>Reviewed ({reviewedRecs.length})</summary>
                <ul className="recommendation-list">
                  {reviewedRecs.map((rec) => (
                    <RecommendationRow key={rec.id} recommendation={rec} onChanged={onChanged} />
                  ))}
                </ul>
              </details>
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
                  <TaskRow task={task} key={task.id} onChanged={onChanged} />
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
                    <TaskRow task={task} key={task.id} onChanged={onChanged} />
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
        </div>
      ) : null}

      {subview === "continuity" ? (
        <div>
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
              <CheckpointForm projectId={projectId} onSaved={onChanged} />
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
        </div>
      ) : null}

      {subview === "connected" ? (
        <div>
          <Section
            title="Cross-application context"
            description="Next research, Work opportunities and CoCoder findings associated with this project. Source systems remain authoritative."
            actions={integrationContext.data?.length ? <Tag tone="accent">{integrationContext.data.length} linked</Tag> : null}
          >
            {integrationContext.loading ? <LoadingBlock label="Loading linked context" compact /> : null}
            {integrationContext.error ? <InlineError message={integrationContext.error.message} /> : null}
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

          <InspectPanel applicationIds={(data.applications ?? []).map((app) => app.id)} />

          <Section title="Repositories" description="Linked source checkouts and their Git state.">
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
          </Section>

          <Section title="Supporting tools" description="Applications associated with this project.">
            {data.applications.length ? (
              <ul className="tool-list">
                {data.applications.map((summary) => {
                  const app = applications?.find((item) => item.id === summary.id);
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
                        <button
                          className="button button-secondary button-small"
                          disabled={!app.actions.launch.enabled}
                          title={app.actions.launch.reason ?? "Launch"}
                          onClick={() => onLaunchApp(app)}
                        >
                          <Play size={13} /> Launch
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted small">No applications associated.</p>
            )}
          </Section>

          <Section title="Adapters" description="Evidence adapter health for this project.">
            <div className="adapter-list">
              {data.adapters.length ? (
                data.adapters.map((adapter) => (
                  <AdapterCard key={adapter.id} adapter={adapter} projectId={projectId} onChanged={onChanged} />
                ))
              ) : (
                <p className="muted small">No adapter registered for this project.</p>
              )}
            </div>
          </Section>
        </div>
      ) : null}

      {subview === "info" ? (
        <div>
          <Section title="Outcomes" description="Outcome relationships for this project.">
            {data.outcomes.length ? (
              <ul className="plain-list">
                {data.outcomes.map((outcome) => (
                  <li key={outcome.id}>
                    <strong>{outcome.name}</strong> · <span className="muted small">{outcome.status}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No outcome relationship configured.</p>
            )}
          </Section>
          {data.notes ? (
            <Section title="Notes" description="Author notes.">
              <p className="small">{data.notes}</p>
            </Section>
          ) : null}
          <Section title="Workspace metadata" description="Kind, status and counters. Counters are observed, not inferred.">
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
          </Section>
        </div>
      ) : null}
    </div>
  );
}
