import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  CircleSlash,
  Code2,
  ExternalLink,
  FileJson,
  FlaskConical,
  Gauge,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Telescope,
  XCircle,
} from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
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
  Stat,
  Tag,
} from "../components/ui";
import {
  formatDateTime,
  provenanceLabel,
  timeAgo,
  titleCase,
  truncate,
} from "../lib/format";
import type {
  ExperimentWorkflow,
  Integration,
  IntegrationDecision,
  IntegrationExecution,
  IntegrationRecord,
  Project,
} from "../types/api";

type Tab = {
  id: string;
  label: string;
  resourceType?: string;
  filter?: (record: IntegrationRecord) => boolean;
  special?: "overview" | "decisions" | "operations" | "repositories" | "results";
};

type WorkspaceConfig = {
  appId: "next" | "work" | "cocoder";
  title: string;
  eyebrow: string;
  description: string;
  icon: typeof Telescope;
  mainResource: string;
  tabs: Tab[];
};

const configs: Record<"next" | "work" | "cocoder", WorkspaceConfig> = {
  next: {
    appId: "next",
    title: "Next",
    eyebrow: "Research workspace",
    description: "Research candidates, evidence, experiments and recommendations from Next's authoritative store.",
    icon: Telescope,
    mainResource: "next_opportunity",
    tabs: [
      { id: "overview", label: "Overview", special: "overview" },
      { id: "candidates", label: "Candidates", resourceType: "next_opportunity" },
      {
        id: "recommendations",
        label: "Recommendations",
        resourceType: "next_opportunity",
        filter: (record) => record.data.queue_type === "validated",
      },
      { id: "experiments", label: "Experiments", resourceType: "next_experiment" },
      { id: "evidence", label: "Evidence", resourceType: "next_evidence_gap" },
      { id: "decisions", label: "Decisions", special: "decisions" },
      { id: "operations", label: "Operations", special: "operations" },
    ],
  },
  work: {
    appId: "work",
    title: "Work",
    eyebrow: "Commercial workspace",
    description: "Real opportunities, qualification evidence, pursuit decisions and commercial activity from Work.",
    icon: BriefcaseBusiness,
    mainResource: "work_opportunity",
    tabs: [
      { id: "overview", label: "Overview", special: "overview" },
      { id: "opportunities", label: "Opportunities", resourceType: "work_opportunity" },
      {
        id: "qualifications",
        label: "Qualifications",
        resourceType: "work_opportunity",
        filter: (record) => Boolean(record.data.qualification?.qualified),
      },
      {
        id: "pursuits",
        label: "Pursuits",
        resourceType: "work_opportunity",
        filter: (record) => Boolean(record.local_decision),
      },
      { id: "results", label: "Results", special: "results" },
      { id: "decisions", label: "Decisions", special: "decisions" },
      { id: "operations", label: "Operations", special: "operations" },
    ],
  },
  cocoder: {
    appId: "cocoder",
    title: "CoCoder",
    eyebrow: "Quality workspace",
    description: "Repository assessments, findings and review history from CoCoder.",
    icon: ShieldCheck,
    mainResource: "cocoder_review",
    tabs: [
      { id: "overview", label: "Overview", special: "overview" },
      { id: "repositories", label: "Repositories", special: "repositories" },
      { id: "reviews", label: "Assessments", resourceType: "cocoder_review" },
      {
        id: "findings",
        label: "Findings",
        resourceType: "cocoder_finding",
        filter: (record) => ["high", "medium", "low", "info"].includes(String(record.data.severity)),
      },
      { id: "decisions", label: "Decisions", special: "decisions" },
      { id: "operations", label: "Operations", special: "operations" },
    ],
  },
};

const decisionHelp =
  "Saved locally in Mission Control. Source application state is not modified or claimed as synchronised.";

function resourceScore(record: IntegrationRecord): string | null {
  if (record.application_id === "next") {
    const score = record.data.scores?.score;
    return score != null ? `Score ${score}` : null;
  }
  if (record.application_id === "work") {
    const score = record.data.qualification?.score;
    return score != null ? `Qualification ${score}` : null;
  }
  if (record.application_id === "cocoder") {
    return String(record.data.severity ?? record.state.split("/")[0]).trim();
  }
  return null;
}

