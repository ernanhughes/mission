import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiPath } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, ErrorState, LoadingBlock, Section, Stat, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";

type Episode = { id: string; title?: string; project_key?: string; status?: string; outcome_status?: string };
type Finding = { id: string; episode_id: string; title?: string; kind?: string; status?: string; severity?: string; description?: string; rationale?: string; evidence_refs?: string[]; next_action?: string };
type Proposal = { id?: string; proposal_id?: string; status?: string; objective?: string; episode_id?: string; action_category?: string; finding_ids?: string[]; scope?: string; version?: number; scope_hash?: string; acceptance_criteria?: string };
type Envelope = { id?: string; envelope_id?: string; episode_id?: string; status?: string; commission_digest?: string; objective_ref?: string; authorization_ref?: string; originating_findings?: string[] };
type Catalogue = { worker?: { reachable?: boolean; status?: string; version?: string }; strategies?: unknown[] };
type Investigation = { investigation_id: string; source_identity: string; source_digest: string; source_snapshot?: { episode_id?: string; finding_id?: string }; status: string; result: string; hypothesis?: { statement?: string; rationale?: string; uncertainty?: string; evidence_ids?: string[]; generation?: string }; candidate?: Record<string, any> | null; proposed_experiments?: Array<Record<string, any>>; retrieved_experience?: Array<Record<string, unknown>>; authority?: string };
type Objective = { id: string; episode_id: string; text: string; status?: string };
type ExperimentDetail = { experiment_state?: string; human_decisions?: Array<{ decision?: string; actor?: string; rationale?: string; evidence?: { experiment_id?: string; result_digest?: string; candidate_id?: string } }>; retained_experience?: { status?: string; source?: string; records?: Array<{ name?: string; outcome?: string; scenario?: string; reuse_eligible?: boolean; promotion_status?: string; matched_terms?: number }> }; experiment_result?: { experiment_id?: string; protocol_digest?: string; actual_model_invocations?: number; formal_acceptance?: string; qualification?: string; praxis_comparisons?: Array<{ scenario?: string; recommendation?: string; praxis?: { decision?: string; rationale?: string }; resource_comparison?: { baseline_invocations?: number; candidate_invocations?: number; additional_compute?: boolean; cost_status?: string } }>; C6_execution_failure?: Record<string, unknown>; C7_invalid_candidate?: { rejected_before_execution?: boolean } } | null };
type IntegrationStatus = { mission_to_stephanie?: { status?: string; reason?: string; interface?: string; workflow?: string; execution_authority?: string }; worker_execution?: { status?: string; reason?: string }; praxis?: { status?: string; reason?: string } };
type Sc3Records = { status: string; source?: string; operational_record?: boolean; formal_acceptance?: string;
  actual_worker_model_invocations?: number; mission_writes?: number;
  experiment?: { experiment_id?: string; protocol_digest?: string; qualification?: string; comparisons?: Array<Record<string, any>>; execution_failure?: Record<string, any>; invalid_candidate?: Record<string, any> };
  candidate?: { candidate_id?: string; name?: string; intervention?: string; parameters?: Record<string, unknown>; hypothesis?: Record<string, any>; digest?: string };
  hypothesis_inference?: { model?: string; request_id?: string; authority?: string; evaluator_in_context?: boolean; raw_response_present?: boolean; raw_response_exposed?: boolean };
  retained_experience?: Array<Record<string, any>> };
type View = "overview" | "opportunities" | "investigations" | "experiments" | "experience" | "configuration";

