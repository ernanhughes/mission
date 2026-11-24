import { useState, type FormEvent } from "react";
import { CheckCircle2, Circle, Pencil, Pin, PinOff, RefreshCw, Save, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import { InlineError, ProvenanceBadge, SimpleStatusBadge, Tag } from "../../components/ui";
import { timeAgo, titleCase, truncate } from "../../lib/format";
import type { Adapter, Recommendation, Task } from "../../types/api";

export function CheckpointForm({ projectId, onSaved }: { projectId: string; onSaved: () => void }) {
  const toast = useToast();
  const storageKey = `mc.checkpoint.${projectId}`;
  const [summary, setSummary] = useState(() => {
    try {
      return sessionStorage.getItem(`${storageKey}.summary`) ?? "";
    } catch {
      return "";
    }
  });
  const [lastCompleted, setLastCompleted] = useState("");
  const [nextAction, setNextAction] = useState(() => {
    try {
      return sessionStorage.getItem(`${storageKey}.next`) ?? "";
    } catch {
      return "";
    }
  });
  const [blockers, setBlockers] = useState("");
  const [milestone, setMilestone] = useState("");
  const [evidence, setEvidence] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function persist(nextSummary: string, nextNext: string) {
    try {
      sessionStorage.setItem(`${storageKey}.summary`, nextSummary);
      sessionStorage.setItem(`${storageKey}.next`, nextNext);
    } catch {
      /* storage unavailable */
    }
  }

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
      persist("", "");
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
          onChange={(event) => {
            setSummary(event.target.value);
            persist(event.target.value, nextAction);
          }}
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
          <input
            value={nextAction}
            onChange={(event) => {
              setNextAction(event.target.value);
              persist(summary, event.target.value);
            }}
          />
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

export function TaskRow({ task, onChanged }: { task: Task; onChanged: () => void }) {
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

export function RecommendationRow({
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

export function AdapterCard({
  adapter,
  projectId,
  onChanged,
}: {
  adapter: Adapter;
  projectId: string;
  onChanged: () => void;
}) {
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

export function ProjectTabBadges({ children }: { children?: React.ReactNode }) {
  return <span className="project-tab-badge">{children}</span>;
}

export function PinButton({
  pinned,
  busy,
  onToggle,
}: {
  pinned: boolean;
  busy: boolean;
  onToggle: () => void;
}) {
  return (
    <button className="button button-secondary" onClick={onToggle} disabled={busy}>
      {pinned ? <PinOff size={15} /> : <Pin size={15} />}
      {pinned ? "Unpin" : "Pin"}
    </button>
  );
}

export function ProjectLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link className="text-link" to={to}>
      {children}
    </Link>
  );
}

export function tagToneForFreshness(state: string): "accent" | "danger" | "default" {
  if (state === "current") return "accent";
  if (state === "stale" || state === "outdated") return "danger";
  return "default";
}

export function TagWrap({ children }: { children: React.ReactNode }) {
  return <Tag>{children}</Tag>;
}
