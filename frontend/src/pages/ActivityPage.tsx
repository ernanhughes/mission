import { useMemo, useState, type FormEvent } from "react";
import { Activity, Filter, Plus } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  ProvenanceBadge,
  Section,
} from "../components/ui";
import { activityLabel, formatDateTime, formatDate, timeAgo } from "../lib/format";
import type { ActivityEvent, Project } from "../types/api";

const activityTypes = [
  "user_note",
  "user_decision",
  "workspace_focus",
  "checkpoint",
  "task_created",
  "task_updated",
  "recommendation_reviewed",
  "application_launch",
  "application_stopped",
  "application_launch_failed",
  "application_health",
  "repository_opened",
  "git_observation",
  "adapter_observation",
  "adapter_available",
  "adapter_unavailable",
  "discovery_scan",
  "briefing_generated",
  "system",
];

export function ActivityPage() {
  const projects = useApi<Project[]>("/api/projects");
  const [projectId, setProjectId] = useState("");
  const [type, setType] = useState("");
  const [date, setDate] = useState("");
  const [noteProject, setNoteProject] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteDetail, setNoteDetail] = useState("");
  const [noteEvidence, setNoteEvidence] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const since = date ? new Date(`${date}T00:00:00`).toISOString() : undefined;
  const path = apiPath("/api/activity", {
    project_id: projectId || undefined,
    type: type || undefined,
    since,
    limit: 200,
  });
  const activity = useApi<ActivityEvent[]>(path);
  const grouped = useMemo(() => {
    const groups = new Map<string, ActivityEvent[]>();
    for (const event of activity.data ?? []) {
      const key = new Date(event.occurred_at).toLocaleDateString();
      groups.set(key, [...(groups.get(key) ?? []), event]);
    }
    return Array.from(groups.entries());
  }, [activity.data]);

  async function addNote(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setNoteError(null);
    try {
      await api.post("/api/activity/notes", {
        project_id: noteProject || null,
        title: noteTitle,
        detail: noteDetail,
        evidence_ref: noteEvidence || null,
      });
      toast.push("success", "Note added to activity");
      setNoteTitle("");
      setNoteDetail("");
      setNoteEvidence("");
      activity.reload();
    } catch (caught) {
      setNoteError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="History"
        title="Activity"
        description="A chronological record that keeps user notes, verified observations, external claims and failures distinct."
      />

      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Filter by project</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">All projects</option>
            {(projects.data ?? []).map((project) => (
              <option value={project.id} key={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by type</span>
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All types</option>
            {activityTypes.map((item) => (
              <option value={item} key={item}>
                {activityLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className="date-field">
          <Filter size={14} aria-hidden="true" />
          <span className="sr-only">Since date</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        {projectId || type || date ? (
          <button
            className="button button-ghost button-small"
            onClick={() => {
              setProjectId("");
              setType("");
              setDate("");
            }}
          >
            Clear filters
          </button>
        ) : null}
        <span className="toolbar-count">{activity.data?.length ?? 0} events</span>
      </div>

      <div className="activity-layout">
        <div>
          {activity.loading && !activity.data ? <LoadingBlock label="Loading activity" /> : null}
          {activity.error ? <ErrorState message={activity.error.message} onRetry={activity.reload} /> : null}
          {activity.data && activity.data.length === 0 ? (
            <EmptyState
              title="No activity matches"
              description="Add a note, save a checkpoint or run discovery to create a record."
              icon={<Activity size={20} />}
            />
          ) : null}
          {grouped.map(([day, events]) => (
            <section className="activity-day" key={day}>
              <h2>{day}</h2>
              <ul className="activity-feed">
                {events.map((event) => (
                  <li key={event.id}>
                    <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
                    <div className="activity-entry">
                      <div className="activity-head">
                        <strong>{event.title}</strong>
                        <span className="activity-type">{activityLabel(event.type)}</span>
                      </div>
                      <div className="activity-meta">
                        <span>{formatDateTime(event.occurred_at)}</span>
                        {event.project_name ? <span>{event.project_name}</span> : null}
                        {event.application_name ? <span>{event.application_name}</span> : null}
                        <span>{event.source}</span>
                        <ProvenanceBadge value={event.provenance} />
                      </div>
                      {event.detail ? <p className="activity-detail">{event.detail}</p> : null}
                      {event.evidence_ref ? (
                        <details className="evidence-list">
                          <summary>Evidence</summary>
                          <code>{event.evidence_ref}</code>
                        </details>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <aside className="activity-side">
          <Section title="Add a note" description="Notes are explicitly user-authored.">
            <form className="form-stack" onSubmit={(event) => void addNote(event)}>
              <InlineError message={noteError} />
              <label className="field">
                <span>Project (optional)</span>
                <select value={noteProject} onChange={(event) => setNoteProject(event.target.value)}>
                  <option value="">Workspace-wide</option>
                  {(projects.data ?? []).map((project) => (
                    <option value={project.id} key={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Title</span>
                <input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} required />
              </label>
              <label className="field">
                <span>Detail</span>
                <textarea rows={4} value={noteDetail} onChange={(event) => setNoteDetail(event.target.value)} />
              </label>
              <label className="field">
                <span>Evidence reference (optional)</span>
                <input
                  value={noteEvidence}
                  onChange={(event) => setNoteEvidence(event.target.value)}
                  placeholder="C:\Projects\...\report.json"
                />
              </label>
              <button className="button button-primary" type="submit" disabled={saving || !noteTitle.trim()}>
                <Plus size={14} /> {saving ? "Saving…" : "Add note"}
              </button>
            </form>
          </Section>

          <Section title="Provenance key">
            <dl className="provenance-key">
              <div>
                <dt>
                  <ProvenanceBadge value="verified_observation" />
                </dt>
                <dd>Read from a local system or process in this run.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="external_claim" />
                </dt>
                <dd>A statement made by another application, not independently verified.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="derived_observation" />
                </dt>
                <dd>Deterministically derived from recorded evidence.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="ai_recommendation" />
                </dt>
                <dd>Advisory model output. It never replaces a human decision.</dd>
              </div>
            </dl>
          </Section>
        </aside>
      </div>
    </div>
  );
}
