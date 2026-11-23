import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { InlineError, Section, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";

type Proposal = Record<string, any>;

export function OpportunityProposalBridge({ opportunityId }: { opportunityId: string }) {
  const toast = useToast();
  const [capabilityId, setCapabilityId] = useState("");
  const [acceptance, setAcceptance] = useState("human verifies the improvement");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Proposal | null>(null);

  async function create(dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const endpoint = dryRun
        ? `/api/inspect/opportunities/${opportunityId}/proposal-draft`
        : `/api/inspect/opportunities/${opportunityId}/proposals`;
      const body = await api.post<Record<string, any>>(endpoint, {
        capability_id: capabilityId.trim(),
        parameters: {},
        acceptance_criteria: [{ id: "a1", statement: acceptance, source: "human:owner" }],
        acceptance_provenance: "project workspace",
        expected_benefits: [],
        owner: "",
      });
      if (dryRun) {
        toast.push("success", "Draft preview ready", "No proposal was imported.");
      } else {
        setCreated((body as Proposal).proposal_key ? (body as Proposal) : ((body as { proposal?: Proposal }).proposal ?? body));
        toast.push("success", "Proposal imported", "Approval remains explicit and human.");
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="inline-form">
      <InlineError message={error} />
      <label className="muted small">
        Capability (optional, advisory when blank){" "}
        <input value={capabilityId} onChange={(e) => setCapabilityId(e.target.value)} placeholder="app.action" size={24} aria-label="Capability id" />
      </label>
      <label className="muted small">
        Acceptance{" "}
        <input value={acceptance} onChange={(e) => setAcceptance(e.target.value)} size={40} aria-label="Acceptance criterion" />
      </label>
      <button className="button button-secondary button-small" disabled={busy} onClick={() => void create(true)}>
        Preview draft
      </button>
      <button className="button button-primary button-small" disabled={busy} onClick={() => void create(false)}>
        {busy ? "Working…" : "Import governed proposal"}
      </button>
      {created ? (
        <p className="muted small">
          <Tag tone={created.status === "awaiting_approval" ? "accent" : "default"}>{String(created.status)}</Tag>{" "}
          {String(created.proposal_key)} — approval and execution stay on the governed Praxis route. Execution
          success, acceptance and improvement remain distinct.
        </p>
      ) : null}
    </div>
  );
}

export function LinkedProposals({ opportunityId }: { opportunityId: string }) {
  const proposals = useApi<Proposal[]>(`/api/praxis/proposals?limit=200`);
  if (proposals.loading || proposals.error || !proposals.data) return null;
  const linked = (proposals.data ?? []).filter((p) => {
    const refs: string[] = Array.isArray((p as Record<string, any>).evidence_refs)
      ? (p as Record<string, any>).evidence_refs
      : [];
    return refs.some((r) => typeof r === "string" && r.includes(opportunityId));
  });
  if (!linked.length) return null;
  return (
    <Section title="Linked Praxis proposals" description="Governed proposals seeded from this opportunity. Approval is human and explicit; execution never follows automatically.">
      <ul className="plain-list">
        {linked.map((p) => (
          <li key={String(p.proposal_key)}>
            <code>{String(p.proposal_key)}</code> · {String(p.status)}
            {p.approved_by ? ` · approved by ${String(p.approved_by)}` : " · not approved"}
            {p.execution_id ? ` · execution ${String(p.execution_id)}` : " · no execution"}
          </li>
        ))}
      </ul>
    </Section>
  );
}