function ResourceRow({
  record,
  active,
  onSelect,
}: {
  record: IntegrationRecord;
  active: boolean;
  onSelect: () => void;
}) {
  const score = resourceScore(record);
  return (
    <button className={`resource-row ${active ? "active" : ""}`} onClick={onSelect}>
      <div className="resource-row-top">
        <span className={`resource-state state-${record.application_id}`}>{record.state || record.resource_type}</span>
        <span className="resource-time">{timeAgo(record.source_timestamp || record.observed_at)}</span>
      </div>
      <strong>{record.title}</strong>
      <p>{truncate(record.summary || "No summary supplied by the source.", 220)}</p>
      <div className="resource-meta">
        {score ? <span>{score}</span> : null}
        {record.project_name ? <span>{record.project_name}</span> : null}
        {record.local_decision ? (
          <span className="local-decision-pill">{record.local_decision.decision} · local only</span>
        ) : null}
        {record.stale ? <span className="warn-text">stale</span> : null}
      </div>
    </button>
  );
}

function DecisionPanel({
  record,
  projects,
  onChanged,
}: {
  record: IntegrationRecord;
  projects: Project[];
  onChanged: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [projectId, setProjectId] = useState(record.project_id ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReason("");
    setProjectId(record.project_id ?? "");
    setError(null);
  }, [record.id, record.project_id]);

  async function decide(decision: string) {
    setBusy(decision);
    setError(null);
    try {
      await api.post(`/api/integrations/${record.application_id}/resources/${record.id}/decision`, {
        decision,
        reason,
      });
      toast.push("success", `Decision recorded locally: ${decision}`);
      setReason("");
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not record decision", message);
    } finally {
      setBusy(null);
    }
  }

  async function associate() {
    setBusy("associate");
    setError(null);
    try {
      await api.patch(`/api/integrations/${record.application_id}/resources/${record.id}`, {
        project_id: projectId || null,
      });
      toast.push("success", projectId ? "Associated with project" : "Project association removed");
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not associate project", message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="decision-box">
      <div className="decision-box-head">
        <div>
          <span className="eyebrow">Human decision</span>
          <p className="muted small">{decisionHelp}</p>
        </div>
        {record.local_decision ? (
          <ProvenanceBadge value="user" />
        ) : null}
      </div>
      {record.local_decision ? (
        <div className="latest-local-decision">
          <strong>{record.local_decision.decision}</strong>
          <span>{formatDateTime(record.local_decision.decided_at)}</span>
          <span className="tag">Sync: {record.local_decision.sync_state.replace(/_/g, " ")}</span>
          {record.local_decision.reason ? <p>{record.local_decision.reason}</p> : null}
        </div>
      ) : null}
      <label className="field">
        <span>Reason (optional)</span>
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Why this decision?"
        />
      </label>
      <InlineError message={error} />
      <div className="button-row">
        {record.decision_options.map((decision) => (
          <button
            className="button button-secondary button-small"
            key={decision}
            disabled={busy !== null}
            onClick={() => void decide(decision)}
          >
            {titleCase(decision)}
          </button>
        ))}
      </div>
      <div className="association-row">
        <label className="field">
          <span>Project context</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">No project</option>
            {projects.map((project) => (
              <option value={project.id} key={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button button-ghost button-small"
          onClick={() => void associate()}
          disabled={busy !== null || projectId === (record.project_id ?? "")}
        >
          Associate
        </button>
      </div>
    </div>
  );
}

function NextDetail({ record }: { record: IntegrationRecord }) {
  const data = record.data;
  return (
    <>
      <div className="detail-section">
        <h3>Why it might matter</h3>
        <p>{data.what_discovered || data.description || record.summary}</p>
        {data.capability_unlocked ? (
          <p className="detail-emphasis">{data.capability_unlocked}</p>
        ) : null}
      </div>
      <div className="detail-grid">
        <div>
          <span className="eyebrow">Assessment</span>
          <dl className="kv-list">
            {Object.entries(data.scores || {}).map(([key, value]) =>
              value != null ? (
                <KeyValue key={key} label={titleCase(key)}>
                  {String(value)}
                </KeyValue>
              ) : null,
            )}
            <KeyValue label="Queue">{titleCase(String(data.queue_type || "unknown"))}</KeyValue>
            <KeyValue label="Evaluation">{data.evaluation_basis || "Not stated"}</KeyValue>
            <KeyValue label="Research">{titleCase(String(data.research_status || "not started"))}</KeyValue>
          </dl>
        </div>
        <div>
          <span className="eyebrow">Experiment</span>
          <p className="small">{data.simplest_experiment || "No experiment proposed."}</p>
          <span className="eyebrow detail-gap">Falsification</span>
          <p className="small">{data.falsification || "Not stated."}</p>
        </div>
      </div>
      {data.items?.length ? (
        <div className="detail-section">
          <h3>Source items</h3>
          <ul className="evidence-links">
            {data.items.map((item: Record<string, unknown>, index: number) => (
              <li key={`${item.id}-${index}`}>
                {typeof item.url === "string" ? (
                  <a href={item.url} target="_blank" rel="noreferrer">
                    {String(item.title || item.url)} <ExternalLink size={11} />
                  </a>
                ) : (
                  String(item.title || item.id)
                )}
                <span>{String(item.source || "")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.source_decision_history?.length ? (
        <details className="json-details">
          <summary>Next's recorded decision history</summary>
          <pre>{JSON.stringify(data.source_decision_history, null, 2)}</pre>
        </details>
      ) : null}
    </>
  );
}

function WorkDetail({ record }: { record: IntegrationRecord }) {
  const data = record.data;
  const qualification = data.qualification || {};
  return (
    <>
      <div className="detail-grid">
        <div>
          <span className="eyebrow">Opportunity</span>
          <dl className="kv-list">
            <KeyValue label="Organisation">{data.buyer || "Not stated"}</KeyValue>
            <KeyValue label="Location">{data.location || "Unknown"}</KeyValue>
            <KeyValue label="Remote">{data.remote == null ? "Unknown" : data.remote ? "Yes" : "No"}</KeyValue>
            <KeyValue label="Track">{titleCase(String(data.track || "unknown"))}</KeyValue>
            <KeyValue label="Availability">{titleCase(String(data.availability || "unknown"))}</KeyValue>
            <KeyValue label="Source">{data.source || "Not stated"}</KeyValue>
          </dl>
        </div>
        <div>
          <span className="eyebrow">Qualification</span>
          <dl className="kv-list">
            <KeyValue label="Qualified">{qualification.qualified ? "Yes" : "No"}</KeyValue>
            <KeyValue label="Score">{qualification.score ?? "Not stated"}</KeyValue>
            <KeyValue label="Bucket">{titleCase(String(qualification.bucket || "unknown"))}</KeyValue>
            <KeyValue label="Policy">{qualification.policy || "Not stated"}</KeyValue>
            <KeyValue label="Evidence mode">{qualification.evidence_mode || "Not stated"}</KeyValue>
          </dl>
        </div>
      </div>
      <div className="detail-section">
        <h3>Next action</h3>
        <p>{qualification.next_action || "No next action supplied."}</p>
        {qualification.stop_condition ? (
          <p className="muted small">Stop condition: {qualification.stop_condition}</p>
        ) : null}
      </div>
      <div className="detail-grid">
        <div>
          <span className="eyebrow">Unknowns and blockers</span>
          <ul className="plain-list">
            {[...(qualification.blocked || []), ...(qualification.unknowns || [])].slice(0, 8).map((item: string) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <span className="eyebrow">Compensation</span>
          <dl className="kv-list">
            <KeyValue label="Amount">
              {data.compensation?.amount != null
                ? `${data.compensation.amount} ${data.compensation.currency || ""}`
                : "Not stated"}
            </KeyValue>
            <KeyValue label="Type">{titleCase(String(data.compensation?.money_type || "unknown"))}</KeyValue>
            <KeyValue label="Basis">{data.compensation?.basis || "Not stated"}</KeyValue>
          </dl>
          <p className="muted small">
            Listed value is not earned income. Work reports outcomes separately.
          </p>
        </div>
      </div>
    </>
  );
}

function CoCoderDetail({ record }: { record: IntegrationRecord }) {
  const data = record.data;
  return (
    <>
      <div className="detail-grid">
        <div>
          <span className="eyebrow">Finding</span>
          <dl className="kv-list">
            <KeyValue label="Severity">{titleCase(String(data.severity || "unknown"))}</KeyValue>
            <KeyValue label="Confidence">{titleCase(String(data.confidence || "unknown"))}</KeyValue>
            <KeyValue label="Claim type">{titleCase(String(data.claim_type || "unknown"))}</KeyValue>
            <KeyValue label="Rule">{data.rule_code || "Not stated"}</KeyValue>
            <KeyValue label="Category">{data.category || "Not stated"}</KeyValue>
          </dl>
        </div>
        <div>
          <span className="eyebrow">Scope</span>
          <dl className="kv-list">
            <KeyValue label="Repository">
              <PathText>{data.repository_path || "Not recorded"}</PathText>
            </KeyValue>
            <KeyValue label="Revision">{`${data.base || "?"}..${data.head || "?"}`}</KeyValue>
            <KeyValue label="Artifact">
              <PathText>{data.artifact_path || "Not recorded"}</PathText>
            </KeyValue>
          </dl>
        </div>
      </div>
      <div className="detail-section">
        <h3>Statement</h3>
        <p>{data.statement || record.summary}</p>
        {data.question ? <p className="detail-emphasis">{data.question}</p> : null}
        {data.remediation ? <p className="small">Remediation: {data.remediation}</p> : null}
      </div>
      {data.affected_paths?.length ? (
        <div className="detail-section">
          <h3>Affected paths</h3>
          <div className="tag-row">
            {data.affected_paths.map((path: string) => (
              <Tag key={path}>{path}</Tag>
            ))}
          </div>
        </div>
      ) : null}
      {data.unknowns?.length ? (
        <div className="detail-section">
          <h3>Unknowns</h3>
          <ul className="plain-list">
            {data.unknowns.slice(0, 10).map((item: string) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

function OperationsPanel({
  integration,
  executions,
  onReload,
}: {
  integration: Integration;
  executions: IntegrationExecution[];
  onReload: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repoPath, setRepoPath] = useState(integration.repositories[0]?.path ?? "");
  const [base, setBase] = useState("HEAD~1");
  const [head, setHead] = useState("HEAD");
  const [request, setRequest] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(180);
  const [expandedExecution, setExpandedExecution] = useState<string | null>(
    executions[0]?.id ?? null,
  );

  useEffect(() => {
    if (!repoPath && integration.repositories.length) {
      setRepoPath(integration.repositories[0].path);
    }
  }, [integration.repositories, repoPath]);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/integrations/${integration.application_id}/refresh`);
      toast.push("success", `${integration.name} refreshed`);
      onReload();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Refresh failed", message);
    } finally {
      setBusy(false);
    }
  }

  async function runReview() {
    if (!window.confirm(`Run a CoCoder review on ${repoPath}?\n\nBase: ${base}\nHead: ${head}`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const execution = await api.post<IntegrationExecution>(
        `/api/integrations/${integration.application_id}/actions/run_review/execute`,
        {
          parameters: {
            repo_path: repoPath,
            base,
            head,
            request,
            timeout_seconds: timeoutSeconds,
          },
          confirm: true,
        },
      );
      toast.push("info", "Review queued", "Mission Control is executing a bounded local CoCoder review.");
      setExpandedExecution(execution.id);
      onReload();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not start review", message);
    } finally {
      setBusy(false);
    }
  }

  const reviewAction = integration.actions.find((action) => action.id === "run_review");

  return (
    <>
      <div className="operations-toolbar">
        <button className="button button-secondary button-small" onClick={() => void refresh()} disabled={busy}>
          <RefreshCw size={14} className={busy ? "spin" : ""} /> Refresh read model
        </button>
        <span className="muted small">
          {integration.mode} · last checked {integration.last_checked_at ? timeAgo(integration.last_checked_at) : "never"}
        </span>
      </div>
      <InlineError message={error} />
      {integration.actions.map((action) => (
        <div className={`operation-card ${action.enabled ? "" : "disabled"}`} key={action.id}>
          <div className="operation-head">
            <div>
              <span className="eyebrow">{titleCase(action.risk)} · {titleCase(action.side_effect)}</span>
              <h3>{action.title}</h3>
            </div>
            <SimpleStatusBadge
              state={action.enabled ? "available" : "unavailable"}
              label={action.enabled ? "Supported" : "Blocked"}
            />
          </div>
          <p>{action.description}</p>
          {!action.enabled ? <p className="warn-text small">{action.unavailable_reason}</p> : null}
          {action.id === "run_review" && action.enabled && integration.application_id === "cocoder" ? (
            <div className="operation-form form-stack">
              <div className="form-grid two">
                <label className="field">
                  <span>Repository</span>
                  <select value={repoPath} onChange={(event) => setRepoPath(event.target.value)}>
                    {integration.repositories.map((repository) => (
                      <option value={repository.path} key={repository.path}>
                        {repository.name} ({repository.source})
                      </option>
                    ))}
                  </select>
                </label>
                <div className="form-grid two">
                  <label className="field">
                    <span>Base</span>
                    <input value={base} onChange={(event) => setBase(event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Head</span>
                    <input value={head} onChange={(event) => setHead(event.target.value)} />
                  </label>
                </div>
              </div>
              <label className="field">
                <span>Intent (optional)</span>
                <input
                  value={request}
                  onChange={(event) => setRequest(event.target.value)}
                  placeholder="Why this change exists; CoCoder reports where it cannot connect the diff."
                />
              </label>
              <div className="form-grid two">
                <label className="field">
                  <span>Timeout (seconds)</span>
                  <input
                    type="number"
                    min={10}
                    max={300}
                    value={timeoutSeconds}
                    onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
                  />
                </label>
                <div className="operation-submit">
                  <button className="button button-primary" onClick={() => void runReview()} disabled={busy || !repoPath}>
                    <Play size={14} /> {busy ? "Starting…" : "Run bounded review"}
                  </button>
                </div>
              </div>
              {reviewAction ? <p className="muted small">Requires explicit confirmation; artifacts remain under Mission Control data.</p> : null}
            </div>
          ) : null}
        </div>
      ))}
      <Section title="Execution history" description="Queued is not completed. Full lifecycle is retained locally.">
        {executions.length ? (
          <div className="execution-list">
            {executions.map((execution) => (
              <div className="execution-row" key={execution.id}>
                <button
                  className="execution-summary"
                  onClick={() =>
                    setExpandedExecution((current) => (current === execution.id ? null : execution.id))
                  }
                >
                  <span>
                    <strong>{execution.action_id}</strong>
                    <span>{execution.started_at ? formatDateTime(execution.started_at) : formatDateTime(execution.created_at)}</span>
                  </span>
                  <SimpleStatusBadge
                    state={
                      execution.status === "succeeded"
                        ? "running"
                        : execution.status === "failed"
                          ? "launch_failed"
                          : "in_progress"
                    }
                    label={titleCase(execution.status)}
                  />
                  <ChevronRight size={14} className={expandedExecution === execution.id ? "rotate-90" : ""} />
                </button>
                {expandedExecution === execution.id ? (
                  <div className="execution-detail">
                    <div className="inline-meta">
                      <span>Risk: {titleCase(execution.risk)}</span>
                      <span>Exit {execution.exit_code ?? "—"}</span>
                      {execution.artifact_ref ? <PathText>{execution.artifact_ref}</PathText> : null}
                    </div>
                    {execution.error ? <InlineError message={execution.error} /> : null}
                    <pre className="log-view">{execution.output || "No output yet."}</pre>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No actions executed" description="Approved integration actions will appear here." icon={<Play size={18} />} />
        )}
      </Section>
    </>
  );
}

function DetailView({
  record,
  projects,
  onChanged,
}: {
  record: IntegrationRecord;
  projects: Project[];
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const [proposing, setProposing] = useState(false);
  const canProposeWorkflow =
    record.application_id === "next" &&
    record.title.includes("TraceLite") &&
    record.state === "NEW";

  async function proposeWorkflow() {
    setProposing(true);
    try {
      const workflow = await api.post<ExperimentWorkflow>("/api/workflows", {
        record_id: record.id,
        template: "trace_reduce_v1",
        force_new: true,
      });
      toast.push("success", "Experiment proposal created", "Review the scope before approving.");
      navigate(`/workflows/${workflow.id}`);
    } catch (caught) {
      toast.push("error", "Could not create experiment proposal", errorMessage(caught));
    } finally {
      setProposing(false);
    }
  }

  return (
    <article className="record-detail">
      <header className="record-detail-head">
        <div>
          <span className="eyebrow">{titleCase(record.resource_type)} · {record.application_name}</span>
          <h2>{record.title}</h2>
          <div className="inline-meta">
            <SimpleStatusBadge state={record.stale ? "stale" : "running"} label={record.state || titleCase(record.resource_type)} />
            {record.project_name ? <span>{record.project_name}</span> : null}
            <span>{record.source_timestamp ? formatDateTime(record.source_timestamp) : formatDateTime(record.observed_at)}</span>
            {record.stale ? <span className="warn-text">Observation stale</span> : null}
          </div>
        </div>
        <span className="integration-detail-icon" aria-hidden="true">
          <FileJson size={20} />
        </span>
      </header>
      <div className="source-attribution">
        <span>Source <strong>{record.application_name}</strong></span>
        <span>{record.source_version || "version not stated"}</span>
        <span>Observed {timeAgo(record.observed_at)}</span>
      </div>
      {canProposeWorkflow ? (
        <div className="workflow-cta">
          <div>
            <span className="eyebrow">MC10 cross-application experiment</span>
            <p>Create a bounded proposal for human approval. No Worker execution occurs until you approve the scope.</p>
          </div>
          <button className="button button-primary button-small" onClick={() => void proposeWorkflow()} disabled={proposing}>
            <Sparkles size={14} /> {proposing ? "Proposing…" : "Propose TraceLite experiment"}
          </button>
        </div>
      ) : null}
      {record.application_id === "next" ? <NextDetail record={record} /> : null}
      {record.application_id === "work" ? <WorkDetail record={record} /> : null}
      {record.application_id === "cocoder" ? <CoCoderDetail record={record} /> : null}
      {record.evidence.length ? (
        <details className="json-details">
          <summary>Evidence references ({record.evidence.length})</summary>
          <ul>
            {record.evidence.map((item) => (
              <li key={item}><code>{item}</code></li>
            ))}
          </ul>
        </details>
      ) : null}
      <details className="json-details">
        <summary>Raw source payload</summary>
        <pre>{JSON.stringify(record.data, null, 2)}</pre>
      </details>
      <DecisionPanel record={record} projects={projects} onChanged={onChanged} />
    </article>
  );
}

export function IntegrationWorkspacePage({ appId }: { appId: "next" | "work" | "cocoder" }) {
  const config = configs[appId];
  const Icon = config.icon;
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("record");
  const [activeTab, setActiveTab] = useState(config.tabs[0].id);
  const [searchText, setSearchText] = useState("");
  const integration = useApi<Integration>(`/api/integrations/${appId}`, { pollMs: 45000 });
  const projects = useApi<Project[]>("/api/projects");
  const tab = config.tabs.find((item) => item.id === activeTab) ?? config.tabs[0];
  const recordPath = tab.resourceType
    ? apiPath(`/api/integrations/${appId}/resources`, {
        resource_type: tab.resourceType,
        limit: 400,
      })
    : null;
  const records = useApi<IntegrationRecord[]>(recordPath);
  const detail = useApi<IntegrationRecord>(
    selectedId ? `/api/integrations/${appId}/resources/${selectedId}` : null,
  );
  const overview = useApi<IntegrationRecord[]>(
    activeTab === "overview"
      ? apiPath(`/api/integrations/${appId}/resources`, { resource_type: config.mainResource, limit: 6 })
      : null,
  );
  const decisions = useApi<IntegrationDecision[]>(
    tab.special === "decisions" ? `/api/integrations/${appId}/decisions` : null,
  );
  const executions = useApi<IntegrationExecution[]>(
    tab.special === "operations"
      ? apiPath("/api/integrations/executions", { application_id: appId, limit: 12 })
      : null,
    { pollMs: 2500 },
  );

  useEffect(() => {
    if (selectedId && detail.data) {
      const matchingTab = config.tabs.find(
        (item) => item.resourceType === detail.data?.resource_type,
      );
      if (matchingTab) setActiveTab(matchingTab.id);
    }
  }, [selectedId, detail.data, config.tabs]);

  const filteredRecords = useMemo(() => {
    let rows = records.data ?? [];
    if (tab.filter) rows = rows.filter(tab.filter);
    if (searchText.trim()) {
      const needle = searchText.toLocaleLowerCase();
      rows = rows.filter(
        (record) =>
          record.title.toLocaleLowerCase().includes(needle) ||
          record.summary.toLocaleLowerCase().includes(needle) ||
          record.state.toLocaleLowerCase().includes(needle),
      );
    }
    return rows;
  }, [records.data, tab, searchText]);

  async function refreshAll() {
    try {
      await api.post(`/api/integrations/${appId}/refresh`);
    } catch {
      // The integration panel shows the diagnostic.
    }
    integration.reload();
    records.reload();
    overview.reload();
    executions.reload();
    detail.reload();
  }

  return (
    <div className="page engine-page">
      <PageHeader
        eyebrow={config.eyebrow}
        title={config.title}
        description={config.description}
        actions={
          <>
            <button
              className="button button-secondary"
              onClick={() => {
                integration.reload();
                records.reload();
                overview.reload();
                executions.reload();
              }}
            >
              <RefreshCw size={15} /> Refresh view
            </button>
            <Link className="button button-primary" to="/inbox">
              <Sparkles size={15} /> Review inbox
            </Link>
          </>
        }
      />

      {integration.loading && !integration.data ? <LoadingBlock label={`Connecting to ${config.title}`} /> : null}
      {integration.error ? <ErrorState message={integration.error.message} onRetry={integration.reload} /> : null}
      {integration.data ? (
        <div className={`integration-banner ${integration.data.available ? "available" : "unavailable"}`}>
          <div className="integration-banner-main">
            <span className="integration-logo"><Icon size={20} /></span>
            <div>
              <strong>
                {integration.data.available ? "Live integration available" : "Integration unavailable"}
              </strong>
              <p>{integration.data.detail}</p>
              {integration.data.error ? <p className="warn-text small">{truncate(integration.data.error, 400)}</p> : null}
            </div>
          </div>
          <div className="integration-banner-meta">
            <span>Mode: {integration.data.mode}</span>
            <span>Protocol: {integration.data.protocol_version}</span>
            <span>Last sync: {integration.data.last_checked_at ? timeAgo(integration.data.last_checked_at) : "never"}</span>
            <button className="text-link" onClick={() => void refreshAll()}>
              Refresh source <RefreshCw size={12} />
            </button>
            <Link className="text-link" to="/integrations">Configure</Link>
          </div>
        </div>
      ) : null}

      {integration.data ? (
        <div className="engine-stat-strip">
          {Object.entries(integration.data.resource_counts).map(([type, count]) => (
            <Stat label={titleCase(type.replace(/_/g, " "))} value={count} key={type} />
          ))}
          <Stat label="Last source sync" value={integration.data.last_checked_at ? timeAgo(integration.data.last_checked_at) : "Never"} />
        </div>
      ) : null}

      <div className="engine-tabs" role="tablist" aria-label={`${config.title} sections`}>
        {config.tabs.map((item) => (
          <button
            role="tab"
            aria-selected={activeTab === item.id}
            className={activeTab === item.id ? "active" : ""}
            key={item.id}
            onClick={() => {
              setActiveTab(item.id);
              searchParams.delete("record");
              setSearchParams(searchParams, { replace: true });
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab.special === "overview" ? (
        <div className="engine-overview">
          <Section title="Source status" description="Observations are read from the source; this is a cached read model.">
            <div className="overview-grid">
              <div className="panel">
                <span className="eyebrow">Capabilities</span>
                <div className="tag-row">
                  {integration.data?.capabilities.map((capability) => (
                    <Tag key={capability} tone="accent">{capability}</Tag>
                  ))}
                </div>
                <p className="muted small overview-note">
                  Observations retain source identifiers and freshness. Local decisions never alter source state.
                </p>
              </div>
              <div className="panel">
                <span className="eyebrow">Read model</span>
                <dl className="kv-list">
                  <KeyValue label="Mode">{integration.data?.mode ?? "unknown"}</KeyValue>
                  <KeyValue label="Enabled">{integration.data?.enabled ? "Yes" : "No"}</KeyValue>
                  <KeyValue label="Available">{integration.data?.available ? "Yes" : "No"}</KeyValue>
                  <KeyValue label="Supporting actions">
                    {integration.data?.actions.length ?? 0}
                  </KeyValue>
                </dl>
              </div>
            </div>
          </Section>
          <Section title="Latest records" description="Open any record to inspect evidence and record a local decision.">
            {overview.loading ? <LoadingBlock label="Loading latest records" compact /> : null}
            {overview.data?.length ? (
              <div className="overview-records">
                {overview.data.map((record) => (
                  <button
                    key={record.id}
                    className="overview-record"
                    onClick={() => {
                      searchParams.set("record", record.id);
                      setSearchParams(searchParams);
                    }}
                  >
                    <span>{titleCase(record.resource_type.replace(/_/g, " "))}</span>
                    <strong>{record.title}</strong>
                    <small>{truncate(record.summary, 180)}</small>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No records available"
                description={`Refresh ${config.title} or configure its integration in Settings.`}
                icon={<CircleSlash size={18} />}
              />
            )}
          </Section>
        </div>
      ) : null}

      {tab.special === "decisions" ? (
        <Section title="Local decisions" description="Human decisions are stored by Mission Control with source identity.">
          {decisions.loading ? <LoadingBlock label="Loading decisions" compact /> : null}
          {decisions.data?.length ? (
            <div className="decision-table">
              {decisions.data.map((decision) => (
                <div className="decision-table-row" key={decision.id}>
                  <span className="tag">{decision.decision}</span>
                  <div>
                    <strong>{decision.resource_type.replace(/_/g, " ")}</strong>
                    <span>{decision.external_id}</span>
                  </div>
                  <span>{decision.reason || "No reason"}</span>
                  <span className="decision-sync">{decision.sync_state.replace(/_/g, " ")}</span>
                  <time>{timeAgo(decision.decided_at)}</time>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No local decisions" description="Decisions made in the workspaces will appear here." icon={<Sparkles size={18} />} />
          )}
        </Section>
      ) : null}

      {tab.special === "repositories" ? (
        <Section title="Registered repositories" description="CoCoder may review these repositories; no other path is accepted.">
          {integration.data?.repositories.length ? (
            <div className="repo-review-grid">
              {integration.data.repositories.map((repository) => (
                <div className="repo-review-card" key={repository.path}>
                  <div>
                    <strong>{repository.name}</strong>
                    <PathText>{repository.path}</PathText>
                  </div>
                  <Tag>{repository.source}</Tag>
                  <button
                    className="button button-secondary button-small"
                    onClick={() => {
                      setActiveTab("operations");
                      searchParams.delete("record");
                      setSearchParams(searchParams, { replace: true });
                    }}
                  >
                    Review from Operations <ChevronRight size={13} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No registered repositories" description="Add a project or application repository first." />
          )}
        </Section>
      ) : null}

      {tab.special === "results" ? (
        <Section title="Realised outcomes" description="Work outcomes and income are separate from opportunity estimates.">
          <EmptyState
            title="No realised income records available"
            description="The read-only Work CLI export does not provide verified payments or outcomes. Mission Control does not infer income from listings or outreach."
            icon={<BriefcaseBusiness size={18} />}
          />
        </Section>
      ) : null}

      {tab.special === "operations" ? (
        <Section title="Operations" description="Only registered, bounded actions are available. The browser never supplies a command.">
          {integration.data ? (
            <OperationsPanel
              integration={integration.data}
              executions={executions.data ?? []}
              onReload={() => {
                integration.reload();
                records.reload();
                overview.reload();
                executions.reload();
              }}
            />
          ) : null}
        </Section>
      ) : null}

      {tab.special !== "overview" &&
      tab.special !== "decisions" &&
      tab.special !== "operations" &&
      tab.special !== "repositories" &&
      tab.special !== "results" ? (
        <div className={`resource-layout ${selectedId ? "has-detail" : ""}`}>
          <div className="resource-list-panel">
            <div className="resource-toolbar">
              <label className="search-field">
                <Search size={15} />
                <input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder={`Search ${config.title} records`}
                  aria-label={`Search ${config.title} records`}
                />
              </label>
              <span className="toolbar-count">{filteredRecords.length} records</span>
            </div>
            {records.loading ? <LoadingBlock label="Loading source records" compact /> : null}
            {records.error ? <ErrorState message={records.error.message} onRetry={records.reload} /> : null}
            {!records.loading && filteredRecords.length === 0 ? (
              <EmptyState
                title={`No ${tab.label.toLowerCase()} available`}
                description={
                  integration.data?.available
                    ? "The source returned no matching records. Mission Control does not substitute fixture data."
                    : integration.data?.detail ?? "Configure the integration to load real records."
                }
                icon={<CircleSlash size={18} />}
                action={
                  <button className="button button-secondary button-small" onClick={() => void refreshAll()}>
                    Refresh source
                  </button>
                }
              />
            ) : null}
            <div className="resource-list">
              {filteredRecords.map((record) => (
                <ResourceRow
                  key={record.id}
                  record={record}
                  active={selectedId === record.id}
                  onSelect={() => {
                    searchParams.set("record", record.id);
                    setSearchParams(searchParams);
                  }}
                />
              ))}
            </div>
          </div>
          <div className="resource-detail-panel">
            {detail.loading ? <LoadingBlock label="Loading source record" /> : null}
            {detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} /> : null}
            {detail.data ? (
              <DetailView
                record={detail.data}
                projects={projects.data ?? []}
                onChanged={() => {
                  detail.reload();
                  records.reload();
                  decisions.reload();
                }}
              />
            ) : (
              <div className="detail-empty">
                <FileJson size={26} />
                <h3>Select a record</h3>
                <p>Open a source record to inspect evidence, make a local decision, or associate it with a project.</p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
