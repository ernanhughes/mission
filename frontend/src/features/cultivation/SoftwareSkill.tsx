import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, apiPath, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import { Modal } from "../../components/Modal";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  Section,
  Tag,
} from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import type {
  CultivationGoal,
  CultivationRepoState,
  CultivationSkill,
  CultivationSource,
} from "../../types/api";
import { currentLabel } from "./progress";

const QUALIFICATIONS = ["discovered", "eligible", "pending", "qualified", "excluded", "archived", "unavailable"];
const CLASSIFICATIONS = ["application", "library", "infrastructure", "research", "website", "book", "experiment", "other", "unclassified"];
const LIFECYCLES = ["idea", "planned", "in_development", "functional", "testing", "released", "maintained", "archived"];

function commitTime(ts: number | null): string {
  if (!ts) return "Unknown";
  return new Date(ts * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function GoalBarMini(props: { current: number | null; target: number; percent: number | null; achieved: boolean; unit: string; label: string }) {
  const clamped = props.percent == null ? 0 : Math.min(100, Math.max(0, props.percent));
  const state = props.current == null ? "unknown" : props.current <= 0 ? "empty" : props.achieved ? (props.current > props.target ? "over" : "achieved") : "active";
  return (
    <span
      className="hud-bar hud-bar-block"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={props.label}
      data-state={state}
    >
      <span style={{ width: `${clamped}%` }} />
    </span>
  );
}

export function SkillDetail(props: {
  skillId: string;
  onSelectGoal: (id: string) => void;
  onChanged: () => void;
  onClose: () => void;
}) {
  const skill = useApi<CultivationSkill>(`/api/cultivation/skills/${props.skillId}`);
  const goals = useApi<CultivationGoal[]>(apiPath("/api/cultivation/goals", { skill_id: props.skillId }));
  const sources = useApi<CultivationSource[]>("/api/cultivation/sources");
  const source = useMemo(
    () => (sources.data ?? []).find((row) => row.skill_id === props.skillId && row.kind === "activity_projects") ?? null,
    [sources.data, props.skillId],
  );
  const blogSource = useMemo(
    () => (sources.data ?? []).find((row) => row.skill_id === props.skillId && row.kind === "hugo_blog") ?? null,
    [sources.data, props.skillId],
  );

  return (
    <>
      {skill.loading && !skill.data ? <LoadingBlock label="Loading skill" /> : null}
      {skill.error ? <ErrorState message={skill.error.message} onRetry={skill.reload} /> : null}
      {skill.data ? (
        <Section
          key={skill.data.id}
          title={skill.data.name}
          description={skill.data.description || "A configurable domain of goals."}
          actions={
            <>
              <span className="toolbar-count">{skill.data.goals_achieved}/{skill.data.goals_total} goals · {skill.data.item_completions} completions</span>
              <button className="button button-ghost button-small" onClick={props.onClose}>
                Close
              </button>
            </>
          }
        >
          {(goals.data ?? []).map((goal) => (
            <div key={goal.id} className="goal-card">
              <div className="activity-head">
                <button className="link-button" onClick={() => props.onSelectGoal(goal.id)}>
                  <strong>{goal.name}</strong>
                </button>
                {goal.progress.achieved ? <Tag tone="accent">Achieved</Tag> : null}
              </div>
              <div className="muted">{currentLabel(goal.progress)}</div>
              <GoalBarMini
                current={goal.progress.current}
                target={goal.progress.target}
                percent={goal.progress.percent}
                achieved={goal.progress.achieved}
                unit={goal.progress.unit}
                label={currentLabel(goal.progress)}
              />
            </div>
          ))}
        </Section>
      ) : null}
      {source ? (
        <RepoInventory key={source.id} source={source} onChanged={() => { sources.reload(); props.onChanged(); }} />
      ) : null}
      {blogSource ? (
        <BlogInventory key={blogSource.id} source={blogSource} goals={goals.data ?? []} onChanged={() => { sources.reload(); props.onChanged(); }} />
      ) : null}
      <ApplicationsPanel onChanged={props.onChanged} />
    </>
  );
}

// ---------------------------------------------------------- repo inventory
function RepoInventory(props: { source: CultivationSource; onChanged: () => void }) {
  const toast = useToast();
  const [qualification, setQualification] = useState("");
  const [classification, setClassification] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkOpen, setBulkOpen] = useState(false);
  const [scopeText, setScopeText] = useState<string | null>(null);
  const limit = 50;

  const query = useMemo(
    () =>
      apiPath("/api/cultivation/repo-states", {
        qualification: qualification || undefined,
        classification: classification || undefined,
        lifecycle: lifecycle || undefined,
        search: appliedSearch || undefined,
        limit,
        offset: page * limit,
      }),
    [qualification, classification, lifecycle, appliedSearch, page],
  );
  const repos = useApi<{ items: CultivationRepoState[]; total: number }>(query);

  function resetPage() {
    setPage(0);
  }

  async function sync() {
    try {
      const result = await api.post<{ status: string; observed: Record<string, unknown> }>(
        `/api/cultivation/sources/${props.source.id}/sync`,
        {},
      );
      toast.push(result.status === "ok" ? "success" : "info", "Source synced");
      repos.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Sync failed", errorMessage(caught));
    }
  }

  const observed = (props.source.observed ?? {}) as Record<string, unknown>;
  const byQual = (observed.by_qualification ?? {}) as Record<string, number>;
  const configuredRoots = ((props.source.config ?? {}) as Record<string, unknown>).included_roots as string[] | undefined;

  async function saveScope() {
    const roots = (scopeText ?? "")
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    try {
      await api.patch(`/api/cultivation/sources/${props.source.id}`, {
        config: { ...(props.source.config ?? {}), included_roots: roots },
      });
      setScopeText(null);
      toast.push("success", roots.length ? "Scope updated" : "Scope reset to all software roots");
      repos.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Scope update failed", errorMessage(caught));
    }
  }

  return (
    <Section
      title="Repository inventory"
      description="Discovered repositories and their qualification state. Nothing counts until you confirm it."
      actions={
        <button className="button button-secondary button-small" onClick={() => void sync()}>
          Sync from Activity index
        </button>
      }
    >
      <p className="muted">
        {Number(observed.repos_total ?? 0)} discovered
        {Object.entries(byQual).map(([key, value]) => ` · ${key}: ${value}`).join("")}
        {props.source.last_sync_at ? ` · Last sync: ${formatDateTime(props.source.last_sync_at)}` : " · Never synced"}
        {props.source.last_status === "stale" ? " · Source stale — showing last known" : ""}
      </p>
      <div className="toolbar">
        <span className="muted">
          Scope: {configuredRoots && configuredRoots.length ? configuredRoots.join(", ") : "all software roots (Books excluded)"}
        </span>
        {scopeText == null ? (
          <button
            className="button button-ghost button-small"
            onClick={() => setScopeText((configuredRoots ?? []).join(", "))}
          >
            Edit scope
          </button>
        ) : (
          <>
            <input
              value={scopeText}
              onChange={(event) => setScopeText(event.target.value)}
              placeholder="C:\Projects, … (empty = all software roots)"
              aria-label="Included roots, comma separated"
              style={{ minWidth: "280px" }}
            />
            <button className="button button-primary button-small" onClick={() => void saveScope()}>
              Save scope
            </button>
            <button className="button button-ghost button-small" onClick={() => setScopeText(null)}>
              Cancel
            </button>
          </>
        )}
      </div>
      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Filter by qualification</span>
          <select
            value={qualification}
            onChange={(event) => {
              setQualification(event.target.value);
              resetPage();
            }}
          >
            <option value="">All states</option>
            {QUALIFICATIONS.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by classification</span>
          <select
            value={classification}
            onChange={(event) => {
              setClassification(event.target.value);
              resetPage();
            }}
          >
            <option value="">All kinds</option>
            {CLASSIFICATIONS.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by lifecycle</span>
          <select
            value={lifecycle}
            onChange={(event) => {
              setLifecycle(event.target.value);
              resetPage();
            }}
          >
            <option value="">Any lifecycle</option>
            <option value="unset">Unset</option>
            {LIFECYCLES.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="search-field">
          <span className="sr-only">Search repositories</span>
          <input
            value={search}
            placeholder="Search repos…"
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setAppliedSearch(search.trim());
                resetPage();
              }
            }}
          />
        </label>
        {selected.size > 0 ? (
          <button className="button button-secondary button-small" onClick={() => setBulkOpen(true)}>
            Qualify {selected.size} selected
          </button>
        ) : null}
        <span className="toolbar-count">{repos.data?.total ?? 0} tracked</span>
      </div>

      {repos.loading && !repos.data ? <LoadingBlock label="Loading inventory" compact /> : null}
      {(repos.data?.items ?? []).map((repo) => (
        <RepoRow
          key={repo.repo_id}
          repo={repo}
          selected={selected.has(repo.repo_id)}
          onToggle={() =>
            setSelected((current) => {
              const next = new Set(current);
              if (next.has(repo.repo_id)) next.delete(repo.repo_id);
              else next.add(repo.repo_id);
              return next;
            })
          }
          onChanged={() => {
            repos.reload();
            props.onChanged();
          }}
        />
      ))}
      <div className="toolbar">
        {page > 0 ? (
          <button className="button button-ghost button-small" onClick={() => setPage(page - 1)}>
            Previous
          </button>
        ) : null}
        {(repos.data?.total ?? 0) > (page + 1) * limit ? (
          <button className="button button-secondary button-small" onClick={() => setPage(page + 1)}>
            More
          </button>
        ) : null}
      </div>
      {bulkOpen ? (
        <BulkQualifyModal
          repoIds={Array.from(selected)}
          onClose={() => setBulkOpen(false)}
          onDone={() => {
            setBulkOpen(false);
            setSelected(new Set());
            repos.reload();
            props.onChanged();
          }}
        />
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------- blog inventory
function BlogInventory(props: { source: CultivationSource; goals: CultivationGoal[]; onChanged: () => void }) {
  const toast = useToast();
  const [editingPath, setEditingPath] = useState(false);
  const [path, setPath] = useState(props.source.path);
  const [editingTarget, setEditingTarget] = useState(false);
  const [target, setTarget] = useState("1");
  const weekly = props.goals.find((goal) => goal.id === "weekly_blog") ?? null;
  const lifetime = props.goals.find((goal) => goal.id === "blog_posts") ?? null;
  const observed = (props.source.observed ?? {}) as Record<string, unknown>;
  const recent = (observed.recent_posts ?? []) as Array<Record<string, unknown>>;

  async function sync() {
    try {
      const result = await api.post<{ status: string }>(`/api/cultivation/sources/${props.source.id}/sync`, {});
      toast.push(result.status === "ok" ? "success" : "info", result.status === "ok" ? "Blog source synced" : "Blog source stale — kept last observation");
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Sync failed", errorMessage(caught));
    }
  }

  async function savePath() {
    try {
      await api.patch(`/api/cultivation/sources/${props.source.id}`, { path });
      toast.push("success", "Source directory updated");
      setEditingPath(false);
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Path update failed", errorMessage(caught));
    }
  }

  async function saveTarget() {
    if (!weekly) return;
    try {
      await api.patch(`/api/cultivation/goals/${weekly.id}`, { target_value: Number(target) });
      toast.push("success", "Weekly requirement updated");
      setEditingTarget(false);
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Target update failed", errorMessage(caught));
    }
  }

  return (
    <Section
      title="Publication overview"
      description="Live filesystem counts from programmer.ie. Lifetime achievement is separate from weekly discipline."
      actions={
        <button className="button button-secondary button-small" onClick={() => void sync()}>
          Refresh from source
        </button>
      }
    >
      <p className="muted">
        Published: <strong>{Number(observed.published ?? 0)}</strong> · Drafts: <strong>{Number(observed.drafts ?? 0)}</strong> · Scheduled: {Number(observed.scheduled ?? 0)} · Unknown: {Number(observed.unknown ?? 0)}
        {props.source.last_sync_at ? ` · Last sync: ${formatDateTime(props.source.last_sync_at)}` : " · Never synced"}
        {props.source.last_status === "stale" ? " · Stale — showing last known" : ""}
      </p>
      <p className="muted">
        Technology: {Number(observed.tech_published ?? 0)} · Finance: {Number(observed.finance_published ?? 0)} · Technology / Finance preferred, other topics still count
      </p>
      <p className="muted">
        This week ({String(observed.week_start_date ?? "—")} → {String(observed.week_end_date ?? "—")}, Europe/Dublin): {Number(observed.this_week ?? 0)}/{weekly?.target_value ?? 1} · Last week: {Number(observed.last_week ?? 0)} · Last published: {String(observed.latest_published_at ?? "—").slice(0, 10)}
      </p>
      {lifetime ? <p className="muted">Lifetime: {currentLabel(lifetime.progress)} · {lifetime.description}</p> : null}
      {weekly ? <p className="muted">Weekly: {currentLabel(weekly.progress)} · {weekly.description}</p> : null}
      {props.source.last_error ? <p className="muted">Note: {props.source.last_error}</p> : null}
      <div className="toolbar">
        <span className="muted">Source: <code>{props.source.path}</code></span>
        {editingPath ? (
          <>
            <input value={path} onChange={(event) => setPath(event.target.value)} aria-label="Source directory" style={{ minWidth: "280px" }} />
            <button className="button button-primary button-small" onClick={() => void savePath()}>Save directory</button>
            <button className="button button-ghost button-small" onClick={() => setEditingPath(false)}>Cancel</button>
          </>
        ) : (
          <button className="button button-ghost button-small" onClick={() => { setPath(props.source.path); setEditingPath(true); }}>Edit directory</button>
        )}
      </div>
      <div className="toolbar">
        <span className="muted">Required posts per week: {weekly?.target_value ?? 1} · Week starts Monday (Europe/Dublin) · Tracking from first sync, no retrospective backfill</span>
        {editingTarget ? (
          <>
            <input value={target} onChange={(event) => setTarget(event.target.value)} inputMode="decimal" aria-label="Required posts per week" style={{ width: "80px" }} />
            <button className="button button-primary button-small" onClick={() => void saveTarget()}>Save requirement</button>
            <button className="button button-ghost button-small" onClick={() => setEditingTarget(false)}>Cancel</button>
          </>
        ) : weekly ? (
          <button className="button button-ghost button-small" onClick={() => { setTarget(String(weekly.target_value ?? 1)); setEditingTarget(true); }}>Edit requirement</button>
        ) : null}
      </div>
      {recent.slice(0, 5).map((post) => (
        <p key={String(post.identity ?? post.relpath)} className="row-line">
          <strong>{String(post.title ?? post.identity)}</strong>
          <span className="muted"> · {String(post.date ?? "").slice(0, 10)}{post.topic ? ` · ${String(post.topic)}` : ""}</span>
          <br />
          <code>{String(post.relpath ?? "")}</code>
        </p>
      ))}
    </Section>
  );
}

function RepoRow(props: { repo: CultivationRepoState; selected: boolean; onToggle: () => void; onChanged: () => void }) {
  const { repo } = props;
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [classification, setClassification] = useState(repo.classification);
  const [lifecycle, setLifecycle] = useState(repo.lifecycle_stage ?? "");
  const [qualification, setQualification] = useState(repo.qualification);
  const [rationale, setRationale] = useState("");
  const [goalId, setGoalId] = useState("");
  const [goals, setGoals] = useState<Array<{ id: string; name: string }> | null>(null);

  async function openEditor() {
    setEditing(true);
    try {
      const list = await api.get<Array<{ id: string; name: string }>>("/api/cultivation/goals");
      setGoals(list.map((goal) => ({ id: goal.id, name: goal.name })));
    } catch {
      setGoals([]);
    }
  }

  async function save() {
    try {
      await api.patch(`/api/cultivation/repo-states/${repo.repo_id}`, {
        classification,
        lifecycle_stage: lifecycle || null,
        qualification,
        rationale,
        goal_id: qualification === "qualified" ? goalId || null : null,
      });
      toast.push("success", "Repository updated");
      setEditing(false);
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  return (
    <div className="panel review-card">
      <div className="activity-head">
        <input type="checkbox" aria-label={`Select ${repo.name}`} checked={props.selected} onChange={props.onToggle} />
        <strong>{repo.name}</strong>
        <Tag>{repo.qualification}</Tag>
        {repo.classification !== "unclassified" ? <Tag>{repo.classification}</Tag> : null}
        {repo.lifecycle_stage ? <Tag>{repo.lifecycle_stage}</Tag> : null}
        {!repo.accessible ? <Tag>Unavailable</Tag> : null}
        {!repo.indexed ? <Tag>Not indexed</Tag> : null}
      </div>
      <div className="activity-meta">
        <span title={repo.head_sha ?? ""}>{(repo.head_sha ?? "").slice(0, 8) || "no commit"}</span>
        <span>{repo.total_commits} commits</span>
        {repo.last_commit_ts ? <span>last {commitTime(repo.last_commit_ts)}</span> : null}
        {repo.projects.map((project) => (
          <span key={project.id}>{project.name}</span>
        ))}
        <span>{repo.decided_by === "owner" ? "owner decided" : "source observed"}</span>
      </div>
      {repo.rationale ? <p className="muted">{repo.rationale}</p> : null}
      {!editing ? (
        <div className="activity-actions">
          <button className="button button-ghost button-small" onClick={() => void openEditor()}>
            Classify
          </button>
        </div>
      ) : (
        <div className="form-stack">
          <div className="form-grid three">
            <label className="field">
              <span>Kind</span>
              <select value={classification} onChange={(event) => setClassification(event.target.value)}>
                {CLASSIFICATIONS.map((item) => (
                  <option value={item} key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Lifecycle</span>
              <select value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}>
                <option value="">Unset</option>
                {LIFECYCLES.map((item) => (
                  <option value={item} key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Qualification</span>
              <select value={qualification} onChange={(event) => setQualification(event.target.value)}>
                {["discovered", "eligible", "pending", "qualified", "excluded", "archived", "unavailable"].map((item) => (
                  <option value={item} key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {qualification === "qualified" ? (
            <label className="field">
              <span>Count toward goal</span>
              <select value={goalId} onChange={(event) => setGoalId(event.target.value)}>
                <option value="">Select goal…</option>
                {(goals ?? []).map((goal) => (
                  <option value={goal.id} key={goal.id}>
                    {goal.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="field">
            <span>Rationale (required for qualified / excluded)</span>
            <input value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why does this count (or not)?" />
          </label>
          <div className="toolbar">
            <button className="button button-primary button-small" onClick={() => void save()}>
              Save judgement
            </button>
            <button className="button button-ghost button-small" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function BulkQualifyModal(props: { repoIds: string[]; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [qualification, setQualification] = useState("qualified");
  const [rationale, setRationale] = useState("");
  const [goalId, setGoalId] = useState("");
  const [goals, setGoals] = useState<Array<{ id: string; name: string }> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function open() {
    try {
      const list = await api.get<Array<{ id: string; name: string }>>("/api/cultivation/goals");
      setGoals(list.map((goal) => ({ id: goal.id, name: goal.name })));
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  useEffect(() => {
    void open();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const result = await api.post<{ updated: number }>("/api/cultivation/repo-states/bulk", {
        repo_ids: props.repoIds,
        qualification,
        rationale,
        goal_id: qualification === "qualified" ? goalId || null : null,
      });
      toast.push("success", `Updated ${result.updated} repositories`);
      props.onDone();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={`Qualify ${props.repoIds.length} repositories`} onClose={props.onClose}>
      <form className="form-stack" onSubmit={(event) => void submit(event)}>
        <InlineError message={error} />
        <div className="form-grid two">
          <label className="field">
            <span>Qualification</span>
            <select value={qualification} onChange={(event) => setQualification(event.target.value)}>
              {["qualified", "excluded", "eligible", "pending", "archived"].map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          {qualification === "qualified" ? (
            <label className="field">
              <span>Count toward goal</span>
              <select value={goalId} onChange={(event) => setGoalId(event.target.value)}>
                <option value="">Select goal…</option>
                {(goals ?? []).map((goal) => (
                  <option value={goal.id} key={goal.id}>
                    {goal.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <label className="field">
          <span>Rationale (recorded on every repository)</span>
          <textarea rows={3} value={rationale} onChange={(event) => setRationale(event.target.value)} required />
        </label>
        <button className="button button-primary" type="submit" disabled={saving || !rationale.trim()}>
          {saving ? "Applying…" : `Apply to ${props.repoIds.length} repositories`}
        </button>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------ applications
type CultivationApp = {
  id: string;
  name: string;
  description: string;
  lifecycle_stage: string;
  release_evidence: Record<string, unknown>;
  completed_at: string | null;
  notes: string;
  repos: Array<{ repo_id: string; name: string; path: string | null; qualification: string; accessible: boolean }>;
  memberships: Array<{ goal_id: string; goal_name: string | null; stage: string; completed_at: string | null; qualified: boolean; evidence_status: string }>;
};

const APP_LIFECYCLES = ["idea", "planned", "in_development", "functional", "testing", "released", "maintained", "archived"];
const RELEASE_KINDS = ["versioned_release", "deployment", "published", "completion_decision", "owner_confirmed", "project_record"];

function ApplicationsPanel(props: { onChanged: () => void }) {
  const toast = useToast();
  const apps = useApi<CultivationApp[]>("/api/cultivation/applications");
  const [showNew, setShowNew] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  return (
    <Section
      title="Applications"
      description="Usable products. One released application counts once, however many repositories it owns."
      actions={
        <button className="button button-primary button-small" onClick={() => setShowNew(true)}>
          <Plus size={13} /> New application
        </button>
      }
    >
      {apps.loading && !apps.data ? <LoadingBlock label="Loading applications" compact /> : null}
      {(apps.data ?? []).length === 0 ? <p className="muted">No applications registered yet.</p> : null}
      {(apps.data ?? []).map((app) => (
        <div key={app.id} className="panel review-card">
          <div className="activity-head">
            <button className="link-button" onClick={() => setDetailId(app.id)}>
              <strong>{app.name}</strong>
            </button>
            <Tag>{app.lifecycle_stage.replace(/_/g, " ")}</Tag>
            {app.memberships.length > 0 ? <Tag tone="accent">Counted</Tag> : null}
          </div>
          <div className="muted">
            {app.repos.length} {app.repos.length === 1 ? "repository" : "repositories"}
            {app.completed_at ? ` · completed ${formatDateTime(app.completed_at)}` : ""}
          </div>
        </div>
      ))}
      {showNew ? (
        <NewAppModal
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            apps.reload();
            props.onChanged();
          }}
        />
      ) : null}
      {detailId ? (
        <AppDetailModal
          appId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => {
            apps.reload();
            props.onChanged();
          }}
        />
      ) : null}
    </Section>
  );
}

function NewAppModal(props: { onClose: () => void; onCreated: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/cultivation/applications", { name, description });
      toast.push("success", "Application registered");
      props.onCreated();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="New application" onClose={props.onClose}>
      <form className="form-stack" onSubmit={(event) => void create(event)}>
        <InlineError message={error} />
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button className="button button-primary" type="submit" disabled={saving || !name.trim()}>
          {saving ? "Creating…" : "Register application"}
        </button>
      </form>
    </Modal>
  );
}

function AppDetailModal(props: { appId: string; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const app = useApi<CultivationApp>(`/api/cultivation/applications/${props.appId}`);
  const [repoId, setRepoId] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [kind, setKind] = useState("owner_confirmed");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [completedAt, setCompletedAt] = useState("");
  const [goalId, setGoalId] = useState("");
  const [goals, setGoals] = useState<Array<{ id: string; name: string }> | null>(null);

  async function loadGoals() {
    try {
      const list = await api.get<Array<{ id: string; name: string }>>("/api/cultivation/goals");
      setGoals(list.map((goal) => ({ id: goal.id, name: goal.name })));
    } catch {
      setGoals([]);
    }
  }

  useEffect(() => {
    void loadGoals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function link() {
    if (!repoId.trim()) return;
    try {
      await api.post(`/api/cultivation/applications/${props.appId}/repos`, { repo_id: repoId.trim() });
      setRepoId("");
      app.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Link failed", errorMessage(caught));
    }
  }

  async function release() {
    try {
      await api.post(`/api/cultivation/applications/${props.appId}/release`, {
        lifecycle: lifecycle || "released",
        evidence: { kind, reference, note, completed_at: completedAt || undefined },
        completed_at: completedAt || undefined,
        goal_id: goalId || null,
        note,
      });
      toast.push("success", "Release recorded — the application now counts once");
      app.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Release failed", errorMessage(caught));
    }
  }

  async function unrelease() {
    try {
      await api.post(`/api/cultivation/applications/${props.appId}/unrelease`, { note });
      toast.push("success", "Release withdrawn");
      app.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Unrelease failed", errorMessage(caught));
    }
  }

  return (
    <Modal title={app.data?.name ?? "Application"} wide onClose={props.onClose}>
      {app.loading && !app.data ? <LoadingBlock label="Loading application" /> : null}
      {app.error ? <ErrorState message={app.error.message} onRetry={app.reload} /> : null}
      {app.data ? (
        <>
          <dl className="key-values">
            <div>
              <dt>Lifecycle</dt>
              <dd>{app.data.lifecycle_stage.replace(/_/g, " ")}</dd>
            </div>
            {app.data.completed_at ? (
              <div>
                <dt>Completed</dt>
                <dd>{formatDateTime(app.data.completed_at)}</dd>
              </div>
            ) : null}
            {app.data.release_evidence && Object.keys(app.data.release_evidence).length > 0 ? (
              <div>
                <dt>Evidence</dt>
                <dd>
                  {(app.data.release_evidence.kind as string) ?? ""} ·{" "}
                  {((app.data.release_evidence.reference as string) || (app.data.release_evidence.note as string) || "") as string}
                </dd>
              </div>
            ) : null}
          </dl>
          <Section title="Repositories" description="One application may own several repositories.">
            {(app.data.repos ?? []).map((repo) => (
              <p key={repo.repo_id} className="row-line">
                <code>{repo.name}</code>
                <span className="muted"> · {repo.qualification}</span>
              </p>
            ))}
            <div className="inline-form">
              <input
                value={repoId}
                onChange={(event) => setRepoId(event.target.value)}
                placeholder="Activity repository id (see inventory)"
                aria-label="Repository id to link"
              />
              <button className="button button-secondary button-small" onClick={() => void link()}>
                Link repository
              </button>
            </div>
          </Section>
          <Section title="Release" description="A release needs explicit evidence — commits alone never qualify.">
            <div className="form-grid two">
              <label className="field">
                <span>Stage</span>
                <select value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}>
                  <option value="">Choose…</option>
                  <option value="released">Released</option>
                  <option value="maintained">Maintained</option>
                </select>
              </label>
              <label className="field">
                <span>Evidence kind</span>
                <select value={kind} onChange={(event) => setKind(event.target.value)}>
                  {RELEASE_KINDS.map((item) => (
                    <option value={item} key={item}>
                      {item.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="form-grid two">
              <label className="field">
                <span>Reference</span>
                <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Tag, URL, decision…" />
              </label>
              <label className="field">
                <span>Completion date</span>
                <input type="date" value={completedAt} onChange={(event) => setCompletedAt(event.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Count toward goal</span>
              <select value={goalId} onChange={(event) => setGoalId(event.target.value)}>
                <option value="">Select goal…</option>
                {(goals ?? []).map((goal) => (
                  <option value={goal.id} key={goal.id}>
                    {goal.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Note</span>
              <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Release note (optional)" />
            </label>
            <div className="toolbar">
              <button className="button button-primary button-small" onClick={() => void release()} disabled={!lifecycle || !goalId}>
                Record release
              </button>
              <button className="button button-ghost button-small" onClick={() => void unrelease()}>
                Withdraw release
              </button>
            </div>
          </Section>
        </>
      ) : null}
    </Modal>
  );
}
