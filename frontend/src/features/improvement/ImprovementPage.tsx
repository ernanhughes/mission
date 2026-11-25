import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiPath } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, ErrorState, LoadingBlock, Section, Stat, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";

type Episode = { id: string; title?: string; project_key?: string; status?: string; outcome_status?: string };
type Finding = { id: string; episode_id: string; title?: string; kind?: string; status?: string; severity?: string; description?: string };
type Proposal = { id?: string; proposal_id?: string; status?: string; objective?: string; episode_id?: string; action_category?: string };
type Envelope = { id?: string; envelope_id?: string; episode_id?: string; status?: string; commission_digest?: string; objective_ref?: string };
type Catalogue = { worker?: { reachable?: boolean; status?: string; version?: string }; strategies?: unknown[] };
type Sc3Records = { status: string; source?: string; operational_record?: boolean; formal_acceptance?: string;
  actual_worker_model_invocations?: number; mission_writes?: number;
  experiment?: { experiment_id?: string; protocol_digest?: string; qualification?: string; comparisons?: Array<Record<string, any>>; execution_failure?: Record<string, any>; invalid_candidate?: Record<string, any> };
  candidate?: { candidate_id?: string; name?: string; intervention?: string; parameters?: Record<string, unknown>; hypothesis?: Record<string, any>; digest?: string };
  hypothesis_inference?: { model?: string; request_id?: string; authority?: string; evaluator_in_context?: boolean; raw_response_present?: boolean; raw_response_exposed?: boolean };
  retained_experience?: Array<Record<string, any>> };
type View = "overview" | "opportunities" | "experiments" | "experience" | "configuration";

const VIEWS: { id: View; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "opportunities", label: "Opportunities" },
  { id: "experiments", label: "Experiments" },
  { id: "experience", label: "Experience" },
  { id: "configuration", label: "Configuration" },
];

