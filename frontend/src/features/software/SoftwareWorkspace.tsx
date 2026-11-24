import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import {
  InlineError,
  LoadingBlock,
  PathText,
  Section,
  SimpleStatusBadge,
  Tag,
} from "../../components/ui";
import { InspectPanel, InspectProjectBlock } from "../../features/inspect/InspectPanels";
import { WorkerRuntimePanel } from "../worker/WorkerRuntimePanel";
import { copyText } from "../../lib/clipboard";
import { formatDateTime, timeAgo } from "../../lib/format";
import type {
  Application,
  ProjectDetail,
  ProjectGitLink,
} from "../../types/api";
import { AdapterCard, CheckpointForm, RecommendationRow, TaskRow } from "../project/shared";
import { FindingsSection, PromptsSection, SoftwareQualityTab } from "./SoftwareQualityTab";

type TabId = "overview" | "activity" | "inspect" | "quality" | "improvements" | "context";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "activity", label: "Activity" },
  { id: "inspect", label: "Inspect" },
  { id: "quality", label: "Quality" },
  { id: "improvements", label: "Improvements" },
  { id: "context", label: "Context" },
];

function CopyBlock({ text, label }: { text: string; label: string }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await copyText(text);
      setCopied(true);
      toast.push("success", "Copied", "Paste it into your local agent. Nothing was executed.");
      window.setTimeout(() => setCopied(false), 2000);
    } catch (caught) {
      toast.push("error", "Could not copy", errorMessage(caught));
    }
  }
  return (
    <div>
      <pre className="log-view" style={{ whiteSpace: "pre-wrap" }}>{text}</pre>
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={() => void copy()} aria-label={label}>
          <Copy size={13} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

export function SoftwareWorkspace({
  projectId,
  data,
  applications,
  onLaunchApp,
  onChanged,
}: {
  projectId: string;
  data: ProjectDetail;
  applications: Application[] | null;
  onLaunchApp: (app: Application) => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = useState<TabId>("overview");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskError, setTaskError] = useState<string | null>(null);
  const toast = useToast();

  async function addTask() {
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

  const openTasks = data.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
  const pendingRecs = data.recommendations.filter((rec) => rec.review_state === "pending");
  const linkedApps = (data.applications ?? [])
    .map((ref) => (applications ?? []).find((app) => app.id === ref.id))
    .filter((app): app is Application => Boolean(app));

  return (
    <div>
      <div className="button-row" role="tablist" aria-label="Project workspace sections">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            role="tab"
            aria-selected={tab === entry.id}
            className={`button button-small ${tab === entry.id ? "button-secondary" : "button-ghost"}`}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <SoftwareOverview
          data={data}
          projectId={projectId}
          linkedApps={linkedApps}
          onLaunchApp={onLaunchApp}
          onChanged={onChanged}
        />
      ) : null}

      {tab === "activity" ? <SoftwareActivity projectId={projectId} /> : null}

      {tab === "inspect" ? (
        data.inspect_project_id ? (
          <InspectProjectBlock inspectId={data.inspect_project_id} showHeader />
        ) : (
          <InspectPanel applicationIds={(data.applications ?? []).map((app) => app.id)} />
        )
      ) : null}

      {tab === "quality" ? <SoftwareQualityTab projectId={projectId} data={data} /> : null}

      {tab === "improvements" ? (
        <div>
          <FindingsSection projectId={projectId} />
          <PromptsSection projectId={projectId} />
          <Section
            title="Outstanding work"
            description="Open tasks and owner decisions pending. Prioritize by impact on the project goal."
            actions={<Tag tone={openTasks.length || pendingRecs.length ? "warn" : "accent"}>{openTasks.length + pendingRecs.length} open</Tag>}
          >
            <InlineError message={taskError} />
            <div className="inline-form">
              <input
                value={taskTitle}
                onChange={(event) => setTaskTitle(event.target.value)}
                placeholder="New task title"
                aria-label="New task title"
                size={40}
              />
              <button className="button button-secondary button-small" onClick={() => void addTask()}>
                Add task
              </button>
            </div>
            {openTasks.length === 0 ? (
              <p className="muted small">No open tasks. An empty list is not evidence of completeness.</p>
            ) : (
              <ul className="plain-list">
                {openTasks.map((task) => (
                  <TaskRow key={task.id} task={task} onChanged={onChanged} />
                ))}
              </ul>
            )}
          </Section>
          <Section
            title="Recommendations awaiting review"
            description="Owner decisions accept, defer or reject each recommendation with a recorded rationale."
          >
            {pendingRecs.length === 0 ? (
              <p className="muted small">No pending recommendations.</p>
            ) : (
              <ul className="plain-list">
                {pendingRecs.map((rec) => (
                  <RecommendationRow key={rec.id} recommendation={rec} onChanged={onChanged} />
                ))}
              </ul>
            )}
          </Section>
        </div>
      ) : null}

      {tab === "context" ? <SoftwareContext projectId={projectId} /> : null}
    </div>
  );
}