const VIEWS: { id: View; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "opportunities", label: "Opportunities" },
  { id: "investigations", label: "Investigations" },
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
  const integration = useApi<IntegrationStatus>("/api/improvement/integration");
  const investigations = useApi<{ status: string; investigations: Investigation[] }>("/api/improvement/investigations");
  const [selectedFinding, setSelectedFinding] = useState("");
  const [selectedProposal, setSelectedProposal] = useState("");
  const [selectedInvestigation, setSelectedInvestigation] = useState("");
  const [proposalBusy, setProposalBusy] = useState(false);
  const [investigationBusy, setInvestigationBusy] = useState(false);
  const [experimentBusy, setExperimentBusy] = useState(false);
  const [selectedObjective, setSelectedObjective] = useState("");
  const [selectedAuthorization, setSelectedAuthorization] = useState("");
  const [selectedEnvelope, setSelectedEnvelope] = useState("");
  const [experimentProposalId, setExperimentProposalId] = useState<string | null>(null);
  const [createdProposal, setCreatedProposal] = useState<string | null>(null);
  const [decisionActor, setDecisionActor] = useState("");
  const [decisionRationale, setDecisionRationale] = useState("");

  const selectedEpisode = episodes.data?.episodes.find((row) => row.id === episodeId);
  const chosenFinding = findings.data?.findings.find((row) => row.id === selectedFinding);
  const approvedProposal = proposals.data?.proposals.find((row) => (row.id ?? row.proposal_id) === selectedProposal
    && row.status === "approved" && row.action_category === "REQUEST_USER_DECISION"
    && row.episode_id === episodeId && (row.finding_ids ?? []).includes(selectedFinding));
  const activeInvestigation = investigations.data?.investigations.find((row) => row.investigation_id === selectedInvestigation);
  const objectivesPath = apiPath("/api/work-intent/objectives", { episode_id: activeInvestigation?.source_snapshot?.episode_id, limit: 200 });
  const objectives = useApi<{ objectives: Objective[] }>(activeInvestigation?.source_snapshot?.episode_id ? objectivesPath : null);
  const investigationDetail = useApi<ExperimentDetail>(activeInvestigation ? `/api/improvement/investigations/${encodeURIComponent(activeInvestigation.investigation_id)}` : null);
  const unresolved = useMemo(() => (findings.data?.findings ?? []).filter((row) => row.status === "open"), [findings.data]);
  const proposedExperiment = activeInvestigation?.proposed_experiments?.[0];
  const authorizationProposals = (proposals.data?.proposals ?? []).filter((row) => {
    if (row.action_category !== "REQUEST_USER_DECISION" || row.episode_id !== activeInvestigation?.source_snapshot?.episode_id) return false;
    try { return JSON.parse(row.scope ?? "").investigation_id === activeInvestigation?.investigation_id; } catch { return false; }
  });
  // The integrated local dispatcher accepts either the human-approved proposal
  // or its already-recorded queued state; no manual file handoff is required.
  const approvedExperimentProposal = authorizationProposals.find((row) => (row.id ?? row.proposal_id) === selectedAuthorization && ["approved", "queued"].includes(row.status ?? ""));
  const matchingEnvelopes = (envelopes.data?.envelopes ?? []).filter((row) => row.status === "active" && row.episode_id === activeInvestigation?.source_snapshot?.episode_id
    && row.objective_ref === selectedObjective && approvedExperimentProposal
    && row.authorization_ref === `proposal:${approvedExperimentProposal.id}@v${approvedExperimentProposal.version}:${approvedExperimentProposal.scope_hash}`
    && !!activeInvestigation?.source_snapshot?.finding_id
    && row.originating_findings?.includes(activeInvestigation.source_snapshot.finding_id));

  async function createExperimentAuthorization() {
    if (!activeInvestigation || !selectedObjective) return;
    setExperimentBusy(true);
    try {
      const response = await api.post<{ status: string; proposal_id: string }>("/api/improvement/experiment-authorizations", { investigation_id: activeInvestigation.investigation_id, objective_id: selectedObjective });
      setSelectedAuthorization(response.proposal_id);
      setExperimentProposalId(response.proposal_id);
      await proposals.reload();
      toast.push("success", "Experiment decision request recorded", `Review ${response.proposal_id} through Work Corrective before dispatch.`);
    } catch (error) {
      toast.push("error", "Decision request not recorded", error instanceof Error ? error.message : "Mission rejected the request.");
    } finally { setExperimentBusy(false); }
  }

  async function createAuthorizedEnvelope() {
    if (!activeInvestigation || !approvedExperimentProposal || !selectedObjective) return;
    setExperimentBusy(true);
    try {
      const body = JSON.parse(approvedExperimentProposal.scope ?? "");
      if ((envelopes.data?.envelopes ?? []).some((row) => row.status === "active" && row.episode_id === body.episode_id)) throw new Error("An active envelope already exists for this episode. Reconcile it before creating or superseding an envelope.");
      const response = await api.post<{ status: string; envelope_id: string }>("/api/work-envelopes", {
        episode_id: body.episode_id, objective_id: body.objective_id, originating_findings: [body.finding_id],
        scope: approvedExperimentProposal.scope, acceptance_criteria: approvedExperimentProposal.acceptance_criteria,
        authorization_proposal_id: approvedExperimentProposal.id,
        programme_id: "STEPHANIE-CONVERGENCE-04", stage_id: "SC4B",
      });
      setSelectedEnvelope(response.envelope_id);
      await envelopes.reload();
      toast.push("success", "Authorized Work Envelope registered", response.envelope_id);
    } catch (error) {
      toast.push("error", "Work Envelope not registered", error instanceof Error ? error.message : "Mission rejected the envelope.");
    } finally { setExperimentBusy(false); }
  }

  async function recordHumanOutcomeDecision(decision: "accepted" | "rejected") {
    if (!activeInvestigation || !approvedExperimentProposal || !decisionActor.trim()) return;
    setExperimentBusy(true);
    try {
      const response = await api.post<{ status: string }>(`/api/improvement/investigations/${encodeURIComponent(activeInvestigation.investigation_id)}/decision`, {
        proposal_id: approvedExperimentProposal.id ?? approvedExperimentProposal.proposal_id,
        decision, actor: decisionActor.trim(), rationale: decisionRationale.trim(),
      });
      await investigationDetail.reload();
      toast.push("success", `Candidate ${decision}`, `Mission recorded this decision in Work Outcome (${response.status}).`);
    } catch (error) {
      toast.push("error", "Decision not recorded", error instanceof Error ? error.message : "Mission rejected the outcome decision.");
    } finally { setExperimentBusy(false); }
  }

  async function dispatchAuthorizedExperiment() {
    if (!activeInvestigation || !approvedExperimentProposal || !selectedEnvelope) return;
    setExperimentBusy(true);
    try {
      const result = await api.post<{ status: string }>("/api/improvement/experiments/dispatch", {
        proposal_id: approvedExperimentProposal.id ?? approvedExperimentProposal.proposal_id,
        envelope_id: selectedEnvelope, investigation_id: activeInvestigation.investigation_id,
      });
      toast.push("success", "Bounded experiment completed", `Mission recorded ${result.status}; inspect the experiment evidence below.`);
      await investigations.reload();
      await investigationDetail.reload();
    } catch (error) {
      toast.push("error", "Experiment not dispatched", error instanceof Error ? error.message : "Mission could not establish an authorized dispatch.");
    } finally { setExperimentBusy(false); }
  }

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

  async function requestStephanieInvestigation() {
    if (!selectedEpisode || !chosenFinding || !approvedProposal) return;
    setInvestigationBusy(true);
    try {
      const response = await api.post<{ status: string; investigation: Investigation }>("/api/improvement/investigations", {
        proposal_id: approvedProposal.id ?? approvedProposal.proposal_id,
        episode_id: selectedEpisode.id,
        finding_id: chosenFinding.id,
      });
      setSelectedInvestigation(response.investigation.investigation_id);
      setView("investigations");
      await investigations.reload();
      toast.push("success", "Stephanie investigation completed", response.investigation.result);
    } catch (error) {
      toast.push("error", "Stephanie investigation unavailable", error instanceof Error ? error.message : "Mission did not receive a verified result.");
      void investigations.reload();
    } finally {
      setInvestigationBusy(false);
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
          <Stat label="Stephanie investigation" value={integration.loading ? "Checking" : integration.data?.mission_to_stephanie?.status ?? "Unavailable"} />
          <Stat label="SC3 artifact snapshot" value={sc3.data?.status === "available" ? "Available (isolated)" : sc3.data?.status ?? "Checking"} />
        </div>
        {health.error ? <ErrorState message="Mission backend is unavailable. Improvement records cannot be refreshed." onRetry={health.reload} /> : null}
        {integration.data?.mission_to_stephanie?.reason ? <p className="muted small">Stephanie: {integration.data.mission_to_stephanie.reason}</p> : null}
        <p className="muted small">Stephanie can propose only a frozen deterministic fixture experiment. Execution requires a separate exact-scope human decision and matching active Work Envelope.</p>
      </Section>
      <Section title="Governance boundary" description="Mission remains the authority for objectives, approval, Work Outcome and formal acceptance.">
        <ul className="plain-list"><li>Creating a request records a draft proposal only.</li><li>Approval and experiment authorization are separate human decisions.</li><li>Worker completion, evaluation, Praxis recommendation and formal acceptance remain distinct.</li><li>No production promotion is available from this page.</li></ul>
        <p><Link to="/activity?tab=work" className="button button-ghost button-small">Review Work Outcome proposals</Link></p>
      </Section>
    </div> : null}

    {view === "opportunities" ? <Section title="Mission observations" description="Select an existing Work Episode and open finding. First create a Work Corrective request and approve it in Mission's existing Work Outcome workflow.">
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
      {chosenFinding ? <><label className="field"><span>Approved Mission decision request</span><select value={selectedProposal} onChange={(event) => setSelectedProposal(event.target.value)}>
        <option value="">Select an approved proposal for this finding</option>{(proposals.data?.proposals ?? []).filter((row) => row.status === "approved" && row.action_category === "REQUEST_USER_DECISION" && row.episode_id === episodeId && (row.finding_ids ?? []).includes(chosenFinding.id)).map((row) => <option key={row.id ?? row.proposal_id} value={row.id ?? row.proposal_id}>{row.objective || row.id || row.proposal_id}</option>)}
      </select></label><button className="button button-ghost" type="button" disabled={!approvedProposal || investigationBusy || integration.data?.mission_to_stephanie?.status !== "available"} onClick={() => void requestStephanieInvestigation()}>{investigationBusy ? "Investigating…" : "Request Stephanie investigation"}</button>
        {!approvedProposal ? <p className="muted small">An approved proposal must include this episode and finding before Stephanie is invoked.</p> : null}</> : null}
    </Section> : null}

    {view === "investigations" ? <Section title="Live Stephanie investigations" description="Stephanie returns source-bound hypotheses. Eligible findings may produce a frozen deterministic fixture candidate; execution still needs a separate human decision and matching Work Envelope.">
      {investigations.loading ? <LoadingBlock compact /> : null}{investigations.error ? <ErrorState message={investigations.error.message} onRetry={investigations.reload} /> : null}
      {investigations.data?.status === "unavailable" ? <EmptyState title="Stephanie investigation interface unavailable" description={integration.data?.mission_to_stephanie?.reason ?? "Configure the allowlisted local CLI and isolated run root."} /> : null}
      {investigations.data?.status === "available" && !investigations.data.investigations.length ? <EmptyState title="No live investigations" description="No completed Mission-sourced investigation is present in Stephanie's configured run root." /> : null}
      {investigations.data?.investigations.map((row) => <button className="list-row" type="button" key={row.investigation_id} aria-pressed={selectedInvestigation === row.investigation_id} onClick={() => setSelectedInvestigation(row.investigation_id)}><span><strong>{row.investigation_id} · {row.result}</strong><small>{row.source_identity} · {row.status}</small></span><Tag>{row.status}</Tag></button>)}
      {activeInvestigation ? <Section title="Investigation evidence" description={`Source ${activeInvestigation.source_identity} · digest ${activeInvestigation.source_digest}`}>
        <p><strong>{activeInvestigation.hypothesis?.statement ?? "No hypothesis returned"}</strong></p><p>{activeInvestigation.hypothesis?.rationale}</p><p className="muted small">Uncertainty: {activeInvestigation.hypothesis?.uncertainty}</p>
        <p>Candidate: {activeInvestigation.candidate ? "Proposed" : "None; additional evidence is required"} · Proposed experiments: {activeInvestigation.proposed_experiments?.length ?? 0} · Retained experience matches: {activeInvestigation.retrieved_experience?.length ?? 0}</p>
        <p className="muted small">{activeInvestigation.authority}</p>
        {investigationDetail.data?.retained_experience ? <Section title="Live retained experience" description={`${investigationDetail.data.retained_experience.source ?? "Stephanie retrieval"} · ${investigationDetail.data.retained_experience.status ?? "status unknown"}`}>
          {(investigationDetail.data.retained_experience.records ?? []).map((row, index) => <div className="list-row" key={`${row.name ?? "experience"}-${index}`}><span><strong>{row.name ?? "Unnamed experience"} · {row.scenario ?? "overall"}</strong><small>{row.outcome ?? "Outcome unavailable"} · reuse eligible {String(row.reuse_eligible ?? "unknown")} · promotion {row.promotion_status ?? "unknown"} · matched terms {row.matched_terms ?? "unknown"}</small></span></div>)}
          {investigationDetail.data.retained_experience.status === "available" && !investigationDetail.data.retained_experience.records?.length ? <p>No matching retained records were found in the live CaseBook.</p> : null}
        </Section> : null}
        {proposedExperiment ? <Section title="Frozen experiment authorization" description={`Candidate ${proposedExperiment.candidate_id} · digest ${proposedExperiment.candidate_digest} · protocol ${proposedExperiment.protocol_digest} · experiment ${proposedExperiment.experiment_id}. Fixture provider only; no model calls; promotion is excluded.`}>
          <label className="field"><span>Mission Work Objective</span><select value={selectedObjective} onChange={(event) => setSelectedObjective(event.target.value)}><option value="">Select objective</option>{(objectives.data?.objectives ?? []).map((row) => <option value={row.id} key={row.id}>{row.text || row.id}</option>)}</select></label>
          <button className="button button-ghost" type="button" disabled={!selectedObjective || experimentBusy} onClick={() => void createExperimentAuthorization()}>{experimentBusy ? "Recording…" : "Request separate experiment decision"}</button>
          {experimentProposalId ? <div className="page-actions"><Link to="/activity?tab=work" className="button button-ghost button-small">Review experiment decision {experimentProposalId}</Link><button className="button button-ghost button-small" type="button" onClick={() => void proposals.reload()}>Refresh approval state</button></div> : null}
          <label className="field"><span>Approved experiment decision</span><select value={selectedAuthorization} onChange={(event) => setSelectedAuthorization(event.target.value)}><option value="">Select approved authorization</option>{authorizationProposals.filter((row) => ["approved", "queued"].includes(row.status ?? "")).map((row) => <option key={row.id ?? row.proposal_id} value={row.id ?? row.proposal_id}>{row.id ?? row.proposal_id} · {row.status === "queued" ? "approved · handed off" : "approved"}</option>)}</select></label>
          {approvedExperimentProposal && !matchingEnvelopes.length ? <button className="button button-ghost" type="button" disabled={experimentBusy || (envelopes.data?.envelopes ?? []).some((row) => row.status === "active" && row.episode_id === activeInvestigation.source_snapshot?.episode_id)} onClick={() => void createAuthorizedEnvelope()}>Register matching Work Envelope</button> : null}
          {approvedExperimentProposal && matchingEnvelopes.length ? <><label className="field"><span>Authorized active Work Envelope</span><select value={selectedEnvelope} onChange={(event) => setSelectedEnvelope(event.target.value)}><option value="">Select matching envelope</option>{matchingEnvelopes.map((row) => <option key={row.id ?? row.envelope_id} value={row.id ?? row.envelope_id}>{row.id ?? row.envelope_id}</option>)}</select></label><button className="button button-primary" type="button" disabled={!selectedEnvelope || experimentBusy} onClick={() => void dispatchAuthorizedExperiment()}>{experimentBusy ? "Dispatching…" : "Execute frozen experiment once"}</button></> : null}
          <p className="muted small">Unknown dispatch outcomes are never retried. A claim or incomplete result requires reconciliation from the Worker execution ledger.</p>
        </Section> : null}
        {investigationDetail.data?.experiment_state === "unknown" ? <p role="status">Experiment execution state is UNKNOWN. Mission will not retry it; reconcile from the authoritative Worker ledger.</p> : null}
        {investigationDetail.data?.experiment_result ? <Section title="Experiment result and retained evaluation" description={investigationDetail.data.experiment_result.qualification ?? "Saved experiment evidence."}>
          <p>Experiment {investigationDetail.data.experiment_result.experiment_id} · formal acceptance {investigationDetail.data.experiment_result.formal_acceptance ?? "UNKNOWN"} · model calls {investigationDetail.data.experiment_result.actual_model_invocations ?? "unknown"}</p>
          {(investigationDetail.data.experiment_result.praxis_comparisons ?? []).map((row) => <div className="list-row" key={row.scenario}><span><strong>{row.scenario}: {row.praxis?.decision ?? "unknown"} · {row.recommendation ?? "no recommendation"}</strong><small>{row.praxis?.rationale ?? "No rationale returned"}</small><small>Baseline invocations {row.resource_comparison?.baseline_invocations ?? "unknown"} · candidate invocations {row.resource_comparison?.candidate_invocations ?? "unknown"} · additional compute {String(row.resource_comparison?.additional_compute ?? "unknown")} · cost {row.resource_comparison?.cost_status ?? "unknown"}</small></span></div>)}
          {(investigationDetail.data.human_decisions ?? []).map((item, index) => <div className="list-row" key={`${item.evidence?.experiment_id ?? "decision"}-${index}`}><span><strong>Human candidate decision: {item.decision ?? "unknown"}</strong><small>Recorded by {item.actor ?? "unknown"} · experiment {item.evidence?.experiment_id ?? "unknown"} · result {item.evidence?.result_digest ?? "unbound"}</small><small>{item.rationale || "No rationale supplied."} Production promotion remains unauthorized.</small></span></div>)}
          {!investigationDetail.data.human_decisions?.length && approvedExperimentProposal ? <>
            <p>A human decision records whether this candidate is accepted for this experiment result. It does not complete the Mission objective or authorize production promotion.</p>
            <label className="field"><span>Human decision maker</span><input value={decisionActor} maxLength={80} onChange={(event) => setDecisionActor(event.target.value)} placeholder="Your name" /></label>
            <label className="field"><span>Decision rationale</span><textarea value={decisionRationale} maxLength={500} onChange={(event) => setDecisionRationale(event.target.value)} placeholder="Optional rationale" /></label>
            <div className="page-actions"><button className="button button-primary" type="button" disabled={!decisionActor.trim() || experimentBusy} onClick={() => void recordHumanOutcomeDecision("accepted")}>Accept candidate result</button><button className="button button-ghost" type="button" disabled={!decisionActor.trim() || experimentBusy} onClick={() => void recordHumanOutcomeDecision("rejected")}>Reject candidate result</button></div>
          </> : null}
          <p className="muted small">Execution completion, independent evaluation, Praxis recommendation, human acceptance, objective completion, and production promotion remain separate states.</p>
        </Section> : null}
      </Section> : null}
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
        <ul className="plain-list"><li>AI: shared inference foundation, consumed by Stephanie.</li><li>Stephanie: allowlisted local CLI for deterministic investigations and its existing SC3 experiment coordination; an isolated run root must be configured.</li><li>Worker: existing SC3 runtime; dispatch requires separate exact-scope Mission approval and its bound active Work Envelope.</li><li>Praxis: Stephanie-owned independent comparison after Worker fixture execution.</li><li>Mission: Work Outcome, corrective proposals, Work Envelopes, evaluation and human decisions.</li></ul>
      </Section>
      <Section title="Qualification limits" description="SC3 established deterministic integration, not operational effectiveness.">
        <ul className="plain-list"><li>Genuine Worker comparison: one pair; Praxis returned insufficient evidence.</li><li>No production promotion or automated acceptance.</li><li>Model cost, provider semantics and broader hypothesis quality remain unqualified.</li><li>Mission operational backend must pass its activation gate before these views can be used live.</li></ul>
      </Section>
    </div> : null}
  </div>;
}
