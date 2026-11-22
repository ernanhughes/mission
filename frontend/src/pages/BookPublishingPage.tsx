import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FileText, Play, Plus, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import { formatDateTime } from "../lib/format";
import type {
  PublishingEvidence,
  PublishingFollowup,
  PublishingSummary,
} from "../types/api";

const resultTones: Record<string, string | undefined> = {
  passed: "accent",
  failed: undefined,
  pending: undefined,
  unavailable: undefined,
  unknown: undefined,
};

function availableActionsFor(evidence: PublishingEvidence): string[] {
  return evidence.available_actions ?? [];
}

function EvidenceCard({ item }: { item: PublishingEvidence }) {
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>{item.evidence_type.replace(/_/g, " ")}</strong>
        <Tag tone={resultTones[item.result]}>{item.result}</Tag>
        <Tag>{item.freshness}</Tag>
      </div>
      <p className="muted small">
        Source: {item.source_system}
        {item.source_reference ? (
          <>
            {" "}· <code>{item.source_reference}</code>
          </>
        ) : null}
        {item.executed_at ? ` · observed ${String(item.executed_at).slice(0, 10)}` : null}
      </p>
      <p>{item.diagnostics || "No diagnostics recorded."}</p>
      {availableActionsFor(item).length > 0 ? (
        <div>
          <span className="eyebrow">Next actions (in the owning system)</span>
          <ul>
            {availableActionsFor(item).map((action, index) => (
              <li key={index} className="muted small">
                <code>{action}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function PromoteBlocker({
  projectId,
  evidenceType,
  sourceReference,
  onDone,
}: {
  projectId: string;
  evidenceType: string;
  sourceReference: string;
  onDone: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<"task" | "decision">("task");
  const [title, setTitle] = useState(`Publishing follow-up: ${evidenceType}`);
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  if (!open) {
    return (
      <button className="button button-ghost button-small" onClick={() => setOpen(true)}>
        <Plus size={13} /> Track as task / decision
      </button>
    );
  }
  async function submit() {
    setBusy(true);
    try {
      await api.post("/api/publication/followups", {
        project_id: projectId,
        evidence_type: evidenceType,
        source_reference: sourceReference,
        title,
        rationale,
        target_type: target,
      });
      toast.push("success", "Follow-up opened");
      setOpen(false);
      onDone();
    } catch (caught) {
      toast.push("error", "Could not open follow-up", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="inline-form">
      <select value={target} onChange={(event) => setTarget(event.target.value as "task" | "decision")} aria-label="Follow-up target">
        <option value="task">Task</option>
        <option value="decision">Decision</option>
      </select>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title" aria-label="Follow-up title" />
      <input value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Rationale (optional)" aria-label="Follow-up rationale" />
      <button className="button button-primary button-small" disabled={busy || !title.trim()} onClick={() => void submit()}>
        {busy ? "…" : "Open follow-up"}
      </button>
      <button className="button button-ghost button-small" disabled={busy} onClick={() => setOpen(false)}>
        Cancel
      </button>
    </div>
  );
}

function FollowupsSection({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const toast = useToast();
  const items = useApi<PublishingFollowup[]>(`/api/publication/followups?project_id=${projectId}`);
  const [busy, setBusy] = useState<string | null>(null);
  async function act(id: string, path: string, verb: string) {
    setBusy(id + path);
    try {
      await api.post(`/api/publication/followups/${id}/${path}`, {});
      toast.push("success", `Follow-up ${verb}`);
      items.reload();
      onChanged();
    } catch (caught) {
      toast.push("error", `Could not ${verb} follow-up`, errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }
  if (items.loading && !items.data) return <LoadingBlock label="Loading follow-ups" compact />;
  if (items.error) return <ErrorState message={items.error.message} onRetry={items.reload} />;
  const rows = items.data ?? [];
  if (rows.length === 0) return <p className="muted">No follow-ups. Promote a blocker below to track it here.</p>;
  return (
    <div>
      {rows.map((item) => (
        <div key={item.id} className="panel review-card">
          <div className="activity-head">
            <strong>{item.title || item.evidence_type}</strong>
            <Tag>{item.status}</Tag>
            <span className="muted">
              {item.target_type} → {item.target_id ?? "—"}
            </span>
          </div>
          <p className="muted small">
            {item.evidence_type} · {item.source_reference || "no source ref"}
          </p>
          {item.status !== "closed" ? (
            <div className="button-row">
              <button className="button button-secondary button-small" disabled={busy !== null} onClick={() => void act(item.id, "recheck", "re-checked")}>
                <RefreshCw size={14} /> Re-check
              </button>
              <button className="button button-ghost button-small" disabled={busy !== null} onClick={() => void act(item.id, "close", "closed")}>
                Close
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function AssessmentSection({ projectId, bookId, onChanged }: { projectId: string; bookId: string | null; onChanged: () => void }) {
  const toast = useToast();
  const assessments = useApi<Array<Record<string, unknown>>>(`/api/publication/assessments?project_id=${projectId}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function assess() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/publication/assessments", {
        project_id: projectId,
        book_id: bookId ?? "",
        technical_scope: "pilot",
      });
      toast.push("success", "Assessment created");
      assessments.reload();
      onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  async function refresh(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/publication/assessments/${id}/refresh`, {});
      toast.push("success", "Assessment refreshed");
      assessments.reload();
      onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  const rows = assessments.data ?? [];
  return (
    <Section
      title="Assessments and approval"
      description="Snapshots are assessed explicitly here; nothing auto-runs. Approval stays a distinct mandatory gate."
      actions={
        <button className="button button-primary button-small" disabled={busy} onClick={() => void assess()}>
          <Play size={14} /> {busy ? "…" : "Assess current snapshot"}
        </button>
      }
    >
      <InlineError message={error} />
      {rows.length === 0 ? <p className="muted">No assessments yet.</p> : null}
      {rows.slice(0, 5).map((row) => (
        <div key={String(row.id)} className="panel review-card">
          <div className="activity-head">
            <strong>{String(row.assessment_status ?? "unknown")}</strong>
            <span className="muted">
              readiness: {String(row.readiness_detail ?? "—").slice(0, 80)} · {formatDateTime(String(row.created_at ?? ""))}
            </span>
          </div>
          <div className="button-row">
            <button className="button button-secondary button-small" disabled={busy} onClick={() => void refresh(String(row.id))}>
              <RefreshCw size={14} /> Refresh
            </button>
            <a className="button button-ghost button-small" href={`/api/publication/assessments/${String(row.id)}/dossier.md`} target="_blank" rel="noreferrer">
              <FileText size={14} /> Dossier
            </a>
          </div>
        </div>
      ))}
    </Section>
  );
}

export function BookPublishingPage() {
  const { projectId = "" } = useParams();
  const toast = useToast();
  const summary = useApi<PublishingSummary>(`/api/publication/publishing?project_id=${projectId}`);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.post(`/api/publication/publishing/refresh?project_id=${projectId}`, {});
      toast.push("success", "Evidence re-read (no validation, build or publish ran)");
      summary.reload();
    } catch (caught) {
      toast.push("error", "Refresh failed", errorMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Publishing"
        title={summary.data?.book_title ?? "Publishing"}
        description="Source-backed account of what is verified, what is unknown, and which existing system can act next."
        actions={
          <>
            <Link className="button button-ghost button-small" to={`/projects/${projectId}`}>
              Back to project
            </Link>
            <button className="button button-secondary button-small" disabled={refreshing} onClick={() => void refresh()}>
              <RefreshCw size={14} /> {refreshing ? "Reading…" : "Refresh evidence"}
            </button>
          </>
        }
      />
      {summary.loading && !summary.data ? <LoadingBlock label="Loading publishing evidence" /> : null}
      {summary.error ? <ErrorState message={summary.error.message} onRetry={summary.reload} /> : null}
      {summary.data ? (
        <>
          <div className="stat-strip">
            <Stat label="Lifecycle" value={summary.data.lifecycle ?? "unknown"} detail={summary.data.lifecycle_note} />
            <Stat label="Publication gate" value={summary.data.publication_gate} />
            <Stat label="Chapters" value={summary.data.chapter_count ?? "—"} />
            <Stat
              label="Fingerprint"
              value={summary.data.fingerprint_match == null ? "unknown" : summary.data.fingerprint_match ? "match" : "mismatch"}
            />
          </div>
          <Section title="Required gates" description="Explicit policy gates joined to observed evidence. No invented readiness.">
            {(summary.data.gates ?? []).map((gate) => (
              <div key={gate.gate_id} className="panel review-card">
                <div className="activity-head">
                  <strong>{gate.label}</strong>
                  <code>{gate.gate_id}</code>
                  <Tag tone={gate.status === "passed" ? "accent" : undefined}>{gate.status}</Tag>
                  {gate.stale ? <Tag>Stale</Tag> : null}
                  <span className="muted">{gate.gate_group}</span>
                </div>
                {gate.evidence.length === 0 ? (
                  <p className="muted small">No evidence mapped yet.</p>
                ) : (
                  gate.evidence.map((entry, index) => (
                    <p key={`${entry.evidence_type}-${index}`} className="row-line">
                      <code>{entry.evidence_type}</code> · {entry.result} · {entry.freshness}
                      <span className="muted"> · {entry.source_system}</span>
                    </p>
                  ))
                )}
              </div>
            ))}
          </Section>
          <Section title="Evidence" description="Every item traces to its source system. Unknown is not failure.">
            {(summary.data.evidence ?? []).map((item, index) => (
              <EvidenceCard key={`${item.evidence_type}-${index}`} item={item} />
            ))}
          </Section>
          <Section title="Blockers and next actions" description="Failed, stale and missing evidence plus the owning system for each.">
            {(summary.data.blockers.failed ?? []).length === 0 &&
            (summary.data.blockers.stale ?? []).length === 0 &&
            (summary.data.blockers.missing ?? []).length === 0 ? (
              <p className="muted">No blockers. Every gate is either passing or explicitly unknown.</p>
            ) : (
              <>
                {(summary.data.blockers.failed ?? []).map((name) => (
                  <BlockerRow key={`failed:${name}`} projectId={projectId} kind="failed" name={name} onChanged={summary.reload} />
                ))}
                {(summary.data.blockers.stale ?? []).map((name) => (
                  <BlockerRow key={`stale:${name}`} projectId={projectId} kind="stale" name={name} onChanged={summary.reload} />
                ))}
                {(summary.data.blockers.missing ?? []).map((name) => (
                  <BlockerRow key={`missing:${name}`} projectId={projectId} kind="missing" name={name} onChanged={summary.reload} />
                ))}
              </>
            )}
          </Section>
          <Section title="Follow-ups" description="Promoted blockers with provenance and re-checks.">
            <FollowupsSection projectId={projectId} onChanged={summary.reload} />
          </Section>
          <AssessmentSection projectId={projectId} bookId={summary.data.book_id} onChanged={summary.reload} />
        </>
      ) : null}
    </div>
  );
}

function BlockerRow({ projectId, kind, name, onChanged }: { projectId: string; kind: string; name: string; onChanged: () => void }) {
  const [showForm, setShowForm] = useState(false);
  const toast = useToast();
  const [target, setTarget] = useState<"task" | "decision">("task");
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    try {
      await api.post("/api/publication/followups", {
        project_id: projectId,
        evidence_type: name,
        title: `Publishing follow-up: ${name}`,
        rationale: `Promoted from the publishing workbench (${kind}).`,
        target_type: target,
      });
      toast.push("success", "Follow-up opened");
      setShowForm(false);
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not open follow-up", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  if (!showForm) {
    return (
      <p className="row-line">
        <Tag>{kind}</Tag> <code>{name}</code>{" "}
        <button className="button button-ghost button-small" onClick={() => setShowForm(true)}>
          <Plus size={13} /> Track
        </button>
      </p>
    );
  }
  return (
    <div className="inline-form">
      <span className="tag">{kind}</span> <code>{name}</code>
      <select value={target} onChange={(event) => setTarget(event.target.value as "task" | "decision")} aria-label="Follow-up target">
        <option value="task">Task</option>
        <option value="decision">Decision</option>
      </select>
      <button className="button button-primary button-small" disabled={busy} onClick={() => void submit()}>
        {busy ? "…" : "Open"}
      </button>
      <button className="button button-ghost button-small" disabled={busy} onClick={() => setShowForm(false)}>
        Cancel
      </button>
    </div>
  );
}
