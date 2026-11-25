import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import { EmptyState, ErrorState, LoadingBlock, Section } from "../../components/ui";
import type { WorkProposal, WorkProposalDetail } from "../../types/api";

/**
 * W7 corrective proposals. Read-only on load (proposal list only).
 * Every mutation is an explicit button click with confirm gates;
 * approval additionally requires a human actor name.
 */
export function ProposalsPanel({ episodeId }: { episodeId?: string }) {
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const base = `/api/work-corrective/proposals${episodeId ? `?episode_id=${encodeURIComponent(episodeId)}` : ""}`;
  const list = useApi<{ proposals: WorkProposal[] }>(base);

  return (
    <div>
      <div className="toolbar">
        <select
          aria-label="Filter by proposal status"
          value={status}
          onChange={(e) => { setStatus(e.target.value); setSelected(null); }}
        >
          <option value="">All statuses</option>
          {["draft", "ready_for_review", "approved", "queued", "running", "reported_complete", "verification_pending", "verified_resolved", "rejected", "deferred", "failed", "cancelled"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="toolbar-count">{(list.data?.proposals ?? []).filter((p) => !status || p.status === status).length} proposal(s)</span>
      </div>
      {selected ? (
        <ProposalDetail id={selected} onBack={() => { setSelected(null); list.reload(); }} />
      ) : list.loading ? (
        <LoadingBlock label="Loading proposals" />
      ) : list.error ? (
        <ErrorState message={`Proposals unavailable: ${list.error.message}`} onRetry={list.reload} />
      ) : (
        <ProposalList
          items={(list.data?.proposals ?? []).filter((p) => !status || p.status === status)}
          onOpen={setSelected}
        />
      )}
    </div>
  );
}

function ProposalList({ items, onOpen }: { items: WorkProposal[]; onOpen: (id: string) => void }) {
  if (items.length === 0)
    return (
      <EmptyState
        title="No corrective proposals"
        description="Generate a commission from an Outstanding Work group or an individual finding. Proposals never execute on their own."
      />
    );
  return (
    <ul className="activity-feed">
      {items.map((p) => (
        <li key={p.id}>
          <span className="activity-marker type-user" aria-hidden="true" />
          <div className="activity-entry">
            <div className="activity-head">
              <strong>{p.objective || p.action_category}</strong>
            </div>
            <div className="activity-meta">
              <span>{p.action_category}</span>
              <span>{p.status}</span>
              <span>v{p.version}</span>
              <span>{p.finding_ids.length} finding(s)</span>
            </div>
            <div className="activity-actions">
              <button type="button" className="button button-ghost button-small" onClick={() => onOpen(p.id)}>
                Inspect proposal
              </button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ProposalDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [showCommission, setShowCommission] = useState(false);
  const detail = useApi<{ proposal: WorkProposalDetail }>(`/api/work-corrective/proposals/${id}`);
  const commission = useApi<{ sections: string[]; version: number }>(
    showCommission ? `/api/work-corrective/proposals/${id}/commission` : null,
  );

  async function run(label: string, path: string, body?: unknown) {
    setBusy(label);
    try {
      const out = await api.post<Record<string, unknown>>(path, body);
      if (out.status && !["completed", "no_change"].includes(String(out.status))) throw new Error(String(out.error ?? out.status));
      toast.push("success", label);
      detail.reload();
    } catch (caught) {
      toast.push("error", `${label} failed: ${errorMessage(caught)}`);
    } finally {
      setBusy(null);
    }
  }

  if (detail.loading) return <LoadingBlock label="Loading proposal" />;
  if (detail.error)
    return <ErrorState message={`Proposal unavailable: ${detail.error.message}`} onRetry={detail.reload} />;
  const p = detail.data?.proposal;
  if (!p) return <EmptyState title="Proposal not found" description="It may have been removed from scope." />;

  const terminal = ["verified_resolved", "cancelled"].includes(p.status);
  return (
    <div>
      <div className="toolbar">
        <button type="button" className="button button-ghost button-small" onClick={onBack}>
          Back to proposals
        </button>
        <span className="toolbar-count">{p.id} · v{p.version} · {p.status}</span>
      </div>
      <Section title="Proposal">
        <p className="muted">Action: {p.action_category} · Route: {p.suggested_route} · Risk: {p.risk}</p>
        <p><strong>Objective:</strong> {p.objective || "(unset)"}</p>
        <p><strong>Scope:</strong> {p.scope || "(as narrow as the linked findings)"}</p>
        <p><strong>Exclusions:</strong> {p.exclusions || "no repository changes beyond scope; no push/deploy"}</p>
        <p><strong>Acceptance:</strong> {p.acceptance_criteria || "(evidence class per finding)"}</p>
        <p><strong>Required verification:</strong> {p.required_verification || "(independent check; no self-verification)"}</p>
        <p className="muted">Findings: {p.finding_ids.join(", ") || "(none)"} · Closure: {p.closure_status}</p>
      </Section>
      <Section title="Commission">
        <div className="activity-actions">
          <button type="button" className="button button-small" onClick={() => setShowCommission((v) => !v)}>
            {showCommission ? "Hide commission" : "Preview commission"}
          </button>
          {showCommission && !commission.loading && commission.data ? (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => void navigator.clipboard?.writeText((commission.data?.sections ?? []).join("\n")).then(
                () => toast.push("success", "Commission copied — paste it where the work will be done"),
                () => toast.push("error", "Copy failed"),
              )}
            >
              Copy commission
            </button>
          ) : null}
        </div>
        {showCommission ? (
          commission.loading ? <LoadingBlock label="Assembling commission" /> :
          commission.error ? <ErrorState message={`Commission unavailable: ${commission.error.message}`} onRetry={commission.reload} /> : (
            <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>{(commission.data?.sections ?? []).join("\n")}</pre>
          )
        ) : null}
      </Section>
      {!terminal ? (
        <Section title="Authorization">
          <div className="toolbar">
            <input
              className="input input-small"
              style={{ maxWidth: 200 }}
              placeholder="Actor name (required to approve)"
              aria-label="Actor name for approval"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
            <input
              className="input input-small"
              style={{ maxWidth: 260 }}
              placeholder="Reason"
              aria-label="Reason for transition"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div className="activity-actions">
            {p.status === "draft" ? (
              <button type="button" className="button button-small" disabled={busy !== null} onClick={() => void run("Submit for review", `/api/work-corrective/proposals/${id}/transition`, { to_status: "ready_for_review", actor: actor || "operator", reason })}>
                Submit for review
              </button>
            ) : null}
            {p.status === "ready_for_review" ? (
              <>
                <button type="button" className="button button-small" disabled={busy !== null || !actor.trim()} onClick={() => {
                if (!window.confirm(`Approve proposal ${p.id} v${p.version}? This authorizes handoff, not execution.`)) return;
                void run("Approve", `/api/work-corrective/proposals/${id}/transition`, { to_status: "approved", actor: actor.trim(), reason, confirm: true });
              }}>
                Approve (human, version-pinned)
              </button>
                <button type="button" className="button button-ghost button-small" disabled={busy !== null} onClick={() => void run("Reject", `/api/work-corrective/proposals/${id}/transition`, { to_status: "rejected", actor: actor || "operator", reason, confirm: true })}>
                  Reject
                </button>
                <button type="button" className="button button-ghost button-small" disabled={busy !== null} onClick={() => void run("Defer", `/api/work-corrective/proposals/${id}/transition`, { to_status: "deferred", actor: actor || "operator", reason, confirm: true })}>
                  Defer
                </button>
              </>
            ) : null}
            {p.status === "approved" ? (
              <button type="button" className="button button-small" disabled={busy !== null} onClick={() => void run("Record manual handoff", `/api/work-corrective/proposals/${id}/handoff`, { route: "manual", actor: actor || "operator", confirm: true })}>
                Record manual handoff
              </button>
            ) : null}
            {(p.executions ?? []).length > 0 ? (
              <span className="muted">Handoffs: {p.executions.map((e) => `${e.route}:${e.external_ref || e.id}(${e.status})`).join(", ")}</span>
            ) : null}
          </div>
        </Section>
      ) : null}
      <Section title="History">
        <ul className="activity-feed">
          {(p.events ?? []).map((e, i) => (
            <li key={i}>
              <span className="activity-marker type-user" aria-hidden="true" />
              <div className="activity-entry">
                <div className="activity-meta">
                  <span>{e.from || "(none)"} → {e.to}</span>
                  <span>{e.actor}</span>
                  <span>{e.at}</span>
                </div>
                {e.reason ? <p className="muted">{e.reason}</p> : null}
              </div>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
