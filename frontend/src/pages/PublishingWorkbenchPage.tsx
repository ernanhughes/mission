import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, Plus, RefreshCw, XCircle } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import type { PublishingFollowup, PublishingOverview, PublishingOverviewRow } from "../types/api";

type IdentityConflicts = {
  registry?: string | null;
  errors?: unknown;
  candidates: Array<Record<string, unknown>>;
  conflicts: Array<Record<string, unknown>>;
  unavailable: string[];
  unregistered_writer?: string[];
  suggested_writer_mappings?: string[];
};

const stateTones: Record<string, string | undefined> = {
  passed: "accent",
  failed: undefined,
  pending: undefined,
  unavailable: undefined,
  unknown: undefined,
  current: "accent",
  stale: undefined,
};

function FollowupRow({ item, onChanged }: { item: PublishingFollowup; onChanged: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function act(path: string, body: Record<string, unknown>, verb: string) {
    setBusy(true);
    try {
      await api.post(`/api/publication/followups/${item.id}/${path}`, body);
      toast.push("success", `Follow-up ${verb}`);
      onChanged();
    } catch (caught) {
      toast.push("error", `Could not ${verb} follow-up`, errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>{item.title || item.evidence_type}</strong>
        <Tag>{item.status}</Tag>
        <span className="muted">{item.target_type} → {item.target_id ?? "—"}</span>
      </div>
      <p className="muted small">
        {item.evidence_type} · {item.source_reference || "no source ref"} · observed{" "}
        {item.observed_at || "unknown"}
      </p>
      <div className="button-row">
        {item.status !== "closed" ? (
          <>
            <button className="button button-secondary button-small" disabled={busy} onClick={() => void act("recheck", {}, "re-checked")}>
              <RefreshCw size={14} /> {busy ? "…" : "Re-check"}
            </button>
            <button className="button button-ghost button-small" disabled={busy} onClick={() => void act("close", {}, "closed")}>
              Close
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}

function FollowupsSection() {
  const [showClosed, setShowClosed] = useState(false);
  const open = useApi<PublishingFollowup[]>(
    `/api/publication/followups${showClosed ? "" : "?status=open"}`,
  );
  if (open.loading && !open.data) return <LoadingBlock label="Loading follow-ups" compact />;
  if (open.error) return <ErrorState message={open.error.message} onRetry={open.reload} />;
  const items = open.data ?? [];
  return (
    <Section
      title="Governed follow-ups"
      description="Blockers promoted to explicit work, with provenance and re-checks. Closing is always manual."
      actions={
        <button className="button button-ghost button-small" onClick={() => setShowClosed((value) => !value)}>
          {showClosed ? "Hide closed" : "Show closed"}
        </button>
      }
    >
      {items.length === 0 ? (
        <p className="muted">No follow-ups. Promote a blocker from a book page to track it here.</p>
      ) : (
        items.map((item) => <FollowupRow key={item.id} item={item} onChanged={open.reload} />)
      )}
    </Section>
  );
}

function IdentityInbox() {
  const toast = useToast();
  const conflicts = useApi<IdentityConflicts>("/api/books/identity-conflicts");
  const [busy, setBusy] = useState<string | null>(null);

  async function approveAlias(canonicalId: string, writerId: string) {
    setBusy(`${canonicalId}:${writerId}`);
    try {
      await api.post("/api/books/aliases", {
        canonical_project_id: canonicalId,
        system: "writer",
        external_id: writerId,
        confirm: true,
      });
      toast.push("success", "Identity alias confirmed");
      conflicts.reload();
    } catch (caught) {
      toast.push("error", "Could not confirm alias", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function suggestMapping(writerId: string) {
    setBusy(`suggest:${writerId}`);
    try {
      await api.post("/api/publication/followups", {
        project_id: writerId,
        evidence_type: "identity_mapping",
        source_reference: `writer:${writerId}`,
        title: `Confirm identity mapping for ${writerId}`,
        rationale: "Unregistered Writer book suggested by identity reconciliation. Confirm or map explicitly.",
        target_type: "task",
      });
      toast.push("success", "Mapping review queued as a follow-up");
    } catch (caught) {
      toast.push("error", "Could not queue mapping review", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  if (conflicts.loading && !conflicts.data) return <LoadingBlock label="Loading identity inbox" compact />;
  if (conflicts.error) return <ErrorState message={conflicts.error.message} onRetry={conflicts.reload} />;
  const data = conflicts.data;
  if (!data) return null;
  const rows = [...(data.candidates ?? []), ...(data.conflicts ?? [])];
  return (
    <Section
      title="Identity inbox"
      description="Writer registry vs Mission Control identity. Aliases are explicit and confirmed; nothing is inferred."
    >
      {rows.length === 0 && (data.unregistered_writer ?? []).length === 0 ? (
        <p className="muted">No identity conflicts. Every book resolves to one canonical identity.</p>
      ) : null}
      {rows.map((row, index) => {
        const projectId = String(row.project_id ?? "");
        const writerId = String((row as Record<string, unknown>).writer_id ?? "");
        const candidates = Array.isArray((row as Record<string, unknown>).candidates)
          ? ((row as Record<string, unknown>).candidates as unknown[])
          : [];
        const candidateId = writerId || (typeof candidates[0] === "string" ? (candidates[0] as string) : "");
        return (
          <div key={`${projectId}-${index}`} className="panel review-card">
            <div className="activity-head">
              <strong>{projectId || "Unknown book"}</strong>
              <Tag>{String((row as Record<string, unknown>).state ?? "candidate")}</Tag>
            </div>
            <p className="muted small">
              {String((row as Record<string, unknown>).reason ?? "")}
              {candidateId ? ` · Writer: ${candidateId}` : ""}
            </p>
            <div className="button-row">
              <button
                className="button button-secondary button-small"
                disabled={busy !== null || !candidateId || !projectId}
                onClick={() => void approveAlias(projectId, candidateId)}
              >
                <CheckCircle2 size={14} /> {busy ? "…" : "Confirm mapping"}
              </button>
            </div>
          </div>
        );
      })}
      {(data.unregistered_writer ?? []).map((writerId) => (
        <div key={String(writerId)} className="panel review-card">
          <div className="activity-head">
            <strong>{String(writerId)}</strong>
            <Tag>Unregistered writer book</Tag>
          </div>
          <div className="button-row">
            <button
              className="button button-ghost button-small"
              disabled={busy !== null}
              onClick={() => void suggestMapping(String(writerId))}
            >
              <Plus size={14} /> Queue mapping review
            </button>
          </div>
        </div>
      ))}
      {(data.unavailable ?? []).length > 0 ? (
        <p className="muted">Unavailable manuscripts: {(data.unavailable ?? []).join(", ")}</p>
      ) : null}
    </Section>
  );
}

function RowCard({ row }: { row: PublishingOverviewRow }) {
  const attention = row.failed.length + row.stale.length + row.missing.length + row.identity_conflicts.length;
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>{row.book_title || row.project_name || row.project_id}</strong>
        <Tag tone={row.failed.length ? undefined : "accent"}>
          {row.publication_gate}
        </Tag>
        {attention > 0 ? <Tag>Needs attention · {attention}</Tag> : <Tag tone="accent">Clear</Tag>}
        {row.error ? <Tag>Error</Tag> : null}
      </div>
      <p className="muted small">
        Lifecycle: {row.lifecycle ?? "unknown"} · Chapters: {row.chapter_count ?? "—"} · Fingerprint:{" "}
        {row.fingerprint_match == null ? "unknown" : row.fingerprint_match ? "match" : "mismatch"} ·
        Identity: {row.identity_state ?? "unknown"}
      </p>
      {(row.failed.length > 0 || row.stale.length > 0) && (
        <p className="muted small">
          {row.failed.length > 0 ? <><XCircle size={13} /> Failed: {row.failed.join(", ")} </> : null}
          {row.stale.length > 0 ? <>Stale: {row.stale.join(", ")}</> : null}
        </p>
      )}
      <div className="button-row">
        <Link className="button button-secondary button-small" to={`/projects/${row.project_id}/publishing`}>
          Open publishing <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
}

export function PublishingWorkbenchPage() {
  const overview = useApi<PublishingOverview>("/api/publication/publishing/overview");
  return (
    <div className="page">
      <PageHeader
        eyebrow="Publishing"
        title="Publishing workbench"
        description="Every book's publication readiness in one place. Evidence is read-only; follow-ups turn blockers into tracked, re-checkable work."
      />
      {overview.loading && !overview.data ? <LoadingBlock label="Loading publishing overview" /> : null}
      {overview.error ? <ErrorState message={overview.error.message} onRetry={overview.reload} /> : null}
      {overview.data ? (
        <>
          <div className="stat-strip">
            <Stat label="Books" value={overview.data.count} />
            <Stat label="Need attention" value={overview.data.needs_attention} />
          </div>
          <Section title="Books" description="One row per book. Open a book for gates, evidence and next actions.">
            {overview.data.books.length === 0 ? (
              <EmptyState title="No books" description="No book workspaces are registered." />
            ) : (
              overview.data.books.map((row) => <RowCard key={row.project_id} row={row} />)
            )}
          </Section>
        </>
      ) : null}
      <IdentityInbox />
      <FollowupsSection />
    </div>
  );
}
