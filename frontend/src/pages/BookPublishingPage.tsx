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

type PublishingChapterIssue = {
  id: string; gate_id: string; issue_type: string; severity: string;
  status: string; author_review_status: string;
};
type PublishingChapter = {
  chapter_id: string; title: string; filename: string; bytes: number;
  fingerprint: string; state: string;
  issues: PublishingChapterIssue[];
  followups: Array<{ id: string; title: string; status: string; evidence_type: string }>;
};
type ChaptersData = {
  project_id: string; chapters: PublishingChapter[]; count: number;
  chapter_named_in_assessment: string[];
  assessment: { id: string; status: string; freshness: string; fingerprint_match: boolean | null; created_at: string } | null;
  approvals: Array<{ id: string; decision: string; rationale: string; manuscript_fingerprint: string; freshness: string; created_at: string }>;
  manuscript_fingerprint: string | null;
  observed_at: string;
  error?: string;
};
type RetainedCandidate = {
  id: string; chapter: string; label: string; kind: string;
  candidate_path: string; available: boolean; bytes: number; fingerprint: string;
  verification: Record<string, unknown>; note: string;
};
type CandidatesData = { project_id: string; candidates: RetainedCandidate[]; count: number; observed_at: string };

const PUBLISH_TABS = ["Overview", "Chapters", "Evidence", "Editorial", "Candidates", "Review", "Publish"] as const;
type PublishTab = (typeof PUBLISH_TABS)[number];

const ISSUE_DECISIONS = ["ACCEPT FINDING", "REJECT FINDING", "DEFER", "ACCEPT LIMITATION", "REQUEST RECHECK"];
const APPROVAL_DECISIONS = ["APPROVE_RELEASE_CANDIDATE", "REVOKE_APPROVAL"];

function nextRecommendedAction(summary: PublishingSummary): string {
  const failed = summary.blockers.failed ?? [];
  const stale = summary.blockers.stale ?? [];
  const missing = summary.blockers.missing ?? [];
  if (failed.length > 0) return `Resolve failed evidence: ${failed[0]}. Waive only an explicitly waivable issue with recorded rationale.`;
  if (stale.length > 0) return `Re-check stale evidence: ${stale[0]}. Stored reports no longer match current sources.`;
  if (missing.length > 0) return `Supply missing evidence: ${missing[0]}. Unknown is not failure, but gates cannot pass without it.`;
  return "Review open follow-ups and confirm the next editorial scope with the author.";
}

