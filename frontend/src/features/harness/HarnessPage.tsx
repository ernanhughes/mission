import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, apiPath, ApiError, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, ErrorState, InlineError, LoadingBlock, PageHeader, Section, Tag } from "../../components/ui";

type Strategy = { key: string; id: string; version: string; digest: string; maximum_model_invocations: number; internal_validation: string; correction: string; supported_backends?: string[]; behavior?: string; resource_controls?: Record<string, string | number>; known_limitations?: string[]; availability?: string; qualification?: string };
type ModelRoute = { id: string; model: string; economic_tier: string; data_policy: string; health?: string; verification?: string };
type Catalogue = { worker: { reachable: boolean; status: string; version: string; base_url: string }; strategies: Strategy[]; models: ModelRoute[]; policies: Record<string, { routes: string[]; required_data_policy?: string; attempts_per_route?: number }>; limits: Record<string, unknown>; qualification_note: string };
type Execution = { request_id: string; task_id?: string | null; episode_id?: string | null; mission_correlation?: { status: string; episode_id?: string; objective_id?: string; project_key?: string; reason?: string }; result_status?: string | null; created_at?: string; strategy_execution?: Record<string, any>; requested?: Record<string, any>; resolved?: Record<string, any>; trace?: Record<string, any>; output_digest?: string | null; [key: string]: any };
type Episode = { id: string; title: string; project_key: string; status: string };
type Objective = { id: string; episode_id: string; text: string; authority: string; status: string; version: number };
type WorkResult = { request_id: string; status: string; output?: unknown; strategy_execution?: Record<string, any>; message?: string; execution?: Record<string, any> };

const TABS = ["Overview", "Strategies", "Execute", "Executions", "Decisions", "Experiments"] as const;
type Tab = (typeof TABS)[number];

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unknown";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function StrategyCards({ strategies, executions }: { strategies: Strategy[]; executions: Execution[] }) {
  if (!strategies.length) return <EmptyState title="No Worker strategies available" description="Mission could not load strategy metadata from Worker." />;
  return <div className="harness-card-grid">{strategies.map((strategy) => {
    const related = executions.filter((row) => row.strategy_execution?.strategy?.key === strategy.key);
    return <article className="harness-card" key={strategy.key}>
      <div className="harness-card-head"><h3>{strategy.key}</h3><Tag>{strategy.qualification ?? "qualification unknown"}</Tag></div>
      <p>{strategy.behavior ?? "Behavior metadata unavailable from Worker."}</p>
      <dl><div><dt>Maximum calls</dt><dd>{strategy.maximum_model_invocations}</dd></div><div><dt>Internal validation</dt><dd>{strategy.internal_validation}</dd></div><div><dt>Correction</dt><dd>{strategy.correction}</dd></div><div><dt>Engine</dt><dd>{strategy.supported_backends?.join(", ") || "Unknown"}</dd></div><div><dt>Observed executions in current ledger window</dt><dd>{related.length}</dd></div></dl>
      <p className="muted small">Worker strategy digest: <code>{strategy.digest}</code></p>
      <ul>{(strategy.known_limitations ?? []).map((item) => <li key={item}>{item}</li>)}</ul>
    </article>;
  })}</div>;
}

function ExecutionRows({ rows, onSelect }: { rows: Execution[]; onSelect: (row: Execution) => void }) {
  if (!rows.length) return <EmptyState title="No executions in this Worker ledger window" description="Unavailable history is not reported as zero execution activity." />;
  return <div className="table-scroll"><table className="data-table"><thead><tr><th>Worker request</th><th>Episode</th><th>Strategy</th><th>Execution</th><th>Evaluation</th><th>Acceptance</th></tr></thead><tbody>
    {rows.map((row) => { const evidence = row.strategy_execution ?? {}; const strategy = evidence.strategy?.key ?? row.strategy_identity?.key ?? "Unknown"; return <tr key={row.request_id}>
      <td><button className="button button-ghost button-small" onClick={() => onSelect(row)}>{row.request_id}</button><small>{row.task_id ?? "task unknown"}</small></td>
      <td>{row.mission_correlation?.status === "verified" ? row.mission_correlation.episode_id : "Unmatched"}</td><td>{strategy}</td><td>{row.result_status ?? "Unknown"}</td><td>Not established by execution record</td><td>{row.result_status === "AWAITING_ACCEPTANCE" ? "Awaiting acceptance" : "Unknown"}</td>
    </tr>; })}
  </tbody></table></div>;
}