export function ImprovementPage() {
  const [view, setView] = useState<View>("overview");
  const [episodeId, setEpisodeId] = useState("");
  const toast = useToast();
  const health = useApi<Record<string, any>>("/api/health");
  const episodes = useApi<{ episodes: Episode[] }>("/api/work-episodes?limit=100");
  const findingsPath = apiPath("/api/work-evaluation/findings", { episode_id: episodeId || undefined, status: "open", limit: 100 });
  const findings = useApi<{ findings: Finding[] }>(episodeId ? findingsPath : null);
  const proposals = useApi<{ proposals: Proposal[] }>("/api/work-corrective/proposals?limit=100");
  const envelopes = useApi<{ envelopes: Envelope[] }>("/api/work-envelopes?limit=100");
  const worker = useApi<Catalogue>("/api/harness/catalogue");
  const praxis = useApi<unknown[]>("/api/praxis/proposals?limit=100");
  const sc3 = useApi<Sc3Records>("/api/improvement/records");
  const [selectedFinding, setSelectedFinding] = useState("");
  const [proposalBusy, setProposalBusy] = useState(false);
  const [createdProposal, setCreatedProposal] = useState<string | null>(null);

  const selectedEpisode = episodes.data?.episodes.find((row) => row.id === episodeId);
  const chosenFinding = findings.data?.findings.find((row) => row.id === selectedFinding);
  const unresolved = useMemo(() => (findings.data?.findings ?? []).filter((row) => row.status === "open"), [findings.data]);

  async function createGovernedRequest() {
    if (!selectedEpisode || !chosenFinding) return;
    setProposalBusy(true);
    try {
      const result = await api.post<{ status: string; proposal_id?: string; error?: string }>("/api/work-corrective/proposals", {
        episode_id: selectedEpisode.id,
        finding_ids: [chosenFinding.id],
        action_category: "REQUEST_USER_DECISION",
        objective: `Investigate whether this observed issue supports a bounded improvement opportunity: ${chosenFinding.title ?? chosenFinding.id}`,
        scope: "Evidence review and hypothesis proposal only. Any experiment requires separate human authorization through the existing Mission Work Envelope workflow.",
        exclusions: "No production changes, automatic execution, evaluator changes, acceptance, or promotion.",
        acceptance_criteria: "Return supported opportunity, additional evidence required, insufficient evidence, or abstention, with source-linked limitations.",
        required_verification: "Independent review of source identity and evidence references before experiment authorization.",
        suggested_route: "manual",
        cost_constraints: "No paid inference; any model-assisted step requires explicit bounded authorization.",
        risk: "low",
      });
      if (result.status !== "completed" && result.status !== "duplicate") throw new Error(result.error ?? "Mission rejected the proposal");
      setCreatedProposal(result.proposal_id ?? null);
      toast.push("success", "Governed investigation request recorded", result.proposal_id ?? "Open Work Evaluation proposals to review.");
      void proposals.reload();
    } catch (error) {
      toast.push("error", "Request not recorded", error instanceof Error ? error.message : "Mission request failed.");
    } finally {
      setProposalBusy(false);
    }
  }

  return <div className="page">
    <header className="page-header">
      <div><span className="eyebrow">Stephanie / Mission Control</span><h1>Improvement</h1>
        <p>Investigate verified work observations, review bounded proposals, and preserve human authorization.</p></div>
      <div className="page-actions"><Link className="button button-ghost" to="/activity?tab=work">Work Evaluation</Link><Link className="button button-ghost" to="/harness">Harness</Link></div>
    </header>
    <div className="toolbar" role="tablist" aria-label="Improvement views">
      {VIEWS.map((item) => <button key={item.id} type="button" role="tab" aria-selected={view === item.id}
        className={`button button-small ${view === item.id ? "button-primary" : "button-ghost"}`} onClick={() => setView(item.id)}>{item.label}</button>)}
    </div>

    {view === "overview" ? <div className="grid-2">
      <Section title="Connected capabilities" description="Each state is read from the current Mission API response. A stopped backend is unavailable, never a zero count.">
        <div className="stat-grid">
          <Stat label="Mission" value={health.loading ? "Checking" : health.data?.status ?? "Unavailable"} />
          <Stat label="Worker" value={worker.loading ? "Checking" : worker.data?.worker?.reachable ? "Reachable" : worker.error ? "Unavailable" : "Unavailable"} />
          <Stat label="Work Episodes" value={episodes.data?.episodes?.length ?? (episodes.error ? "Unavailable" : "—")} />
          <Stat label="Mission Praxis proposals" value={praxis.data ? "Available" : praxis.error ? "Unavailable" : "Checking"} />
          <Stat label="SC3 artifact snapshot" value={sc3.data?.status === "available" ? "Available (isolated)" : sc3.data?.status ?? "Checking"} />
        </div>
        {health.error ? <ErrorState message="Mission backend is unavailable. Improvement records cannot be refreshed." onRetry={health.reload} /> : null}
        <p className="muted small">Stephanie currently exposes its improvement workflow through its local CLI. Mission does not report that CLI as an online service. Experiment execution remains gated by an approved Work Envelope.</p>
      </Section>
      <Section title="Governance boundary" description="Mission remains the authority for objectives, approval, Work Outcome and formal acceptance.">
        <ul className="plain-list"><li>Creating a request records a draft proposal only.</li><li>Approval and experiment authorization are separate human decisions.</li><li>Worker completion, evaluation, Praxis recommendation and formal acceptance remain distinct.</li><li>No production promotion is available from this page.</li></ul>
        <p><Link to="/activity?tab=work" className="button button-ghost button-small">Review Work Outcome proposals</Link></p>
      </Section>
    </div> : null}

    {view === "opportunities" ? <Section title="Mission observations" description="Select an existing Work Episode and open finding. Requesting an investigation creates an inert Mission proposal; it does not invoke Stephanie or start an experiment.">
      {episodes.loading ? <LoadingBlock compact /> : null}
      {episodes.error ? <ErrorState message={episodes.error.message} onRetry={episodes.reload} /> : null}
      {episodes.data && !episodes.data.episodes.length ? <EmptyState title="No Work Episodes available" description="Mission has no episode records in the current view." /> : null}
      {episodes.data && episodes.data.episodes.length ? <label className="field"><span>Work Episode</span><select value={episodeId} onChange={(event) => { setEpisodeId(event.target.value); setSelectedFinding(""); setCreatedProposal(null); }}>
        <option value="">Select an episode</option>{episodes.data.episodes.map((row) => <option key={row.id} value={row.id}>{row.project_key || "Unknown project"} · {row.title || row.id}</option>)}
      </select></label> : null}
      {findings.loading ? <LoadingBlock compact /> : null}{findings.error ? <ErrorState message={findings.error.message} onRetry={findings.reload} /> : null}
      {episodeId && findings.data && !unresolved.length ? <EmptyState title="No open findings" description="This episode has no open finding to ground an improvement request." /> : null}
      {unresolved.length ? <div className="stack-list">{unresolved.map((row) => <label className="list-row" key={row.id}>
        <input type="radio" name="improvement-finding" checked={selectedFinding === row.id} onChange={() => setSelectedFinding(row.id)} />
        <span><strong>{row.title || row.kind || row.id}</strong><small>{row.kind || "Finding"} · {row.severity || "severity unknown"} · {row.id}</small>{row.description ? <small>{row.description}</small> : null}</span>
      </label>)}</div> : null}
      <div className="page-actions"><button className="button button-primary" type="button" disabled={!chosenFinding || proposalBusy} onClick={() => void createGovernedRequest()}>{proposalBusy ? "Recording…" : "Create governed investigation request"}</button>
        {createdProposal ? <Link className="button button-ghost" to="/activity?tab=work">Review proposal {createdProposal}</Link> : null}</div>
    </Section> : null}

    {view === "experiments" ? <div className="grid-2">
      <Section title="Mission proposals" description="Existing Work Outcome proposals remain the approval authority.">
        {proposals.loading ? <LoadingBlock compact /> : null}{proposals.error ? <ErrorState message={proposals.error.message} onRetry={proposals.reload} /> : null}
        {proposals.data && !proposals.data.proposals.length ? <EmptyState title="No proposals in the current response" description="No Mission proposal records were returned." /> : null}
        {proposals.data?.proposals.map((row, index) => <div className="list-row" key={row.id ?? row.proposal_id ?? `${row.episode_id}-${index}`}><span><strong>{row.objective || row.id || row.proposal_id}</strong><small>{row.status ?? "status unknown"} · {row.action_category ?? "action unknown"} · {row.episode_id ?? "no episode"}</small></span><Tag>{row.status ?? "unknown"}</Tag></div>)}
        <p><Link to="/activity?tab=work" className="button button-ghost button-small">Open approval workflow</Link></p>
      </Section>
      <Section title="Authorized work envelopes" description="An approved proposal or explicit human authorization is required before bounded execution.">
        {envelopes.loading ? <LoadingBlock compact /> : null}{envelopes.error ? <ErrorState message={envelopes.error.message} onRetry={envelopes.reload} /> : null}
        {envelopes.data && !envelopes.data.envelopes.length ? <EmptyState title="No envelopes in the current response" description="No authorized work envelope was returned." /> : null}
        {envelopes.data?.envelopes.map((row, index) => <div className="list-row" key={row.id ?? row.envelope_id ?? index}><span><strong>{row.id ?? row.envelope_id}</strong><small>{row.status ?? "status unknown"} · episode {row.episode_id ?? "unknown"} · digest {row.commission_digest?.slice(0, 12) ?? "missing"}</small></span><Tag>{row.status ?? "unknown"}</Tag></div>)}
        <p><Link to="/harness?tab=execute" className="button button-ghost button-small">Open bounded Worker execution</Link></p>
      </Section>
      <Section title="Praxis governance" description="Mission's Praxis proposal approvals are distinct from SC3 comparative effectiveness results.">
        {praxis.error ? <ErrorState message={praxis.error.message} onRetry={praxis.reload} /> : null}
        {praxis.data ? <p>{praxis.data.length} governed proposal record(s) returned. <Link to="/integrations">Open integrations</Link></p> : null}
      </Section>
      <Section title="SC3 candidate and comparison" description="Historical isolated evidence only; these values are not operational records.">
        {sc3.loading ? <LoadingBlock compact /> : null}{sc3.error ? <ErrorState message={sc3.error.message} onRetry={sc3.reload} /> : null}
        {sc3.data?.status === "available" ? <><p><strong>{sc3.data.candidate?.name}</strong> · {sc3.data.candidate?.candidate_id}</p><p>{sc3.data.candidate?.intervention}</p>
          <p className="muted small">Formal acceptance: {sc3.data.formal_acceptance}; actual Worker model calls in this deterministic run: {sc3.data.actual_worker_model_invocations}; operational record: no.</p>
          <div className="page-actions"><button className="button button-ghost button-small" type="button" onClick={() => setView("experience")}>Inspect retained experience</button></div></> : <p className="muted">No verified SC3 artifact snapshot is configured.</p>}
      </Section>
      <Section title="Execution and outcome" description="Worker executions are surfaced through Harness; evaluation and acceptance remain separate Work Outcome states.">
        <p><Link to="/harness?tab=executions">Inspect Worker execution evidence</Link> · <Link to="/activity?tab=work">Inspect evaluation and acceptance</Link></p>
        <p className="muted small">A completed experiment may conclude that a candidate is ineffective. Completion does not imply improvement or acceptance.</p>
      </Section>
    </div> : null}

    {view === "experience" ? <Section title="Retained experience" description="Mission reads a bounded projection of Stephanie's existing isolated SC3 artifact; it does not copy its database or expose raw model output.">
      {sc3.loading ? <LoadingBlock compact /> : null}{sc3.error ? <ErrorState message={sc3.error.message} onRetry={sc3.reload} /> : null}
      {sc3.data?.status !== "available" ? <EmptyState title="Stephanie artifact snapshot unavailable" description="Configure MISSION_CONTROL_STEPHANIE_ARTIFACT_ROOT to the verified SC3 artifact directory. The current response does not establish that Stephanie is running." /> : null}
      {sc3.data?.status === "available" ? <><p><Tag>Isolated SC3 evidence · not operational</Tag></p>
        {(sc3.data.retained_experience ?? []).map((row, index) => <div className="list-row" key={`${row.experiment_id ?? "experience"}-${index}`}><span>
          <strong>{row.outcome ?? "Outcome unknown"} · {row.recommendation ?? "No recommendation"}</strong>
          <small>Experiment {row.experiment_id ?? "unknown"} · decision {row.decision_status ?? "unknown"} · reuse eligible {String(row.reuse_eligible ?? "unknown")}</small>
          <small>{row.limitations ?? "No limitation record"}</small><small>Worker references {row.execution_reference_count ?? 0} · evaluations {(row.evaluation_references ?? []).join(", ") || "none"}</small>
        </span></div>)}
        <p>Candidate hypothesis: {sc3.data.candidate?.hypothesis?.statement ?? "missing"}</p>
        <p className="muted small">Hypothesis call: {sc3.data.hypothesis_inference?.model ?? "unknown"}; authority {sc3.data.hypothesis_inference?.authority ?? "unknown"}; raw response retained {String(sc3.data.hypothesis_inference?.raw_response_present ?? false)}, exposed here {String(sc3.data.hypothesis_inference?.raw_response_exposed ?? true)}.</p>
        <p className="muted small">Retrieval availability does not demonstrate that prior experience improves a later result.</p></> : null}
    </Section> : null}

    {view === "configuration" ? <div className="grid-2">
      <Section title="Integration posture" description="Current backend responses are authoritative; missing services are shown as unavailable.">
        <ul className="plain-list"><li>AI: shared inference foundation, consumed by Stephanie.</li><li>Stephanie: local CLI; no Mission-facing API currently registered.</li><li>Worker: existing Harness catalogue and execution interface.</li><li>Praxis: existing callable comparison in Stephanie; Mission proposal governance remains separate.</li><li>Mission: Work Outcome, corrective proposals, Work Envelopes, evaluation and human decisions.</li></ul>
      </Section>
      <Section title="Qualification limits" description="SC3 established deterministic integration, not operational effectiveness.">
        <ul className="plain-list"><li>Genuine Worker comparison: one pair; Praxis returned insufficient evidence.</li><li>No production promotion or automated acceptance.</li><li>Model cost, provider semantics and broader hypothesis quality remain unqualified.</li><li>Mission operational backend must pass its activation gate before these views can be used live.</li></ul>
      </Section>
    </div> : null}
  </div>;
}