function SoftwareOverview({
  data,
  projectId,
  linkedApps,
  onLaunchApp,
  onChanged,
}: {
  data: ProjectDetail;
  projectId: string;
  linkedApps: Application[];
  onLaunchApp: (app: Application) => void;
  onChanged: () => void;
}) {
  const gitLinks = useApi<ProjectGitLink[]>(`/api/projects/${projectId}/git-links`);
  const checkpoint = data.latest_checkpoint;
  return (
    <div>
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

      <Section title="Purpose" description="What this system is for. A formal project charter arrives with the quality milestone; until then the recorded description stands.">
        <p>{data.description || "No description recorded."}</p>
        {data.notes ? <p className="muted small">{data.notes}</p> : null}
        <p className="muted small">Origin: {data.origin ?? "curated"} · Kind: {data.kind} · Status: {data.status}</p>
      </Section>

      <Section
        title="Repositories"
        description="Canonical identity is the Git repo_uid or normalized path. Missing checkouts are unavailable, never deleted."
      >
        {gitLinks.loading ? <LoadingBlock label="Loading repositories" compact /> : null}
        {gitLinks.error ? <InlineError message={gitLinks.error.message} /> : null}
        {(gitLinks.data ?? []).map((link) => (
          <div className="adapter-card" key={link.path}>
            <div className="adapter-head">
              <div>
                <strong>{link.role}</strong> · <PathText>{link.path}</PathText>
              </div>
              <SimpleStatusBadge state={link.accessible ? "running" : "unavailable"} label={link.accessible ? "Available" : "Unavailable"} />
            </div>
            <p className="muted small">
              {link.classification.replace(/_/g, " ")} · branch {link.branch ?? "unknown"} ·{" "}
              {link.head_sha ? link.head_sha.slice(0, 8) : "no commit indexed"} · {link.total_commits} commits
              {link.repo_uid ? ` · uid ${link.repo_uid.slice(0, 14)}…` : ""}
              {!link.backfill_complete ? " · backfill pending" : ""}
            </p>
          </div>
        ))}
        {gitLinks.data && gitLinks.data.length === 0 && !gitLinks.loading ? (
          <p className="muted small">No repository linked to this workspace yet.</p>
        ) : null}
      </Section>

      <Section
        title="Applications"
        description="Launching is owned by the application registry. This workspace never invents launch commands."
      >
        {linkedApps.length === 0 ? (
          <p className="muted small">
            No linked application. {data.applications.length ? (
              <>Linked ids: {data.applications.map((app) => app.name).join(", ")} — enable them under <Link className="text-link" to="/applications">Applications</Link>.</>
            ) : "Register one under Applications when the system is genuinely launchable."}
          </p>
        ) : (
          linkedApps.map((app) => (
            <div className="adapter-card" key={app.id}>
              <div className="adapter-head">
                <div>
                  <strong>{app.name}</strong>
                </div>
                <div className="button-row">
                  <Link className="button button-secondary button-small" to="/applications">
                    Open Application
                  </Link>
                  <button
                    className="button button-primary button-small"
                    disabled={!app.actions.launch.enabled}
                    title={app.actions.launch.reason ?? "Launch via the authorized registry definition"}
                    onClick={() => onLaunchApp(app)}
                  >
                    Launch
                  </button>
                </div>
              </div>
              <p className="muted small">{app.status.label} — {app.status.detail.slice(0, 200)}</p>
              {!app.actions.launch.enabled && app.actions.launch.reason ? (
                <p className="warn-text small">{app.actions.launch.reason}</p>
              ) : null}
            </div>
          ))
        )}
      </Section>

      <Section title="Checkpoint and resume" description="Persisted locally. Restarting Mission Control does not lose it.">
        {checkpoint ? (
          <p>
            <strong>{checkpoint.summary}</strong>
            <br />
            <span className="muted small">Next: {checkpoint.next_action || data.next_action || "not recorded"}</span>
          </p>
        ) : (
          <p className="muted small">No checkpoint recorded yet.</p>
        )}
        <CheckpointForm projectId={projectId} onSaved={onChanged} />
      </Section>

      <WorkerRuntimePanel />
    </div>
  );
}