export function HarnessPage({ projectKey }: { projectKey?: string } = {}) {
  const [search, setSearch] = useSearchParams();
  const scopedProjectKey = projectKey ?? search.get("project_key") ?? undefined;
  const tab = (TABS.find((candidate) => candidate.toLowerCase() === (search.get("tab") ?? "overview").toLowerCase()) ?? "Overview") as Tab;
  const catalogue = useApi<Catalogue>("/api/harness/catalogue");
  const executionPath = apiPath("/api/harness/executions", { project_key: scopedProjectKey, limit: 100 });
  const executions = useApi<{ executions: Execution[]; coverage: { source: string; read_window: number; truncated: boolean } }>(executionPath, { pollMs: 5000 });
  const activeJobs = useApi<{ jobs: Array<Record<string, any>>; cancellation: string }>("/api/harness/jobs", { pollMs: 2000 });
  const episodes = useApi<{ episodes: Episode[] }>(apiPath("/api/work-episodes", { project_key: scopedProjectKey, limit: 100 }));
  const [episodeId, setEpisodeId] = useState("");
  const objectives = useApi<{ objectives: Objective[] }>(episodeId ? apiPath("/api/work-intent/objectives", { episode_id: episodeId }) : null);
  const [objectiveId, setObjectiveId] = useState("");
  const [strategyId, setStrategyId] = useState("adaptive.v1");
  const [routeId, setRouteId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [actor, setActor] = useState("");
  const [authorizationNote, setAuthorizationNote] = useState("");
  const [timeoutMs, setTimeoutMs] = useState(30000);
  const [outputTokens, setOutputTokens] = useState(256);
  const [selectedExecution, setSelectedExecution] = useState<Execution | null>(null);
  const verifiedEpisodeId = selectedExecution?.mission_correlation?.status === "verified" ? selectedExecution.mission_correlation.episode_id : undefined;
  const selectedEvaluation = useApi<Record<string, any>>(verifiedEpisodeId ? apiPath(`/api/work-evaluation/episodes/${encodeURIComponent(verifiedEpisodeId)}`) : null);
  const selectedEpisode = useApi<Record<string, any>>(verifiedEpisodeId ? apiPath(`/api/work-episodes/${encodeURIComponent(verifiedEpisodeId)}`) : null);
  const selectedArtifacts = useApi<Record<string, any>>(selectedExecution?.request_id ? `/api/harness/executions/${encodeURIComponent(selectedExecution.request_id)}/artifacts` : null);
  const [launchResult, setLaunchResult] = useState<WorkResult | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [submissionInDoubt, setSubmissionInDoubt] = useState(false);
  const [submissionId, setSubmissionId] = useState("");
  const [launching, setLaunching] = useState(false);

  useEffect(() => { if (!episodeId && episodes.data?.episodes.length) setEpisodeId(episodes.data.episodes[0].id); }, [episodeId, episodes.data]);
  useEffect(() => { setObjectiveId(objectives.data?.objectives[0]?.id ?? ""); }, [objectives.data]);
  const selectedObjective = objectives.data?.objectives.find((row) => row.id === objectiveId);
  const selectedStrategy = catalogue.data?.strategies.find((row) => row.key === strategyId);
  const safeRoutes = useMemo(() => (catalogue.data?.models ?? []).filter((row) => row.economic_tier === "free" && row.data_policy === "local_only"), [catalogue.data]);
  const eligiblePolicies = useMemo(() => Object.entries(catalogue.data?.policies ?? {}).filter(([, policy]) => policy.routes.includes(routeId) && policy.required_data_policy === "local_only" && Number(policy.attempts_per_route) <= 2), [catalogue.data, routeId]);
  useEffect(() => { if (!safeRoutes.some((route) => route.id === routeId)) setRouteId(safeRoutes[0]?.id ?? ""); }, [safeRoutes, routeId]);
  useEffect(() => { if (!eligiblePolicies.some(([id]) => id === policyId)) setPolicyId(eligiblePolicies[0]?.[0] ?? ""); }, [eligiblePolicies, policyId]);

  const rows = executions.data?.executions ?? [];
  const decisions = rows.flatMap((row) => {
    const evidence = row.strategy_execution ?? {};
    const items = evidence.validation?.decisions ?? [];
    return items.map((decision: Record<string, any>, index: number) => ({ row, decision, index }));
  });
  const comparisons = useMemo(() => {
    const groups = new Map<string, Execution[]>();
    for (const row of rows) {
      const requested = row.requested ?? {};
      const model = row.resolved?.configuration?.resolved_model_route ?? row.resolved?.resolved_model_route ?? "unknown";
      const conditions = { backend: requested.backend ?? requested.engine ?? null, policy: requested.policy ?? null,
        timeout_ms: requested.timeout_ms ?? null, max_output_tokens: requested.max_output_tokens ?? null,
        data_policy: requested.data_policy ?? null, temperature: requested.temperature ?? null,
        reasoning_effort: requested.reasoning_effort ?? null,
        selected_executor: row.resolved?.selected_executor ?? null, model };
      const identity = row.mission_correlation?.status === "verified"
        ? `${row.mission_correlation.episode_id}::${row.mission_correlation.objective_id}` : row.request_id;
      const key = `${identity}::${JSON.stringify(conditions)}`;
      groups.set(key, [...(groups.get(key) ?? []), row]);
    }
    return [...groups.entries()].map(([key, values]) => ({ key, values,
      comparable: values.every((row) => row.mission_correlation?.status === "verified"
        && row.requested?.timeout_ms != null && row.requested?.max_output_tokens != null
        && row.requested?.policy != null && row.requested?.data_policy != null
        && row.requested?.temperature != null && row.requested?.reasoning_effort != null
        && (row.requested?.backend ?? row.requested?.engine) != null
        && (row.resolved?.selected_executor != null) && (row.resolved?.resolved_model_route != null))
        && new Set(values.map((row) => row.strategy_execution?.strategy?.key ?? row.resolved?.strategy_identity?.key).filter(Boolean)).size > 1 }));
  }, [rows]);

  function selectTab(next: Tab) {
    setSearch((previous) => { const updated = new URLSearchParams(previous); if (next === "Overview") updated.delete("tab"); else updated.set("tab", next.toLowerCase()); return updated; });
  }

  async function launch(event: FormEvent) {
    event.preventDefault(); setLaunchError(null); setLaunching(true); setLaunchResult(null);
    if (submissionInDoubt) { setLaunchError("A previous submission has an unknown outcome. Inspect the Worker ledger before starting another execution."); setLaunching(false); return; }
    if (!selectedObjective || !selectedStrategy || !routeId || !policyId) { setLaunchError("Choose an existing Work Outcome objective, Worker strategy, and eligible local route."); setLaunching(false); return; }
    const activeSubmissionId = submissionId || window.crypto?.randomUUID?.() || `h6-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setSubmissionId(activeSubmissionId);
    const request = { episode_id: episodeId, objective_id: objectiveId, strategy_id: strategyId, model_route: routeId, policy: policyId,
      ...(strategyId === "adaptive.v1" ? { normalization_policy: "json-fence.v1" } : {}), timeout_ms: timeoutMs, max_output_tokens: outputTokens,
      actor, authorization_note: authorizationNote, submission_id: activeSubmissionId,
      ...(scopedProjectKey ? { project_key: scopedProjectKey } : {}) };
    try {
      if (!window.confirm(`Submit this bounded task to Worker?\n\nStrategy: ${strategyId}\nRoute: ${routeId}\nPolicy: ${policyId}\nMaximum time: ${timeoutMs} ms\nRequested output cap: ${outputTokens} tokens per call\nMaximum calls: ${selectedStrategy.maximum_model_invocations}\n\nNo workspace, filesystem, network, or external tools are attached. Provider inference and remote termination may remain unknown.`)) return;
      const response = await api.post<{ worker_result: WorkResult }>("/api/harness/executions", request);
      setLaunchResult(response.worker_result); setSubmissionId(""); executions.reload();
    } catch (caught) {
      setLaunchError(errorMessage(caught)); executions.reload();
      if (!(caught instanceof ApiError) || caught.status === 0 || caught.status >= 500 || caught.status === 409) setSubmissionInDoubt(true);
      else setSubmissionId("");
    }
    finally { setLaunching(false); }
  }

  return <div className="page harness-page">
    <PageHeader eyebrow={scopedProjectKey ? `Project · ${scopedProjectKey}` : "Worker integration"} title="Harness" description="Mission authorizes bounded Worker runs. Worker remains authoritative for strategy execution and the H3 execution ledger." actions={<Link className="button button-ghost button-small" to="/activity?tab=work">Work Outcome</Link>} />
    <div className="harness-tabs" role="tablist" aria-label="Harness sections">{TABS.map((name) => <button key={name} role="tab" aria-selected={tab === name} className={`button button-small ${tab === name ? "button-secondary" : "button-ghost"}`} onClick={() => selectTab(name)}>{name}</button>)}</div>
    {catalogue.loading && !catalogue.data ? <LoadingBlock label="Connecting to Worker and loading strategy metadata" /> : null}
    {catalogue.error && !catalogue.data ? <ErrorState message={catalogue.error.message} onRetry={catalogue.reload} /> : null}
    {catalogue.data ? <p className="harness-connectivity"><Tag tone={catalogue.data.worker.reachable ? "accent" : "danger"}>Worker {catalogue.data.worker.status}</Tag><span>Version {catalogue.data.worker.version} · {catalogue.data.worker.base_url}</span><span>{catalogue.data.qualification_note}</span></p> : null}
    {executions.error && !executions.data ? <ErrorState message={executions.error.message} onRetry={executions.reload} /> : null}
    {tab === "Overview" ? <>
      <div className="harness-stats"><div><span>Worker strategies</span><strong>{catalogue.data?.strategies.length ?? "Unavailable"}</strong></div><div><span>H3 records in current read window</span><strong>{executions.data?.coverage.read_window ?? "Unavailable"}</strong></div><div><span>Unaccepted results in window</span><strong>{executions.data ? rows.filter((row) => row.result_status === "AWAITING_ACCEPTANCE").length : "Unavailable"}</strong></div><div><span>Telemetry coverage</span><strong>{rows.length ? "Per-record; cost may be unknown" : executions.data ? "No rows in window" : "Unavailable"}</strong></div></div>
      <Section title="Recent Worker executions" description="Source: Worker H3 execution ledger, latest bounded read window. Synthetic and live runs are not mixed into this operational list."><ExecutionRows rows={rows.slice(-10).reverse()} onSelect={setSelectedExecution} /></Section>
      <Section title="Current Worker jobs" description="Read-only Worker job state. This integration does not imply cancellation or remote inference termination.">{activeJobs.error ? <InlineError message={activeJobs.error.message} /> : activeJobs.data?.jobs.length ? <pre className="harness-output">{display(activeJobs.data.jobs)}</pre> : activeJobs.data ? <p>No active jobs observed.</p> : <p>Job state unavailable.</p>}</Section>
      <Section title="Known limits"><ul><li>Strategy catalogue availability is not qualification.</li><li>Worker execution completion, independent Work Outcome evaluation, objective achievement and acceptance remain distinct.</li><li>Provider inference, token-cap enforcement, billed cost and remote termination may be unknown.</li><li>History only covers the Worker ledger read window; unavailable ledger data is not zero.</li></ul></Section>
    </> : null}
    {tab === "Strategies" ? <Section title="Worker strategy catalogue" description="Behavior and invocation bounds are returned by Worker. Qualification is not inferred from listing.">{catalogue.data ? <StrategyCards strategies={catalogue.data.strategies} executions={rows} /> : null}</Section> : null}
    {tab === "Execute" ? <Section title="Authorize a bounded Work Outcome task" description="Select an existing episode objective. Mission records an explicit Work Envelope before dispatch; Worker executes the selected versioned strategy. No code, filesystem, network, or external tools are attached.">
      {episodes.loading ? <LoadingBlock label="Loading Work Outcome episodes" compact /> : null}{episodes.error ? <InlineError message={episodes.error.message} /> : null}
      <form className="form-stack" onSubmit={(event) => void launch(event)}>
        <div className="form-grid two">
          <label className="field"><span>Work episode</span><select value={episodeId} onChange={(event) => setEpisodeId(event.target.value)}><option value="">Select an episode</option>{(episodes.data?.episodes ?? []).map((row) => <option key={row.id} value={row.id}>{row.title} · {row.project_key} · {row.id}</option>)}</select></label>
          <label className="field"><span>Objective</span><select value={objectiveId} onChange={(event) => setObjectiveId(event.target.value)} disabled={!episodeId}><option value="">Select an objective</option>{(objectives.data?.objectives ?? []).map((row) => <option key={row.id} value={row.id}>{row.text.slice(0, 180)} · {row.status}</option>)}</select></label>
          <label className="field"><span>Strategy</span><select value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>{(catalogue.data?.strategies ?? []).map((row) => <option key={row.key} value={row.key}>{row.key} · max {row.maximum_model_invocations} calls</option>)}</select></label>
          <label className="field"><span>Configured local-only route</span><select value={routeId} onChange={(event) => setRouteId(event.target.value)}><option value="">Select a configured free local-only route</option>{safeRoutes.map((row) => <option key={row.id} value={row.id}>{row.id} · {row.model} · health {row.health ?? "unknown"}</option>)}</select></label>
          <label className="field"><span>Policy</span><select value={policyId} onChange={(event) => setPolicyId(event.target.value)}><option value="">Select a route-compatible policy</option>{eligiblePolicies.map(([id, policy]) => <option key={id} value={id}>{id} · {policy.attempts_per_route} attempt(s)</option>)}</select></label>
          <label className="field"><span>Timeout (ms, max 60000)</span><input type="number" min={1000} max={60000} step={1000} value={timeoutMs} onChange={(event) => setTimeoutMs(Math.min(60000, Math.max(1000, Number(event.target.value))))} /></label>
          <label className="field"><span>Requested output cap per call (max 2048)</span><input type="number" min={1} max={2048} value={outputTokens} onChange={(event) => setOutputTokens(Math.min(2048, Math.max(1, Number(event.target.value))))} /></label>
          <label className="field"><span>Human actor</span><input required minLength={2} maxLength={80} value={actor} onChange={(event) => setActor(event.target.value)} placeholder="Your name or operator identity" /></label>
          <label className="field"><span>Authorization note</span><input required minLength={8} maxLength={200} value={authorizationNote} onChange={(event) => setAuthorizationNote(event.target.value)} placeholder="Why is this bounded task authorized?" /></label>
        </div>
        {selectedObjective ? <div className="harness-preview"><strong>Request preview</strong><p>{selectedObjective.text}</p><small>Episode {episodeId} · objective {objectiveId} v{selectedObjective.version} · no workspace or tool permissions · acceptance remains separate</small></div> : <EmptyState title="Select an episode objective" description="Mission will not accept caller-provided objective text." />}
        <InlineError message={launchError} />
        {submissionInDoubt ? <p role="status">Do not resubmit this task. Refresh Worker execution history and verify whether the request reached Worker.</p> : null}
        <button className="button button-primary" type="submit" disabled={launching || submissionInDoubt || !selectedObjective || !routeId || !policyId}>{launching ? "Worker execution in progress…" : submissionInDoubt ? "Submission outcome unknown" : "Review and authorize execution"}</button>
      </form>
      {launchResult ? <Section title="Latest response"><p>Worker result: <Tag>{launchResult.status}</Tag> · request {launchResult.request_id}</p><pre className="harness-output">{display(launchResult.output)}</pre><p>Independent evaluation is not inferred from this response. Acceptance is not automatic.</p></Section> : null}
    </Section> : null}
    {tab === "Executions" ? <Section title={scopedProjectKey ? `Project executions · ${scopedProjectKey}` : "Worker execution history"} description="Read-only projection of the Worker H3 execution ledger. Select a row to inspect its linked strategy evidence."><ExecutionRows rows={[...rows].reverse()} onSelect={setSelectedExecution} />{executions.data?.coverage.truncated ? <p className="muted small">Worker reports additional records outside this read window.</p> : null}</Section> : null}
    {tab === "Decisions" ? <Section title="Harness decisions" description="Decisions are projected from Worker strategy evidence; a selected action is not assumed successful.">{decisions.length ? decisions.map(({ row, decision, index }) => <article className="harness-decision" key={`${row.request_id}-${index}`}><h3>{decision.selected_action ?? "Unknown action"} <Tag>{decision.outcome ?? "outcome unknown"}</Tag></h3><dl><div><dt>Observed state</dt><dd>{display(decision.observed_state)}</dd></div><div><dt>Eligible actions</dt><dd>{display(decision.eligible_actions)}</dd></div><div><dt>Rationale</dt><dd>{display(decision.rationale)}</dd></div><div><dt>Attribution</dt><dd>{display(row.strategy_execution?.validation?.attribution)}</dd></div><div><dt>Remaining resources</dt><dd>{display(decision.remaining_resources)}</dd></div><div><dt>Request</dt><dd>{row.request_id} · {row.mission_correlation?.status === "verified" ? row.mission_correlation.episode_id : "Worker episode unverified"}</dd></div></dl></article>) : <EmptyState title="No decision records in this window" description={executions.data ? "No adaptive decisions were recorded. The ledger window may not include historical fixture bundles." : "Worker ledger is unavailable."} />}</Section> : null}
    {tab === "Experiments" ? <Section title="Comparable executions" description="Groups match task, route, backend, policy, timeout, output cap, data policy, temperature and reasoning effort. A strategy comparison is shown only when more than one strategy is present; no ranking or effectiveness claim is generated.">{comparisons.length ? comparisons.map((group) => <article className="harness-decision" key={group.key}><h3>{group.comparable ? "Matched execution conditions across strategies" : "Repeated or unmatched execution; comparison not established"} <Tag>{group.values.length} record(s)</Tag></h3><p>{group.key}</p><ExecutionRows rows={group.values} onSelect={setSelectedExecution} /></article>) : <EmptyState title="No comparison records available" description="Comparable evidence requires the same task and execution conditions across distinct strategies." />}</Section> : null}
    {selectedExecution ? <div className="harness-detail-overlay" role="dialog" aria-modal="true" aria-label="Execution detail"><div className="harness-detail"><div className="harness-card-head"><h2>Execution {selectedExecution.request_id}</h2><button className="button button-ghost" onClick={() => setSelectedExecution(null)}>Close</button></div><p>Mission Work Envelope correlation: {selectedExecution.mission_correlation?.status === "verified" ? `${selectedExecution.mission_correlation.episode_id} · objective ${selectedExecution.mission_correlation.objective_id}` : `unmatched · ${selectedExecution.mission_correlation?.reason ?? "Worker episode identity is caller supplied and unverified"}`}</p><p>Worker supplied episode: {selectedExecution.episode_id ?? "absent"} · task: {selectedExecution.task_id ?? "Unknown"} · source status: {display(selectedExecution.episode_link)}</p><div className="harness-detail-grid"><section><h3>Request and identity</h3><pre>{display({ requested: selectedExecution.requested, resolved: selectedExecution.resolved })}</pre></section><section><h3>Timeline and trace</h3><pre>{display(selectedExecution.trace)}</pre></section><section><h3>Invocations and decisions</h3><pre>{display(selectedExecution.strategy_execution)}</pre></section><section><h3>Original and transformed artifacts</h3>{selectedArtifacts.loading ? <LoadingBlock compact /> : selectedArtifacts.data?.available ? <><h4>Final output</h4><pre>{display(selectedArtifacts.data.output)}</pre><h4>Raw invocation output</h4><pre>{display(selectedArtifacts.data.strategy_execution?.invocations?.map((call: Record<string, any>) => ({ invocation_id: call.invocation_id, output: call.output, output_digest: call.output_digest })))}</pre><h4>Normalized artifact</h4><pre>{display(selectedArtifacts.data.strategy_execution?.normalized_artifact ?? "No normalized artifact recorded")}</pre><p className="muted small">{selectedArtifacts.data.artifact_retention}</p></> : selectedArtifacts.data ? <p>{selectedArtifacts.data.reason}</p> : selectedArtifacts.error ? <InlineError message={selectedArtifacts.error.message} /> : <p>Artifact state unavailable.</p>}<pre>{display({ output_digest: selectedExecution.output_digest, output_budget: selectedExecution.resolved?.output_budget, timeout_budget: selectedExecution.resolved?.timeout_budget })}</pre></section><section><h3>Independent Work Outcome evaluation</h3>{verifiedEpisodeId ? selectedEvaluation.loading ? <LoadingBlock compact /> : selectedEvaluation.data ? <pre>{display(selectedEvaluation.data)}</pre> : selectedEvaluation.error?.status === 404 ? <p>No independent evaluation is recorded for this episode.</p> : selectedEvaluation.error ? <InlineError message={selectedEvaluation.error.message} /> : <p>Evaluation unavailable.</p> : <p>Evaluation withheld because Mission could not verify the Worker identity against a Work Envelope.</p>}{verifiedEpisodeId ? <Link to={`/activity?tab=work&episode_id=${encodeURIComponent(verifiedEpisodeId)}`}>Open Work Evaluation</Link> : null}</section><section><h3>Episode outcome and acceptance</h3>{!verifiedEpisodeId ? <p>Episode is unmatched or unavailable.</p> : selectedEpisode.loading ? <LoadingBlock compact /> : selectedEpisode.data ? <pre>{display({ status: selectedEpisode.data.status, outcome_status: selectedEpisode.data.outcome_status, completion_verdict: selectedEpisode.data.completion_verdict, evaluator: selectedEpisode.data.evaluator })}</pre> : <p>Episode is unavailable.</p>}<p>Execution, evaluation, objective achievement, task acceptance, and strategy promotion are separate decisions. This integration does not automatically accept or promote.</p></section></div></div></div> : null}
  </div>;
}

export function ProjectHarnessPanel({ projectKey }: { projectKey: string }) {
  const rows = useApi<{ executions: Execution[]; coverage: { read_window: number; truncated: boolean } }>(apiPath("/api/harness/executions", { project_key: projectKey, limit: 100 }));
  return <Section title="Harness executions" description="Exact match on Work Outcome project_key. If Mission's project ID does not equal that key, no relationship is inferred. The same Worker H3 ledger is used; there is no project-specific execution store."><p><Link className="button button-ghost button-small" to={`/harness?tab=executions&project_key=${encodeURIComponent(projectKey)}`}>Open project Harness history</Link></p>{rows.loading ? <LoadingBlock compact /> : null}{rows.error ? <ErrorState message={rows.error.message} onRetry={rows.reload} /> : null}{rows.data ? <ExecutionRows rows={[...rows.data.executions].reverse()} onSelect={() => window.location.assign(`/harness?tab=executions&project_key=${encodeURIComponent(projectKey)}`)} /> : null}</Section>;
}
