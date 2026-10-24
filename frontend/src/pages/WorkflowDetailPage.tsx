import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleSlash,
  ExternalLink,
  Play,
  RefreshCw,
  ShieldCheck,
  Telescope,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PathText,
  ProvenanceBadge,
  Section,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import { formatDateTime, timeAgo, titleCase, truncate } from "../lib/format";
import type { ExperimentWorkflow } from "../types/api";

function statusState(status: string): string {
  if (status === "decided") return "running";
  if (status === "failed" || status === "review_failed") return "launch_failed";
  if (status === "cancelled") return "cancelled";
  if (status === "executing" || status === "reviewing") return "in_progress";
  if (status === "approved") return "accepted";
  return "pending";
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="workflow-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function WorkflowDetailPage() {
  const { workflowId = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const workflow = useApi<ExperimentWorkflow>(`/api/workflows/${workflowId}`, { pollMs: 3000 });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scopeAcknowledged, setScopeAcknowledged] = useState(false);
  const [reason, setReason] = useState("");
  const [overrideAdverse, setOverrideAdverse] = useState(false);

  useEffect(() => {
    setScopeAcknowledged(false);
    setReason("");
    setOverrideAdverse(false);
    setError(null);
  }, [workflowId]);

  const data = workflow.data;
  const proposal = data?.proposal ?? {};
  const measurement = data?.measurement ?? {};
  const review = data?.review_summary ?? {};
  const evidence = data?.next_evidence?.opportunity ?? {};
  const isFixture =
    String(data?.next_evidence?.source_kind || "next") === "fixture" ||
    data?.template === "brightness_observation_v1";
  const canApprove = data?.status === "proposed";
  const canExecute = data?.status === "approved";
  const canDecide = Boolean(
    data && ["reviewed", "review_failed", "executed", "failed"].includes(data.status) && !data.final_decision,
  );
  const testsPassed = Boolean(measurement.passed);
  const reviewAvailable = Boolean(data?.review_summary?.available);
  const canAccept = testsPassed && reviewAvailable && (!data?.adverse_review || overrideAdverse);
  const timeline = useMemo(
    () => [...(data?.events ?? [])].sort((a, b) => a.sequence - b.sequence),
    [data?.events],
  );

  async function run(label: string, operation: () => Promise<unknown>, success: string) {
    setBusy(label);
    setError(null);
    try {
      await operation();
      toast.push("success", success);
      workflow.reload();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", success + " failed", message);
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!data) return;
    if (!scopeAcknowledged) {
      setError("Acknowledge the exact file scope before approving.");
      return;
    }
    await run(
      "approve",
      () =>
        api.post(`/api/workflows/${data.id}/approve`, {
          confirm: true,
          approved_by: "user",
          scope_acknowledged: true,
        }),
      "Workflow approved",
    );
  }

  async function execute() {
    if (!data) return;
    if (!window.confirm(`Execute the approved experiment?\n\nRepository: ${data.repository_path}\nScope: ${(data.approved_scope || []).join(", ")}\nModel: ${proposal.worker?.model}`)) {
      return;
    }
    await run(
      "execute",
      () => api.post(`/api/workflows/${data.id}/execute`, { confirm: true }),
      "Experiment executed",
    );
  }

  async function cancel() {
    if (!data) return;
    if (!window.confirm("Request cancellation at the next safe boundary? No result will be adopted.")) {
      return;
    }
    await run(
      "cancel",
      () => api.post(`/api/workflows/${data.id}/cancel`, { reason: "Cancelled by the user" }),
      "Cancellation recorded",
    );
  }

  async function decide(decision: "accept" | "reject" | "investigate") {
    if (!data) return;
    if (decision === "accept" && data.adverse_review && !overrideAdverse) {
      setError("CoCoder reported high/medium findings. Tick the explicit override before accepting.");
      return;
    }
    await run(
      `decision-${decision}`,
      () =>
        api.post(`/api/workflows/${data.id}/decision`, {
          decision,
          reason,
          override_adverse: decision === "accept" && overrideAdverse,
        }),
      `Decision recorded: ${decision}`,
    );
  }

  async function retry() {
    if (!data) return;
    setBusy("retry");
    setError(null);
    try {
      const created = await api.post<ExperimentWorkflow>("/api/workflows", {
        record_id: data.next_record_id,
        template: data.template,
        force_new: true,
      });
      toast.push("success", "New experiment workflow created");
      navigate(`/workflows/${created.id}`);
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not create a new workflow", message);
    } finally {
      setBusy(null);
    }
  }

  if (workflow.loading && !data) {
    return <div className="page"><LoadingBlock label="Opening experiment trace" /></div>;
  }
  if (workflow.error) {
    return <div className="page"><ErrorState message={workflow.error.message} onRetry={workflow.reload} /></div>;
  }
  if (!data) return null;

  return (
    <div className="page workflow-detail-page">
      <Link className="back-link" to="/workflows"><ArrowLeft size={14} /> All experiments</Link>
      <PageHeader
        eyebrow={`MC10 experiment · ${data.template}`}
        title={data.title}
        description={
          isFixture
            ? "One durable trace from local fixture evidence through approval, Worker execution, CoCoder review and the human decision."
            : "One durable trace from Next evidence through approval, Worker execution, CoCoder review and the human decision."
        }
        actions={
          <>
            <SimpleStatusBadge state={statusState(data.status)} label={titleCase(data.status)} />
            {["proposed", "approved", "executing", "reviewing"].includes(data.status) || busy === "execute" ? (
              <button className="button button-danger" onClick={() => void cancel()} disabled={busy === "cancel"}>
                <CircleSlash size={15} /> {busy === "cancel" ? "Cancelling…" : "Cancel"}
              </button>
            ) : null}
            {data.next_record_id ? (
              <Link className="button button-secondary" to={`/next?record=${data.next_record_id}`}>
                <Telescope size={15} /> Open Next evidence
              </Link>
            ) : null}
            {["failed", "review_failed"].includes(data.status) ? (
              <button className="button button-primary" onClick={() => void retry()} disabled={busy !== null}>
                <RefreshCw size={15} /> New attempt
              </button>
            ) : null}
          </>
        }
      />
      <InlineError message={error} />

      <div className="workflow-status-strip">
        <Metric label="Worker" value={data.worker_status || "not run"} detail={data.worker_request_id || "No request"} />
        <Metric
          label="Tests"
          value={measurement.passed ? "Passed" : measurement.tests ? "Failed" : "Not run"}
          detail={measurement.comparison?.after_reduced_events != null ? `${measurement.comparison.after_reduced_events} reduced events` : undefined}
        />
        <Metric
          label="CoCoder"
          value={data.review_summary?.available ? `${data.review_summary.findings ?? 0} findings` : "Not reviewed"}
          detail={data.adverse_review ? "Adverse: high/medium findings" : "No adverse finding"}
        />
        <Metric label="Decision" value={data.final_decision || "Pending"} detail={data.final_reason || "Human decision required"} />
      </div>

      {data.failure ? (
        <div className="workflow-failure"><AlertTriangle size={18} /><div><strong>Workflow failure</strong><p>{data.failure}</p></div></div>
      ) : null}

      <div className="workflow-grid">
        <div className="workflow-column">
          <Section
            title={isFixture ? "Fixture evidence" : "Original research evidence"}
            description={
              isFixture
                ? "Preserved from the local fixture manifest; Mission Control did not rewrite it."
                : "Preserved from Next's versioned export; Mission Control did not rewrite it."
            }
          >
            <div className="workflow-evidence">
              <span className="eyebrow">{isFixture ? "Local fixture" : "Next candidate"}</span>
              <h3>{data.next_title}</h3>
              <p>{truncate(String(evidence.what_discovered || ""), 700)}</p>
              <dl className="kv-list">
                <KeyValue label="External ID"><code>{data.next_external_id}</code></KeyValue>
                <KeyValue label="Export schema">{String(data.next_evidence.schema || "unknown")}</KeyValue>
                <KeyValue label="Exported">{data.next_evidence.generated_at ? formatDateTime(String(data.next_evidence.generated_at)) : "unknown"}</KeyValue>
                <KeyValue label="Evaluation">{String(evidence.evaluation_basis || "not stated")}</KeyValue>
                <KeyValue label="Evidence">{String(evidence.evidence || "not stated")}</KeyValue>
                <KeyValue label="Proposed experiment">{String(evidence.simplest_experiment || "not stated")}</KeyValue>
                <KeyValue label="Falsification">{String(evidence.falsification || "not stated")}</KeyValue>
              </dl>
              {evidence.items?.length ? (
                <div className="workflow-source-items">
                  {evidence.items.map((item: Record<string, unknown>, index: number) => (
                    <div key={`${item.id || index}`}>
                      <strong>{String(item.title || item.id)}</strong>
                      {item.url ? <a href={String(item.url)} target="_blank" rel="noreferrer">{String(item.source || "source")} <ExternalLink size={11} /></a> : null}
                    </div>
                  ))}
                </div>
              ) : null}
              <PathText>{String(data.next_evidence.export_path || "")}</PathText>
            </div>
          </Section>

          <Section title="Proposal and approval" description="The exact scope, budget, stop conditions and approval hash.">
            <div className="workflow-proposal">
              <p><strong>Objective.</strong> {String(proposal.objective || "")}</p>
              <div className="workflow-scope">
                <span className="eyebrow">Approved file scope</span>
                {(proposal.scope || []).map((item: string) => <Tag tone="accent" key={item}>{item}</Tag>)}
              </div>
              <dl className="kv-list">
                <KeyValue label="Repository"><PathText>{data.repository_path}</PathText></KeyValue>
                <KeyValue label="Baseline commit"><code>{data.baseline_commit}</code></KeyValue>
                <KeyValue label="Worker">{String(proposal.worker?.backend)} / {String(proposal.worker?.model)}</KeyValue>
                <KeyValue label="Budget">{String(proposal.worker?.max_model_calls)} model call · {String(proposal.worker?.timeout_seconds)}s</KeyValue>
                <KeyValue label="Expected result">{String(proposal.expected_result || "")}</KeyValue>
                <KeyValue label="Approval">
                  {data.approved_at ? `${data.approved_by} · ${formatDateTime(data.approved_at)}` : "Not approved"}
                </KeyValue>
                <KeyValue label="Approval hash"><code>{data.approval_hash ? data.approval_hash.slice(0, 16) : "—"}</code></KeyValue>
              </dl>
              <details className="json-details">
                <summary>Stop conditions and evaluation criteria</summary>
                <div className="workflow-two-lists">
                  <div><span className="eyebrow">Stop conditions</span><ul className="plain-list">{(proposal.stop_conditions || []).map((item: string) => <li key={item}>{item}</li>)}</ul></div>
                  <div><span className="eyebrow">Evaluation</span><ul className="plain-list">{(proposal.evaluation_criteria || []).map((item: string) => <li key={item}>{item}</li>)}</ul></div>
                </div>
              </details>
              <details className="json-details">
                <summary>Language Level 0 intention (silent)</summary>
                <pre>{JSON.stringify(data.language_intention, null, 2)}</pre>
              </details>
            </div>
            {canApprove ? (
              <div className="workflow-action-box">
                <label className="checkbox">
                  <input type="checkbox" checked={scopeAcknowledged} onChange={(event) => setScopeAcknowledged(event.target.checked)} />
                  I approve the exact scope above and the bounded Worker budget.
                </label>
                <button className="button button-primary" onClick={() => void approve()} disabled={busy !== null || !scopeAcknowledged}>
                  <ShieldCheck size={15} /> Approve experiment
                </button>
              </div>
            ) : null}
            {canExecute ? (
              <div className="workflow-action-box">
                <p className="muted small">Execution requires explicit confirmation. The approved hash and baseline must still match.</p>
                <button className="button button-primary" onClick={() => void execute()} disabled={busy !== null}>
                  <Play size={15} /> Execute approved experiment
                </button>
              </div>
            ) : null}
          </Section>

          <Section title="Execution and measurement" description="Worker output is not treated as proof; deterministic tests are the gate.">
            <div className="workflow-execution">
              <dl className="kv-list">
                <KeyValue label="Worker status">{data.worker_status || "not run"}</KeyValue>
                <KeyValue label="Worker request"><code>{data.worker_request_id || "—"}</code></KeyValue>
                <KeyValue label="Patch">{String(data.patch.summary || "—")}</KeyValue>
                <KeyValue label="Result commit"><code>{data.result_commit || "—"}</code></KeyValue>
              </dl>
              {measurement.comparison && data.template === "trace_reduce_v1" ? (
                <div className="workflow-measurements">
                  <Metric label="Baseline events" value={String(measurement.comparison.baseline_events ?? "—")} />
                  <Metric label="Baseline reduced" value={String(measurement.comparison.baseline_reduced_events ?? "—")} />
                  <Metric label="After events" value={String(measurement.comparison.after_events ?? "—")} />
                  <Metric label="After reduced" value={String(measurement.comparison.after_reduced_events ?? "—")} />
                  <Metric label="Reduction" value={`${Math.round(Number(measurement.comparison.after_reduction_ratio ?? 0) * 100)}%`} />
                </div>
              ) : null}
              {measurement.comparison && data.template !== "trace_reduce_v1" ? (
                <div className="workflow-measurements">
                  <Metric label="Expected means" value={(measurement.comparison.expected_means || []).join(" / ") || "—"} />
                  <Metric label="Observed means" value={(measurement.comparison.observed_means || []).join(" / ") || "—"} />
                  <Metric label="Expected max" value={(measurement.comparison.expected_max || []).join(" / ") || "—"} />
                  <Metric label="Observed max" value={(measurement.comparison.observed_max || []).join(" / ") || "—"} />
                  <Metric label="Monotonic" value={measurement.comparison.monotonic ? "Yes" : "No"} />
                </div>
              ) : null}
              {measurement.tests?.output_tail ? (
                <details className="json-details">
                  <summary>Deterministic test output</summary>
                  <pre>{measurement.tests.output_tail}</pre>
                </details>
              ) : null}
              {data.worker_result?.output_excerpt ? (
                <details className="json-details">
                  <summary>Worker output excerpt</summary>
                  <pre>{data.worker_result.output_excerpt}</pre>
                </details>
              ) : null}
            </div>
          </Section>

          <Section title="CoCoder review" description="A passing review is not proof that the research hypothesis succeeded.">
            {data.review_summary?.available ? (
              <div className="workflow-review">
                <div className="workflow-review-head">
                  <div>
                    <span className="eyebrow">Independent review</span>
                    <h3>{data.adverse_review ? "Adverse review" : "No high/medium findings"}</h3>
                  </div>
                  <SimpleStatusBadge state={data.adverse_review ? "launch_failed" : "running"} label={data.adverse_review ? "Adverse" : "Clear"} />
                </div>
                <div className="workflow-measurements">
                  <Metric label="Findings" value={String(data.review_summary.findings ?? 0)} />
                  <Metric label="High" value={String(data.review_summary.high ?? 0)} />
                  <Metric label="Medium" value={String(data.review_summary.medium ?? 0)} />
                  <Metric label="Changed files" value={String(data.review_summary.changed_files ?? 0)} />
                </div>
                {data.review_summary.sample?.length ? (
                  <ul className="workflow-finding-list">
                    {data.review_summary.sample.map((finding: Record<string, unknown>) => (
                      <li key={String(finding.finding_id)}>
                        <Tag>{String(finding.severity)}</Tag>
                        <div><strong>{String(finding.title)}</strong><p>{truncate(String(finding.statement || ""), 400)}</p></div>
                      </li>
                    ))}
                  </ul>
                ) : <p className="muted small">No findings were returned for this review.</p>}
                <PathText>{data.review_artifact_path || ""}</PathText>
              </div>
            ) : (
              <EmptyState title="No review available" description="CoCoder review starts after a successful result commit." icon={<ShieldCheck size={18} />} />
            )}
          </Section>

          {data.language_observations?.length ? (
            <Section title="Language observation" description="A typed comparison of intention, expected properties and measured observations. It cannot rewrite the intention or control execution.">
              {data.language_observations.map((observation) => (
                <div className="workflow-review" key={observation.id}>
                  <div className="workflow-review-head">
                    <div>
                      <span className="eyebrow">{observation.schema}</span>
                      <h3>{observation.subject}</h3>
                    </div>
                    <SimpleStatusBadge
                      state={observation.constraint_result === "pass" ? "running" : "launch_failed"}
                      label={`Constraint ${observation.constraint_result}`}
                    />
                  </div>
                  <div className="workflow-observation-properties">
                    {observation.properties.map((property) => (
                      <div className="workflow-observation-property" key={property.id}>
                        <strong>{titleCase(property.id.replace(/_/g, " "))}</strong>
                        <dl className="kv-list">
                          <KeyValue label="Expected"><code>{JSON.stringify(property.expected)}</code></KeyValue>
                          <KeyValue label="Observed"><code>{JSON.stringify(property.observed)}</code></KeyValue>
                          <KeyValue label="Difference"><code>{JSON.stringify(property.difference)}</code></KeyValue>
                          <KeyValue label="Within constraint">{property.within_constraint ? "Yes" : "No"}</KeyValue>
                        </dl>
                      </div>
                    ))}
                  </div>
                  <p className="muted small">Method: {observation.measurement_method || "not stated"}</p>
                  {observation.uncertainty.length ? (
                    <ul className="plain-list">
                      {observation.uncertainty.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  ) : null}
                </div>
              ))}
            </Section>
          ) : null}

          {canDecide ? (
            <Section title="Human decision" description="The workflow cannot adopt itself. A human decision is required.">
              <div className="workflow-decision">
                {!testsPassed ? (
                  <div className="workflow-warning">
                    <AlertTriangle size={16} />
                    <span>Deterministic criteria did not pass. Failed tests can never be accepted.</span>
                  </div>
                ) : !reviewAvailable ? (
                  <div className="workflow-warning">
                    <AlertTriangle size={16} />
                    <span>A completed CoCoder review is required before acceptance. Investigate or reject this attempt.</span>
                  </div>
                ) : data.adverse_review ? (
                  <div className="workflow-warning">
                    <AlertTriangle size={16} />
                    <span>CoCoder reported high/medium findings. Acceptance requires an explicit human override with a reason.</span>
                  </div>
                ) : null}
                {data.adverse_review && testsPassed ? (
                  <label className="checkbox">
                    <input type="checkbox" checked={overrideAdverse} onChange={(event) => setOverrideAdverse(event.target.checked)} />
                    I explicitly override the adverse CoCoder review.
                  </label>
                ) : null}
                <label className="field">
                  <span>Decision reason</span>
                  <textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why is this the right outcome?" />
                </label>
                <div className="button-row">
                  <button className="button button-primary" onClick={() => void decide("accept")} disabled={busy !== null || !canAccept}>
                    <CheckCircle2 size={15} /> Accept outcome
                  </button>
                  <button className="button button-secondary" onClick={() => void decide("investigate")} disabled={busy !== null}>
                    Investigate further
                  </button>
                  <button className="button button-danger" onClick={() => void decide("reject")} disabled={busy !== null}>
                    <CircleSlash size={15} /> Reject
                  </button>
                </div>
              </div>
            </Section>
          ) : data.final_decision ? (
            <Section title="Final decision" description="Stored by Mission Control with the complete workflow trace.">
              <div className="workflow-final">
                <SimpleStatusBadge state={data.final_decision === "accept" ? "running" : "rejected"} label={titleCase(data.final_decision)} />
                <p>{data.final_reason || "No reason recorded."}</p>
                {data.override_adverse ? <span className="warn-text">Adverse review explicitly overridden.</span> : null}
              </div>
            </Section>
          ) : null}
        </div>

        <aside className="workflow-column workflow-aside">
          <Section title="Trace timeline" description="Every entry references its source; observations remain distinct from interpretations.">
            <ol className="workflow-timeline">
              {timeline.map((event) => (
                <li key={event.id}>
                  <span className={`workflow-event-dot event-${event.source}`} />
                  <div>
                    <div className="workflow-event-head">
                      <strong>{titleCase(event.event_type.replace(/_/g, " "))}</strong>
                      <time>{timeAgo(event.created_at)}</time>
                    </div>
                    <p>{event.summary}</p>
                    <span className="workflow-event-source">{event.source}</span>
                    <details>
                      <summary>Evidence payload</summary>
                      <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                    </details>
                  </div>
                </li>
              ))}
            </ol>
          </Section>
          <Section title="Provenance" description="Authoritative source references for this workflow.">
            <dl className="kv-list">
              <KeyValue label="Workflow"><code>{data.id}</code></KeyValue>
              <KeyValue label={isFixture ? "Fixture manifest" : "Next export"}><PathText>{String(data.next_evidence.export_path || "")}</PathText></KeyValue>
              <KeyValue label="Review artifact"><PathText>{data.review_artifact_path || "—"}</PathText></KeyValue>
              <KeyValue label="Created">{formatDateTime(data.created_at)}</KeyValue>
              <KeyValue label="Updated">{formatDateTime(data.updated_at)}</KeyValue>
              <KeyValue label="Provenance"><ProvenanceBadge value="verified_observation" /></KeyValue>
            </dl>
            <p className="muted small workflow-note">
              Language Level 0 is a silent structured intention. No Language model interpreted or negotiated this workflow.
            </p>
          </Section>
        </aside>
      </div>
    </div>
  );
}