function ImproveChapterForm({ projectId, chapterId, onDone }: { projectId: string; chapterId: string; onDone: (recordId?: string) => void }) {
  const toast = useToast();
  const [strategy, setStrategy] = useState<"whole-chapter" | "targeted">("targeted");
  const [mode, setMode] = useState<"inspect" | "generate" | "generate+verify">("inspect");
  const [budget, setBudget] = useState("0");
  const [actor, setActor] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const valid = actor.trim().length >= 2 && note.trim().length >= 8 && !Number.isNaN(Number(budget)) && Number(budget) >= 0;
  async function submit() {
    setBusy(true);
    setResult(null);
    setCandidateId(null);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 200000);
    try {
      const response = await api.post<{ status: string; packet?: Record<string, unknown>; improvement?: Record<string, any>; worker_envelope?: string }>(
        "/api/publication/improvements",
        { project_id: projectId, chapter_id: chapterId, strategy, mode, max_budget_usd: Number(budget), actor: actor.trim(), authorization_note: note.trim() },
        controller.signal,
      );
      if (mode === "inspect") {
        setResult(`Prepared (no dispatch). Packet validated for ${chapterId}; envelope and Worker run not started.`);
      } else {
        const record = response.improvement as Record<string, any> | undefined;
        setResult(`Dispatched: ${record?.status ?? response.status}. Envelope ${response.worker_envelope ?? "—"}. Cost $${Number(record?.cost_usd ?? 0).toFixed(4)}.`);
        if (record?.id) setCandidateId(String(record.id));
      }
      onDone((response.improvement as Record<string, any> | undefined)?.id as string | undefined);
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") setResult("Request timed out waiting for the Worker; the run may still be executing. Check the Candidates tab before retrying.");
      else setResult(errorMessage(caught));
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
    }
  }
  return (
    <div className="inline-form">
      <label className="field"><span>Editorial strategy</span>
        <select value={strategy} onChange={(event) => setStrategy(event.target.value as "whole-chapter" | "targeted")} aria-label="Editorial strategy">
          <option value="targeted">Targeted improvement — fix named findings, preserve structure</option>
          <option value="whole-chapter">Whole-chapter reconstruction — provisional, not proven superior</option>
        </select>
      </label>
      <label className="field"><span>Execution mode</span>
        <select value={mode} onChange={(event) => setMode(event.target.value as "inspect" | "generate" | "generate+verify")} aria-label="Execution mode">
          <option value="inspect">Inspect and prepare only (no dispatch)</option>
          <option value="generate">Generate candidate (free local-only Worker route)</option>
          <option value="generate+verify">Generate + deterministic checks (semantic verification stays pending)</option>
        </select>
      </label>
      <label className="field"><span>Reported-cost ceiling (USD)</span>
        <input type="number" min={0} max={10} step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} aria-label="Maximum inference budget" />
      </label>
      <p className="muted small">Only free local-only routes can be dispatched, so this ceiling is a guard against a misreported cost — not a provider-side spend cap. A run whose Worker-reported cost exceeds it is recorded as failed.</p>
      <label className="field"><span>Human actor</span>
        <input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="Your name" aria-label="Improvement actor" />
      </label>
      <label className="field"><span>Authorization note (min 8 chars)</span>
        <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why is this improvement authorized" aria-label="Improvement authorization note" />
      </label>
      <button className="button button-primary button-small" disabled={busy || !valid} onClick={() => void submit()}>
        {busy ? "…" : mode === "inspect" ? "Prepare request" : "Authorize and dispatch"}
      </button>
      {!valid ? <p className="muted small">A human actor and an authorization note of at least 8 characters are required. System and model identities are refused.</p> : null}
      {result ? <p className="muted" role="status">{result}</p> : null}
      {candidateId ? <p><button className="button button-ghost button-small" onClick={() => onDone(candidateId)}>Open candidate</button></p> : null}
    </div>
  );
}

