import { useApi } from "../../api/useApi";
import { apiPath } from "../../api/client";
import type { WorkOverview } from "../../types/api";
import { EmptyState, ErrorState, LoadingBlock, Section, Tag } from "../../components/ui";
import { assessmentTone } from "./labels";

export function QualityView({ projectKey }: { projectKey: string }) {
  const overview = useApi<WorkOverview>(
    apiPath("/api/work-evaluation/overview", {
      project_key: projectKey || undefined,
      limit: 100,
    }),
  );

  if (overview.loading) return <LoadingBlock label="Loading quality view" />;
  if (overview.error)
    return <ErrorState message={`Quality view unavailable: ${overview.error.message}`} onRetry={overview.reload} />;
  const rows = (overview.data?.episodes ?? []).filter((r) => r.evaluated);
  if (rows.length === 0)
    return (
      <EmptyState
        title="No evaluated episodes"
        description="Execution, outcome and completion quality appear here once episodes are evaluated. Unevaluated work is not poor work."
      />
    );

  return (
    <div>
      <Section title="Per-episode quality (independent perspectives, no composite score)">
        <ul className="activity-feed">
          {rows.map((row) => {
            const exec = assessmentTone(row.execution);
            const out = assessmentTone(row.outcome);
            return (
              <li key={row.id}>
                <span className="activity-marker type-user" aria-hidden="true" />
                <div className="activity-entry">
                  <div className="activity-head">
                    <strong>{row.title || row.id}</strong>
                    <Tag tone={exec.tone}>Execution: {exec.label}</Tag>
                    <Tag tone={out.tone}>Outcome: {out.label}</Tag>
                    {row.status === "candidate" ? <Tag>Conditionally accepted</Tag> : null}
                  </div>
                  <div className="activity-meta">
                    <span>{row.kind}</span>
                    <span>{row.open_findings} open finding(s)</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </Section>
      <Section title="Reading this view">
        <p className="muted">
          Execution, outcome and completion are assessed independently. A technically good implementation can
          still be incomplete; a complete episode can still have quality concerns. No rankings are computed here.
        </p>
      </Section>
    </div>
  );
}
