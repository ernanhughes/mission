import { useApi } from "../../api/useApi";
import { apiPath } from "../../api/client";
import type { WorkOverview, WorkTriageItem } from "../../types/api";
import { EmptyState, ErrorState, LoadingBlock, Section, Stat } from "../../components/ui";

export function CoverageView({ projectKey }: { projectKey: string }) {
  const overview = useApi<WorkOverview>(
    apiPath("/api/work-evaluation/overview", {
      project_key: projectKey || undefined,
      limit: 100,
    }),
  );
  const triage = useApi<{ triage: WorkTriageItem[] }>(
    apiPath("/api/work-intent/triage", { limit: 200 }),
  );
  const evalCoverage = useApi<{
    episode_assessments: number;
    requirements_assessed: number;
    claims_verified: number;
    findings: number;
  }>(apiPath("/api/work-evaluation/coverage", { project_key: projectKey || undefined }));

  if (overview.loading || triage.loading) return <LoadingBlock label="Loading coverage" />;
  if (overview.error)
    return <ErrorState message={`Coverage unavailable: ${overview.error.message}`} onRetry={overview.reload} />;

  const episodes = overview.data?.episodes ?? [];
  const evaluated = episodes.filter((r) => r.evaluated).length;
  const byClass: Record<string, number> = {};
  for (const t of triage.data?.triage ?? []) byClass[t.classification] = (byClass[t.classification] ?? 0) + 1;

  return (
    <div>
      <Section title="Evaluation coverage (consistent denominators)">
        <div className="stat-strip">
          <Stat label="Reconstructed episodes" value={episodes.length} />
          <Stat label="Evaluated episodes" value={evaluated} />
          <Stat label="Unevaluated episodes" value={episodes.length - evaluated} />
          <Stat label="Requirements assessed" value={evalCoverage.data?.requirements_assessed ?? "—"} />
          <Stat label="Claims verified" value={evalCoverage.data?.claims_verified ?? "—"} />
          <Stat label="Recorded findings" value={evalCoverage.data?.findings ?? "—"} />
        </div>
        <p className="muted">
          Unevaluated episodes are unknown, not failed. Stale evaluations are re-checked on new evidence;
          historical evaluations are preserved. Machine-generated scoring traffic remains addressable as
          evidence but is never presented as development work.
        </p>
      </Section>
      <Section title="Triage mix">
        {Object.keys(byClass).length === 0 ? (
          <EmptyState title="No triage records" description="Run observation and triage first." />
        ) : (
          <div className="stat-strip">
            {Object.entries(byClass).map(([name, count]) => (
              <Stat key={name} label={name} value={count} />
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