function SoftwareActivity({ projectId }: { projectId: string }) {
  const toast = useToast();
  const links = useApi<ProjectGitLink[]>(`/api/projects/${projectId}/git-links`);
  const [repoId, setRepoId] = useState<string | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [mode, setMode] = useState("review");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);

  const activeRepoId = repoId ?? (links.data ?? []).find((link) => link.git_repo_id)?.git_repo_id ?? null;
  const timeline = useApi<{ items: Array<Record<string, unknown>>; total: number; partial: boolean }>(
    activeRepoId ? `/api/git-activity/timeline?repo_id=${activeRepoId}&preset=30d&limit=50` : null,
  );
  const commit = useApi<Record<string, unknown>>(
    activeRepoId && sha ? `/api/git-activity/commits/${activeRepoId}/${sha}` : null,
  );
  const models = useApi<{ models?: Array<{ id: string }> }>(activeRepoId ? "/api/git-activity/models" : null);

  async function prepareDailyPrompt() {
    if (!activeRepoId) return;
    setBusy("prompt");
    setPrompt(null);
    try {
      const result = await api.post<Record<string, unknown>>("/api/git-activity/daily/prompt", {
        repo_id: activeRepoId, date, timezone: "Europe/Dublin", mode, profile: "code",
      });
      const markdown = String((result.markdown ?? result.prompt ?? "") || "");
      setPrompt(markdown || JSON.stringify(result, null, 2).slice(0, 8000));
      toast.push("success", "Evidence package prepared", "Review it, then run the review explicitly.");
    } catch (caught) {
      toast.push("error", "Could not prepare prompt", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function requestDailyReview() {
    if (!activeRepoId) return;
    setBusy("review");
    try {
      const review = await api.post<Record<string, unknown>>("/api/git-activity/daily/reviews", {
        repo_id: activeRepoId, date, timezone: "Europe/Dublin", mode, profile: "code", model: model || undefined,
      });
      toast.push("success", "Daily review requested", String(review.id ?? ""));
    } catch (caught) {
      toast.push("error", "Could not request review", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  const items = (timeline.data?.items ?? []) as Array<Record<string, unknown>>;
  const detail = (commit.data?.commit ?? {}) as Record<string, unknown>;

  return (
    <div>
      <Section
        title="Commit activity"
        description="Read-only Git history. Reviews are assessments of this evidence, never scores."
        actions={timeline.data?.partial ? <Tag tone="warn">Index backfill pending</Tag> : undefined}
      >
        {links.loading ? <LoadingBlock label="Loading repositories" compact /> : null}
        {(links.data ?? []).filter((link) => link.git_repo_id).length > 1 ? (
          <label className="muted small">
            Repository{" "}
            <select value={activeRepoId ?? ""} onChange={(event) => { setRepoId(event.target.value || null); setSha(null); }} aria-label="Activity repository">
              {(links.data ?? []).filter((link) => link.git_repo_id).map((link) => (
                <option key={link.git_repo_id as string} value={link.git_repo_id as string}>
                  {link.path}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {timeline.loading ? <LoadingBlock label="Loading commits" compact /> : null}
        {timeline.error ? <InlineError message={timeline.error.message} /> : null}
        {!activeRepoId && !links.loading ? (
          <p className="muted small">No Git-indexed repository yet. Run a Git activity scan, then return here.</p>
        ) : null}
        {activeRepoId && items.length === 0 && !timeline.loading ? (
          <p className="muted small">No commits indexed in the last 30 days. Missing history is reported, never zero-filled.</p>
        ) : null}
        <ul className="plain-list">
          {items.map((item) => (
            <li key={String(item.sha)}>
              <button
                className="writer-queue-row"
                onClick={() => setSha(String(item.sha))}
                aria-expanded={sha === String(item.sha)}
              >
                <span className="writer-queue-main">
                  <strong>{String(item.subject ?? "")}</strong>
                  <small>
                    {String(item.short_sha ?? "").slice(0, 8)} · {String(item.author_name ?? "")} ·{" "}
                    {formatDateTime(new Date(Number(item.committer_ts ?? 0) * 1000).toISOString())} ·{" "}
                    {String(item.review_status ?? "awaiting")}
                  </small>
                </span>
              </button>
              {sha === String(item.sha) ? (
                <div className="writer-chapter-detail">
                  {commit.loading ? <LoadingBlock label="Loading commit" compact /> : null}
                  {commit.error ? <InlineError message={commit.error.message} /> : null}
                  {detail.sha ? (
                    <>
                      <p className="muted small">{String(detail.body ?? "").slice(0, 1200)}</p>
                      <p className="muted small">
                        {Number(detail.files_changed ?? 0)} files · +{Number(detail.insertions ?? 0)}/-
                        {Number(detail.deletions ?? 0)}
                      </p>
                      <CommitPrompt repoId={activeRepoId as string} sha={String(item.sha)} />
                    </>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Review recent development"
        description="Prepare a bounded evidence package, review it, then request an AI review explicitly. Nothing runs implicitly."
      >
        <div className="inline-form">
          <label className="muted small">
            Date{" "}
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} aria-label="Review date" />
          </label>
          <label className="muted small">
            Mode{" "}
            <select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="Review mode">
              <option value="review">Review</option>
              <option value="explain">Explain</option>
            </select>
          </label>
          <label className="muted small">
            Model{" "}
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder={(models.data?.models?.[0]?.id as string) ?? "default route"}
              aria-label="Review model"
              size={28}
              list="git-models"
            />
          </label>
          <datalist id="git-models">
            {(models.data?.models ?? []).map((entry) => (
              <option key={entry.id} value={entry.id} />
            ))}
          </datalist>
          <button className="button button-secondary button-small" disabled={!activeRepoId || busy !== null} onClick={() => void prepareDailyPrompt()}>
            {busy === "prompt" ? "Preparing…" : "Prepare evidence package"}
          </button>
          <button className="button button-primary button-small" disabled={!activeRepoId || busy !== null} onClick={() => void requestDailyReview()}>
            {busy === "review" ? "Requesting…" : "Request daily review"}
          </button>
        </div>
        {prompt ? <CopyBlock text={prompt} label="Copy daily review prompt" /> : null}
      </Section>
    </div>
  );
}

function CommitPrompt({ repoId, sha }: { repoId: string; sha: string }) {
  const toast = useToast();
  const [prompt, setPrompt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function prepare() {
    setBusy(true);
    try {
      const result = await api.get<Record<string, unknown>>(
        `/api/git-activity/commits/${repoId}/${sha}/prompt?profile=code`,
      );
      const markdown = String((result.markdown ?? "") || "");
      setPrompt(markdown || JSON.stringify(result, null, 2).slice(0, 8000));
    } catch (caught) {
      toast.push("error", "Could not prepare prompt", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="button-row">
        <button className="button button-secondary button-small" disabled={busy} onClick={() => void prepare()}>
          {busy ? "Preparing…" : "Copy review prompt"}
        </button>
      </div>
      {prompt ? <CopyBlock text={prompt} label="Copy commit review prompt" /> : null}
    </div>
  );
}

function SoftwareContext({ projectId }: { projectId: string }) {
  const links = useApi<ProjectGitLink[]>(`/api/projects/${projectId}/git-links`);
  return (
    <div>
      <Section
        title="Agent instructions & project context"
        description="README, AGENTS.md and DESCRIPTION.md readiness per repository. Proposals are diffs — applying them is explicit and modifies the repository."
      >
        {links.loading ? <LoadingBlock label="Loading repositories" compact /> : null}
        {links.error ? <InlineError message={links.error.message} /> : null}
        {(links.data ?? []).filter((link) => link.git_repo_id).map((link) => (
          <ContextCard key={link.git_repo_id as string} link={link} />
        ))}
        {(links.data ?? []).filter((link) => !link.git_repo_id).map((link) => (
          <p className="muted small" key={link.path}>
            {link.path} is not Git-indexed — context inventory requires a Git activity scan first.
          </p>
        ))}
      </Section>
    </div>
  );
}

function ContextCard({ link }: { link: ProjectGitLink }) {
  const toast = useToast();
  const inventory = useApi<Record<string, unknown>>(`/api/git-activity/context/${link.git_repo_id}`);
  const [kind, setKind] = useState<"description" | "agents">("agents");
  const [proposal, setProposal] = useState<{ existing?: string; proposal?: string; path?: string } | null>(null);
  const [edited, setEdited] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);

  async function propose() {
    setBusy(true);
    try {
      const result = await api.post<Record<string, unknown>>(`/api/git-activity/context/${link.git_repo_id}/propose`, { kind });
      setProposal({
        existing: String(result.existing ?? ""),
        proposal: String(result.proposal ?? ""),
        path: String(result.path ?? ""),
      });
      setEdited(String(result.proposal ?? ""));
      setConfirmed(false);
    } catch (caught) {
      toast.push("error", "Could not propose context update", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!confirmed || !edited.trim()) return;
    setBusy(true);
    try {
      await api.post(`/api/git-activity/context/${link.git_repo_id}/apply`, {
        kind, content: edited, confirm: true,
      });
      toast.push("success", "Context updated", "Historical content was relocated, not deleted silently — check the diff.");
      setProposal(null);
      setConfirmed(false);
      inventory.reload();
    } catch (caught) {
      toast.push("error", "Could not apply context update", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const record = (inventory.data ?? {}) as Record<string, unknown>;
  return (
    <article className="writer-decision-card">
      <div className="writer-decision-head">
        <strong><PathText>{link.path}</PathText></strong>
        <Tag tone={link.context_status === "ready" ? "accent" : link.context_status === "missing" ? "danger" : "warn"}>
          {link.context_status}
        </Tag>
        {link.has_agents ? <Tag>AGENTS.md</Tag> : <Tag tone="danger">no AGENTS.md</Tag>}
        {link.has_description ? <Tag>DESCRIPTION.md</Tag> : <Tag tone="danger">no DESCRIPTION.md</Tag>}
      </div>
      {inventory.loading ? <LoadingBlock label="Loading context inventory" compact /> : null}
      {inventory.error ? <InlineError message={inventory.error.message} /> : null}
      <div className="inline-form">
        <label className="muted small">
          Document{" "}
          <select value={kind} onChange={(event) => setKind(event.target.value as "description" | "agents")} aria-label="Context document">
            <option value="agents">AGENTS.md</option>
            <option value="description">DESCRIPTION.md</option>
          </select>
        </label>
        <button className="button button-secondary button-small" disabled={busy} onClick={() => void propose()}>
          {busy ? "Working…" : "Review agent instructions / propose update"}
        </button>
      </div>
      {Array.isArray(record.nested_agents) && record.nested_agents.length ? (
        <p className="warn-text small">{record.nested_agents.length} nested AGENTS.md files — review scope before consolidating.</p>
      ) : null}
      {proposal ? (
        <div className="form-stack">
          <p className="muted small">Proposed for <code className="mono">{proposal.path}</code>. Edit freely; applying writes the file and requires confirmation.</p>
          <label className="field">
            <span>Existing (read-only)</span>
            <textarea rows={6} value={proposal.existing ?? ""} readOnly aria-label="Existing context document" />
          </label>
          <label className="field">
            <span>Proposed update (editable)</span>
            <textarea rows={10} value={edited} onChange={(event) => setEdited(event.target.value)} aria-label="Proposed context update" />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
            I confirm writing this file in the repository (outside Mission Control)
          </label>
          <div className="button-row">
            <button className="button button-primary button-small" disabled={!confirmed || !edited.trim() || busy} onClick={() => void apply()}>
              Apply with confirmation
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}
