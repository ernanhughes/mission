import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, GitBranch, Play, ShieldCheck } from "lucide-react";
import { useApi } from "../api/useApi";
import { EmptyState, ErrorState, LoadingBlock, PageHeader, SimpleStatusBadge, Tag } from "../components/ui";
import { timeAgo, titleCase, truncate } from "../lib/format";
import type { ExperimentWorkflow } from "../types/api";

function workflowState(status: string): string {
  if (status === "decided") return "running";
  if (status === "failed" || status === "review_failed") return "launch_failed";
  if (status === "executing" || status === "reviewing") return "in_progress";
  return "pending";
}

export function WorkflowsPage() {
  const workflows = useApi<ExperimentWorkflow[]>("/api/workflows", { pollMs: 10000 });
  return (
    <div className="page">
      <PageHeader
        eyebrow="Cross-application workflows"
        title="Experiments"
        description="Next evidence, human approval, Worker execution, CoCoder review and a durable human decision in one traceable record."
        actions={
          <Link className="button button-secondary" to="/next">
            <GitBranch size={15} /> Browse Next candidates
          </Link>
        }
      />
      {workflows.loading && !workflows.data ? <LoadingBlock label="Loading experiment workflows" /> : null}
      {workflows.error ? <ErrorState message={workflows.error.message} onRetry={workflows.reload} /> : null}
      {workflows.data && workflows.data.length === 0 ? (
        <EmptyState
          title="No experiment workflows yet"
          description="Open a validated Next candidate and propose a bounded experiment. A workflow is created only from real source evidence."
          icon={<GitBranch size={20} />}
        />
      ) : null}
      <div className="workflow-list">
        {workflows.data?.map((workflow) => (
          <Link className="workflow-card" key={workflow.id} to={`/workflows/${workflow.id}`}>
            <div className="workflow-card-head">
              <div>
                <span className="eyebrow">MC10 · {workflow.template}</span>
                <h2>{workflow.title}</h2>
              </div>
              <SimpleStatusBadge state={workflowState(workflow.status)} label={titleCase(workflow.status)} />
            </div>
            <p>{truncate(String(workflow.next_evidence?.opportunity?.what_discovered || workflow.next_title), 320)}</p>
            <div className="workflow-card-meta">
              <span><ShieldCheck size={13} /> Scope: {workflow.proposal.scope?.join(", ") || "not set"}</span>
              <span><Play size={13} /> Worker: {workflow.worker_status || "not run"}</span>
              {workflow.measurement?.passed ? <span className="text-good"><CheckCircle2 size={13} /> Tests passed</span> : null}
              {workflow.adverse_review ? <span className="warn-text"><AlertTriangle size={13} /> Adverse review</span> : null}
              {workflow.final_decision ? <Tag tone="accent">Decision: {workflow.final_decision}</Tag> : null}
              <span className="workflow-time">{timeAgo(workflow.updated_at)}</span>
            </div>
            <span className="workflow-open">Open trace <ArrowRight size={14} /></span>
          </Link>
        ))}
      </div>
    </div>
  );
}