function ImproveChapterRow({ projectId, row, onOpenCandidate }: { projectId: string; row: { chapter_id: string }; onOpenCandidate?: (recordId: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="button-row">
        <button className="button button-ghost button-small" onClick={() => setOpen((value) => !value)}>
          {open ? "Close improvement request" : "Improve chapter"}
        </button>
      </div>
      {open ? <ImproveChapterForm projectId={projectId} chapterId={row.chapter_id} onDone={(recordId) => { if (recordId && onOpenCandidate) { onOpenCandidate(recordId); setOpen(false); } }} /> : null}
    </div>
  );
}

function ChaptersTab({ projectId, onOpenCandidate }: { projectId: string; onOpenCandidate?: (recordId: string) => void }) {
  const chapters = useApi<ChaptersData>(`/api/publication/publishing/chapters?project_id=${projectId}`);
  const [filter, setFilter] = useState("all");
  if (chapters.loading && !chapters.data) return <LoadingBlock label="Loading chapter inventory" compact />;
  if (chapters.error) return <ErrorState message={chapters.error.message} onRetry={chapters.reload} />;
  const rows = chapters.data?.chapters ?? [];
  if (chapters.data?.error) return <EmptyState title="Chapter inventory unavailable" description={chapters.data.error} />;
  const counts = rows.reduce<Record<string, number>>((acc, row) => ({ ...acc, [row.state]: (acc[row.state] ?? 0) + 1 }), {});
  const visible = filter === "all" ? rows : rows.filter((row) => row.state === filter);
  return (
    <Section
      title="Chapter inventory"
      description="Every chapter with its publication state. Unassessed and unknown chapters carry no verdict — zero findings are never reported as success."
      actions={
        <select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter chapters by state">
          <option value="all">All states ({rows.length})</option>
          {Object.keys(counts).sort().map((state) => (
            <option key={state} value={state}>{state} ({counts[state]})</option>
          ))}
        </select>
      }
    >
      {chapters.data?.assessment ? (
        <p className="muted small">
          Latest assessment {chapters.data.assessment.id} · {chapters.data.assessment.status} · fingerprint{" "}
          {chapters.data.assessment.fingerprint_match == null ? "unknown" : chapters.data.assessment.fingerprint_match ? "match" : "mismatch"}
        </p>
      ) : (
        <p className="muted small">No assessment recorded — every chapter below is unassessed-or-unknown, not failing.</p>
      )}
      {visible.length === 0 ? <EmptyState title="No chapters in this state" description="Adjust the filter or refresh the book inventory." /> : null}
      {visible.map((row) => (
        <div key={row.chapter_id} className="panel review-card">
          <div className="activity-head">
            <strong>{row.chapter_id} · {row.title}</strong>
            <Tag tone={row.state === "assessed" ? "accent" : undefined}>{row.state}</Tag>
            <span className="muted small">{row.bytes.toLocaleString()} bytes · fp <code>{row.fingerprint.slice(0, 12) || "—"}</code></span>
          </div>
          <ImproveChapterRow projectId={projectId} row={row} onOpenCandidate={onOpenCandidate} />
          {row.issues.length > 0 || row.followups.length > 0 ? (
            <details>
              <summary>Linked records ({row.issues.length} issues · {row.followups.length} follow-ups)</summary>
              {row.issues.map((issue) => (
                <p key={issue.id} className="row-line"><code>{issue.gate_id}</code> · {issue.issue_type} · {issue.severity} · {issue.status} · author review: {issue.author_review_status}</p>
              ))}
              {row.followups.map((followup) => (
                <p key={followup.id} className="row-line"><code>{followup.evidence_type}</code> · {followup.title} · {followup.status}</p>
              ))}
            </details>
          ) : (
            <p className="muted small">No linked issues or follow-ups. {row.state === "unassessed" ? "Not yet covered by any assessment." : row.state === "stale" ? "Sources moved since the last assessment." : "Named in no assessment record."}</p>
          )}
        </div>
      ))}
    </Section>
  );
}

type DispatchedImprovement = {
  id: string; chapter_id: string; strategy: string; mode: string;
  status: string; model_route?: string | null; cost_usd?: number;
  actor?: string; created_at?: string; envelope_id?: string;
  chapter_fingerprint?: string; source_current?: boolean;
  validation?: { passed?: boolean; warnings?: string[]; warning_count?: number };
  verification?: { status?: string };
  eligible?: boolean;
  candidate_fingerprint?: string;
  truncation?: {
    requested_output_tokens?: number | null;
    observed_output_tokens?: number | null;
    suspected?: boolean;
  };
};

function CandidatesTab({ projectId, focusId }: { projectId: string; focusId?: string | null }) {
  const candidates = useApi<CandidatesData>(`/api/publication/publishing/candidates?project_id=${projectId}`);
  const dispatched = useApi<{ improvements: DispatchedImprovement[]; count: number; worker_reachable: boolean; rejected_records?: number }>(`/api/publication/improvements`);
  const [selected, setSelected] = useState<{ kind: "retained" | "dispatched"; id: string } | null>(
    focusId ? { kind: "dispatched", id: focusId } : null,
  );
  const retainedRow = candidates.data?.candidates.find((row) => selected?.kind === "retained" && row.id === selected.id);
  const dispatchedRow = dispatched.data?.improvements.find((row) => selected?.kind === "dispatched" && row.id === selected.id);
  const bodyPath = selected == null
    ? null
    : selected.kind === "retained"
      ? `/api/publication/publishing/candidates/${encodeURIComponent(selected.id)}/body`
      : `/api/publication/improvements/${encodeURIComponent(selected.id)}/body`;
  const body = useApi<{ available: boolean; markdown?: string; reason?: string }>(bodyPath);
  const [view, setView] = useState<"candidate" | "original" | "side">("candidate");
  const chapterId = retainedRow?.chapter ?? dispatchedRow?.chapter_id;
  const original = useApi<{ markdown?: string }>(
    chapterId ? `/api/living-book/projects/${projectId}/chapters/${encodeURIComponent(chapterId)}` : null,
  );
  if ((candidates.loading && !candidates.data) || (dispatched.loading && !dispatched.data)) return <LoadingBlock label="Loading candidates" compact />;
  if (candidates.error) return <ErrorState message={candidates.error.message} onRetry={() => { candidates.reload(); dispatched.reload(); }} />;
  const rows = candidates.data?.candidates.filter((row) => row.available) ?? [];
  const runs = (dispatched.data?.improvements ?? []).filter((row) => row.status === "reported_complete");
  const readingTitle = retainedRow != null ? retainedRow.label : dispatchedRow != null ? `${dispatchedRow.chapter_id} · generated ${String(dispatchedRow.created_at ?? "").slice(0, 10)}` : "";
  return (
    <>
    <Section
      title="Requested via Mission"
      description="Candidates generated through governed Publication improvement runs. Semantic verification stays pending where recorded; unreviewed output is not an accepted revision."
    >
      {dispatched.error ? <InlineError message={dispatched.error.message} /> : null}
      {runs.length === 0 ? <EmptyState title="No generated candidates yet" description="Use Improve chapter on the Chapters tab to request a bounded, authorized generation. Nothing runs without an explicit human authorization." /> : null}
      {runs.map((row) => (
        <div key={row.id} className="panel review-card">
          <div className="activity-head">
            <strong>{row.chapter_id} · {row.strategy}</strong>
            <Tag tone={row.status === "reported_complete" ? "accent" : undefined}>{row.status}</Tag>
            {row.eligible === false ? <Tag tone="danger">ineligible for acceptance</Tag> : null}
            <span className="muted small">model {row.model_route ?? "unknown"} · cost ${Number(row.cost_usd ?? 0).toFixed(4)} · {String(row.created_at ?? "").slice(0, 10)}</span>
          </div>
          <p className="muted small">Verification: recorded checks {row.validation?.passed ? "passed" : "have failures — see record"}; semantic assessment pending.</p>
          {row.truncation?.suspected ? (
            <p className="muted small">
              <Tag tone="danger">ceiling-bound</Tag>{" "}
              {row.truncation.observed_output_tokens} of {row.truncation.requested_output_tokens} output tokens used —
              the response stopped at the limit, so the chapter is incomplete and must be regenerated with a larger budget.
            </p>
          ) : null}
          {(row.validation?.warning_count ?? 0) > 0 ? (
            <details>
              <summary><Tag tone="danger">Preservation warnings · {row.validation?.warning_count}</Tag> Deterministic evidence that material may have been lost; this is not a semantic verdict.</summary>
              <ul>
                {(row.validation?.warnings ?? []).map((warning, index) => (
                  <li key={index} className="muted small">{warning}</li>
                ))}
              </ul>
            </details>
          ) : (
            <p className="muted small">No deterministic preservation warnings recorded.</p>
          )}
          <p className="muted small">Source fingerprint <code>{String(row.chapter_fingerprint ?? "").slice(0, 12)}</code>{row.source_current === false ? " · source has changed since generation (stale)" : ""} · envelope <code>{String(row.envelope_id ?? "").slice(0, 20)}</code></p>
          <div className="button-row">
            <button className="button button-secondary button-small" onClick={() => { setSelected({ kind: "dispatched", id: row.id }); setView("candidate"); }}>
              Read candidate
            </button>
          </div>
        </div>
      ))}
      {dispatched.data && (dispatched.data.rejected_records ?? 0) > 0 ? (
        <p className="muted small">
          {dispatched.data.rejected_records} file(s) in the candidate store failed the integrity check
          (identity, ownership, or body fingerprint) and are not shown as candidates.
        </p>
      ) : null}
      {dispatched.data && !dispatched.data.worker_reachable ? <p className="muted small">Worker is currently unreachable; stored candidates above remain readable, but live execution status cannot be refreshed.</p> : null}
    </Section>
    <Section
      title="Retained candidates"
      description="Historical experimental records with recorded verification only. Not production candidates and not evidence of publication readiness."
    >
      {rows.length === 0 ? <EmptyState title="No retained candidates" description="No historical candidate records are registered for this book." /> : null}
      {rows.map((row) => (
        <div key={row.id} className="panel review-card">
          <div className="activity-head">
            <strong>{row.label}</strong>
            <Tag>historical</Tag>
            <span className="muted small">{row.chapter} · {(row.bytes / 1024).toFixed(1)} KB · fp <code>{row.fingerprint.slice(0, 12)}</code></span>
          </div>
          <p className="muted small"><code>{row.candidate_path}</code></p>
          <details>
            <summary>Recorded verification</summary>
            <pre className="harness-output">{JSON.stringify(row.verification, null, 2)}</pre>
          </details>
          <p className="muted small">{row.note}</p>
          <div className="button-row">
            <button className="button button-secondary button-small" onClick={() => { setSelected({ kind: "retained", id: row.id }); setView("candidate"); }}>
              Read candidate
            </button>
          </div>
        </div>
      ))}
      {selected != null && (retainedRow != null || dispatchedRow != null) ? (
        <div className="panel review-card">
          <div className="activity-head">
            <strong>Reading: {readingTitle}</strong>
            <button className="button button-ghost button-small" onClick={() => setSelected(null)}>Close</button>
          </div>
          <div className="button-row" role="tablist" aria-label="Reading view">
            {(["candidate", "original", "side"] as const).map((mode) => (
              <button key={mode} role="tab" aria-selected={view === mode} className={`button button-small ${view === mode ? "button-secondary" : "button-ghost"}`} onClick={() => setView(mode)}>
                {mode === "candidate" ? "Candidate" : mode === "original" ? "Original manuscript" : "Side by side"}
              </button>
            ))}
          </div>
          {body.loading ? <LoadingBlock compact /> : null}
          {body.error ? <InlineError message={body.error.message} /> : null}
          {body.data && !body.data.available ? <p className="muted">{body.data.reason ?? "Candidate body unavailable."}</p> : null}
          {body.data?.available && view !== "original" ? (
            <pre className="harness-output" style={{ whiteSpace: "pre-wrap" }}>{body.data.markdown}</pre>
          ) : null}
          {(view === "original" || view === "side") && chapterId != null ? (
            <OriginalChapterPane projectId={projectId} chapterId={chapterId} markdown={original.data?.markdown} loading={original.loading} error={original.error?.message ?? null} />
          ) : null}
          {body.data?.available && view === "side" ? (
            <pre className="harness-output" style={{ whiteSpace: "pre-wrap" }}>{body.data.markdown}</pre>
          ) : null}
          <p className="muted small">Textual differences are not semantic differences. Consult the recorded verification and defect attribution above; unrecorded changes are unverified.</p>
        </div>
      ) : null}
    </Section>
    </>
  );
}

function OriginalChapterPane({ projectId, chapterId, markdown, loading, error }: { projectId: string; chapterId: string; markdown?: string; loading: boolean; error: string | null }) {
  void projectId;
  if (loading) return <LoadingBlock label={`Loading original ${chapterId}`} compact />;
  if (error) return <InlineError message={error} />;
  if (!markdown) return <p className="muted">Original manuscript text unavailable for {chapterId}.</p>;
  return <pre className="harness-output" style={{ whiteSpace: "pre-wrap" }}>{markdown}</pre>;
}

function IssuesReviewList({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const toast = useToast();
  const assessments = useApi<Array<{ id: string; issues: Array<{ id: string; gate_id: string; issue_type: string; severity: string; status: string; waiver_eligibility: string; author_review_status: string; rationale: string }> }>>(
    `/api/publication/assessments?project_id=${projectId}`,
  );
  const [assessmentId, setAssessmentId] = useState("");
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const rows = assessments.data ?? [];
  const active = rows.find((row) => row.id === (assessmentId || rows[0]?.id)) ?? rows[0];
  async function review(issueId: string) {
    const decision = decisions[issueId] ?? "ACCEPT FINDING";
    setBusy(true);
    try {
      await api.post(`/api/publication/issues/${issueId}/review`, { decision, rationale, reviewer });
      toast.push("success", "Issue review recorded");
      assessments.reload();
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not record issue review", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  if (assessments.loading && !assessments.data) return <LoadingBlock label="Loading issues" compact />;
  if (assessments.error) return <ErrorState message={assessments.error.message} onRetry={assessments.reload} />;
  if (rows.length === 0) return <p className="muted">No assessments, so no issues to review.</p>;
  const issues = active?.issues ?? [];
  return (
    <div>
      <label className="field"><span>Assessment</span>
        <select value={active?.id ?? ""} onChange={(event) => setAssessmentId(event.target.value)}>
          {rows.map((row) => <option key={row.id} value={row.id}>{row.id}</option>)}
        </select>
      </label>
      <label className="field"><span>Reviewer (human identity)</span>
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Your name" aria-label="Issue review author" />
      </label>
      <label className="field"><span>Rationale (recorded with the review)</span>
        <input value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this decision" aria-label="Issue review rationale" />
      </label>
      {issues.length === 0 ? <p className="muted">No issues on this assessment.</p> : null}
      {issues.map((issue) => (
        <div key={issue.id} className="panel review-card">
          <div className="activity-head">
            <strong><code>{issue.gate_id}</code> · {issue.issue_type}</strong>
            <Tag>{issue.severity}</Tag>
            <span className="muted small">{issue.status} · author review: {issue.author_review_status}{issue.waiver_eligibility === "waivable" ? " · waivable" : " · non-waivable"}</span>
          </div>
          <div className="inline-form">
            <select value={decisions[issue.id] ?? "ACCEPT FINDING"} onChange={(event) => setDecisions({ ...decisions, [issue.id]: event.target.value })} aria-label={`Decision for ${issue.id}`}>
              {ISSUE_DECISIONS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
            <button className="button button-secondary button-small" disabled={busy || !reviewer.trim()} onClick={() => void review(issue.id)}>
              {busy ? "…" : "Record review"}
            </button>
          </div>
          {!reviewer.trim() ? <p className="muted small">Enter your name to enable review — system and model identities are refused.</p> : null}
        </div>
      ))}
    </div>
  );
}

function ApprovalForm({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const toast = useToast();
  const assessments = useApi<Array<{ id: string; assessment_status: string; freshness: string; manuscript_fingerprint: string }>>(
    `/api/publication/assessments?project_id=${projectId}`,
  );
  const [assessmentId, setAssessmentId] = useState("");
  const [decision, setDecision] = useState("APPROVE_RELEASE_CANDIDATE");
  const [rationale, setRationale] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [acceptedIds, setAcceptedIds] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = assessments.data ?? [];
  const activeId = assessmentId || rows[0]?.id || "";
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/publication/approvals", {
        assessment_id: activeId,
        decision,
        rationale,
        reviewer,
        accepted_limitation_ids: acceptedIds.split(",").map((part) => part.trim()).filter(Boolean),
      });
      toast.push("success", "Approval recorded (snapshot-bound, not a release)");
      assessments.reload();
      onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  if (assessments.loading && !assessments.data) return <LoadingBlock label="Loading assessments" compact />;
  if (assessments.error) return <ErrorState message={assessments.error.message} onRetry={assessments.reload} />;
  if (rows.length === 0) return <p className="muted">No assessment to approve. Create one from the Assessments section first.</p>;
  return (
    <div className="inline-form">
      <label className="field"><span>Assessment snapshot</span>
        <select value={activeId} onChange={(event) => setAssessmentId(event.target.value)}>
          {rows.map((row) => <option key={row.id} value={row.id}>{row.id} · {row.assessment_status} · {row.freshness}</option>)}
        </select>
      </label>
      <label className="field"><span>Decision</span>
        <select value={decision} onChange={(event) => setDecision(event.target.value)}>
          {APPROVAL_DECISIONS.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      </label>
      <label className="field"><span>Reviewer (human identity)</span>
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Your name" aria-label="Approval reviewer" />
      </label>
      <label className="field"><span>Rationale</span>
        <input value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this decision" aria-label="Approval rationale" />
      </label>
      <label className="field"><span>Accepted limitation issue ids (comma-separated, waivable only)</span>
        <input value={acceptedIds} onChange={(event) => setAcceptedIds(event.target.value)} placeholder="issue ids" aria-label="Accepted limitation issue ids" />
      </label>
      <InlineError message={error} />
      <button className="button button-primary button-small" disabled={busy || !reviewer.trim() || !activeId} onClick={() => void submit()}>
        {busy ? "…" : "Record approval"}
      </button>
      <p className="muted small">Approval binds one exact manuscript snapshot and policy version. Stale snapshots and blocked candidates are refused with an explicit reason. Approval is not deployment and never carries across snapshots.</p>
    </div>
  );
}

export function BookPublishingPage() {
  const { projectId = "" } = useParams();
  const toast = useToast();
  const [tab, setTab] = useState<PublishTab>("Overview");
  const [candidateFocus, setCandidateFocus] = useState<string | null>(null);
  const openCandidate = (recordId: string) => { setCandidateFocus(recordId); setTab("Candidates"); };
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
      <div className="harness-tabs" role="tablist" aria-label="Publication sections">
        {PUBLISH_TABS.map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} className={`button button-small ${tab === name ? "button-secondary" : "button-ghost"}`} onClick={() => setTab(name)}>
            {name}
          </button>
        ))}
      </div>
      {summary.loading && !summary.data ? <LoadingBlock label="Loading publishing evidence" /> : null}
      {summary.error ? <ErrorState message={summary.error.message} onRetry={summary.reload} /> : null}
      {summary.data ? (
        <>
          {tab === "Overview" ? (
            <>
              <div className="stat-strip">
                <Stat label="Lifecycle" value={summary.data.lifecycle ?? "unknown"} detail={summary.data.lifecycle_note} />
                <Stat label="Publication gate" value={summary.data.publication_gate} />
                <Stat label="Chapters" value={summary.data.chapter_count ?? "—"} />
                <Stat label="Fingerprint" value={summary.data.fingerprint_match == null ? "unknown" : summary.data.fingerprint_match ? "match" : "mismatch"} />
              </div>
              <Section title="Recommended next action" description="Derived from the current gates and blockers, in priority order.">
                <p>{nextRecommendedAction(summary.data)}</p>
              </Section>
              <AssessmentSection projectId={projectId} bookId={summary.data.book_id} onChanged={summary.reload} />
            </>
          ) : null}
          {tab === "Chapters" ? <ChaptersTab projectId={projectId} onOpenCandidate={openCandidate} /> : null}
          {tab === "Evidence" ? (
            <>
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
            </>
          ) : null}
          {tab === "Editorial" ? (
            <Section title="Editorial findings" description="Publication issues grouped by chapter, with detector detail in the owning systems. Findings shown here are tracked records, not new analysis.">
              <EditorialTab projectId={projectId} />
              <p className="muted small">
                Detector detail lives where the analysis runs: <Link to={`/projects/${projectId}?tab=quality`}>quality tab</Link> for prose findings,{" "}
                <Link to={`/projects/${projectId}?tab=technical`}>technical tab</Link> for claim and evidence verification.
              </p>
            </Section>
          ) : null}
          {tab === "Candidates" ? <CandidatesTab key={candidateFocus ?? "all"} projectId={projectId} focusId={candidateFocus} /> : null}
          {tab === "Review" ? (
            <>
              <Section title="Approvals" description="Author approval of one exact release snapshot. Approval is a mandatory gate and stays distinct from manuscript application and publication.">
                <ApprovalForm projectId={projectId} onChanged={summary.reload} />
              </Section>
              <Section title="Issue reviews" description="Per-issue author decisions with recorded rationale. Non-waivable issues cannot be accepted as limitations.">
                <IssuesReviewList projectId={projectId} onChanged={summary.reload} />
              </Section>
            </>
          ) : null}
          {tab === "Publish" ? (
            <PublishTab summary={summary.data} projectId={projectId} onChanged={summary.reload} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function EditorialTab({ projectId }: { projectId: string }) {
  const chapters = useApi<ChaptersData>(`/api/publication/publishing/chapters?project_id=${projectId}`);
  if (chapters.loading && !chapters.data) return <LoadingBlock label="Loading chapter findings" compact />;
  if (chapters.error) return <ErrorState message={chapters.error.message} onRetry={chapters.reload} />;
  if (chapters.data?.error) return <EmptyState title="Editorial findings unavailable" description={chapters.data.error} />;
  const withIssues = (chapters.data?.chapters ?? []).filter((row) => row.issues.length > 0 || row.followups.length > 0);
  if (withIssues.length === 0) return <EmptyState title="No tracked editorial findings" description="No publication issues or follow-ups reference any chapter. Detector output lives in the quality and technical tabs until it is promoted to a tracked record." />;
  return (
    <div>
      {withIssues.map((row) => (
        <div key={row.chapter_id} className="panel review-card">
          <div className="activity-head">
            <strong>{row.chapter_id} · {row.title}</strong>
            <Tag>{row.state}</Tag>
          </div>
          {row.issues.map((issue) => (
            <p key={issue.id} className="row-line"><code>{issue.gate_id}</code> · {issue.issue_type} · {issue.severity} · {issue.status} · author review: {issue.author_review_status}</p>
          ))}
          {row.followups.map((followup) => (
            <p key={followup.id} className="row-line"><code>{followup.evidence_type}</code> · {followup.title} · {followup.status}</p>
          ))}
        </div>
      ))}
    </div>
  );
}

function PublishTab({ summary, projectId, onChanged }: { summary: PublishingSummary; projectId: string; onChanged: () => void }) {
  const failed = summary.blockers.failed ?? [];
  const stale = summary.blockers.stale ?? [];
  const missing = summary.blockers.missing ?? [];
  const ready = failed.length === 0 && stale.length === 0 && missing.length === 0;
  return (
    <>
      <Section title="Publication readiness" description="Readiness is derived from gates, blockers and approvals — never asserted.">
        <div className="stat-strip">
          <Stat label="Gate" value={summary.publication_gate} />
          <Stat label="Failed" value={String(failed.length)} />
          <Stat label="Stale" value={String(stale.length)} />
          <Stat label="Missing" value={String(missing.length)} />
        </div>
        {ready ? (
          <p>Awaiting author approval of the exact snapshot. Approval happens in the Review tab and binds one manuscript fingerprint and policy version.</p>
        ) : (
          <p className="muted">Blocked: resolve or explicitly waive the items under “Blockers and next actions” on the Evidence tab, then record approval in the Review tab.</p>
        )}
        <p className="muted small">Actual release (rendering, packaging, publication) remains PUB-10 work. This tab prepares readiness; it does not publish, deploy, or mutate the manuscript.</p>
      </Section>
      <Section title="Blockers and next actions" description="Failed, stale and missing evidence plus the owning system for each.">
        {failed.length === 0 && stale.length === 0 && missing.length === 0 ? (
          <p className="muted">No blockers. Every gate is either passing or explicitly unknown.</p>
        ) : (
          <>
            {failed.map((name) => (
              <BlockerRow key={`failed:${name}`} projectId={projectId} kind="failed" name={name} onChanged={onChanged} />
            ))}
            {stale.map((name) => (
              <BlockerRow key={`stale:${name}`} projectId={projectId} kind="stale" name={name} onChanged={onChanged} />
            ))}
            {missing.map((name) => (
              <BlockerRow key={`missing:${name}`} projectId={projectId} kind="missing" name={name} onChanged={onChanged} />
            ))}
          </>
        )}
      </Section>
      <Section title="Follow-ups" description="Promoted blockers with provenance and re-checks.">
        <FollowupsSection projectId={projectId} onChanged={onChanged} />
      </Section>
      <AssessmentSection projectId={projectId} bookId={summary.book_id} onChanged={onChanged} />
    </>
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
