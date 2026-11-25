import { useState } from "react";
import { useApi } from "../../api/useApi";
import { apiPath } from "../../api/client";
import type { WorkOverview } from "../../types/api";
import { EmptyState, ErrorState, LoadingBlock, Section, Stat } from "../../components/ui";
import { completionTone } from "./labels";
import { Tag } from "../../components/ui";
import { ControlsPanel, staleText } from "./ControlsPanel";
import { EpisodesView } from "./EpisodesView";
import { ProposalsPanel } from "./ProposalsPanel";
import { OutstandingView } from "./OutstandingView";
import { QualityView } from "./QualityView";
import { CoverageView } from "./CoverageView";

type SubView = "overview" | "episodes" | "outstanding" | "proposals" | "quality" | "coverage" | "controls";

const SUB_VIEWS: { id: SubView; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "episodes", label: "Work Episodes" },
  { id: "outstanding", label: "Outstanding Work" },
  { id: "proposals", label: "Proposals" },
  { id: "quality", label: "Quality" },
  { id: "coverage", label: "Coverage" },
  { id: "controls", label: "Controls" },
];

export function WorkEvaluationTab() {
  const [view, setView] = useState<SubView>("overview");
  const [projectKey, setProjectKey] = useState("");
  const query = apiPath("/api/work-evaluation/overview", {
    project_key: projectKey || undefined,
    limit: 100,
  });
  const overview = useApi<WorkOverview>(query);

  return (
    <div>
      <div className="toolbar" role="tablist" aria-label="Work evaluation views">
        {SUB_VIEWS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={view === item.id}
            className={`button button-small ${view === item.id ? "button-primary" : "button-ghost"}`}
            onClick={() => setView(item.id)}
          >
            {item.label}
          </button>
        ))}
        <span className="toolbar-count">
          {overview.data ? `${overview.data.total} episode(s)` : ""}
        </span>
        <input
          className="input input-small"
          style={{ maxWidth: 220 }}
          placeholder="Filter by project…"
          aria-label="Filter by project"
          value={projectKey}
          onChange={(event) => setProjectKey(event.target.value)}
        />
      </div>

      {view === "overview" && <OverviewView overview={overview} />}
      {view === "episodes" && <EpisodesView projectKey={projectKey} />}
      {view === "outstanding" && <OutstandingView projectKey={projectKey} onOpenProposals={() => setView("proposals")} />}
      {view === "proposals" && <ProposalsPanel />}
      {view === "quality" && <QualityView projectKey={projectKey} />}
      {view === "coverage" && <CoverageView projectKey={projectKey} />}
      {view === "controls" && <ControlsPanel />}
    </div>
  );
}

function OverviewView({
  overview,
}: {
  overview: ReturnType<typeof useApi<WorkOverview>>;
}) {
  if (overview.loading) return <LoadingBlock label="Loading work evaluation" />;
  if (overview.error)
    return (
      <ErrorState
        message={`Work evaluation is unavailable: ${overview.error.message}`}
        onRetry={overview.reload}
      />
    );
  const rows = overview.data?.episodes ?? [];
  if (rows.length === 0)
    return (
      <EmptyState
        title="No work episodes reconstructed"
        description="Run observation and reconstruction first. Empty here means unavailable data, not finished work."
      />
    );

  const complete = rows.filter((r) => r.completion === "complete").length;
  const needsAttention = rows.filter(
    (r) => r.completion === "incomplete" || r.open_findings > 0,
  );
  const unverified = rows.filter((r) => !r.evaluated).length;
  const attention = [...needsAttention]
    .sort((a, b) => b.open_findings - a.open_findings || b.mandatory_open - a.mandatory_open)
    .slice(0, 10);

  return (
    <div>
      <Section title="State of work">
        <div className="stat-strip">
          <Stat label="Work episodes" value={rows.length} />
          <Stat label="Complete · verified" value={complete} />
          <Stat label="Needs attention" value={needsAttention.length} />
          <Stat label="Unevaluated" value={unverified} />
        </div>
      </Section>
      <Section title="Needs attention">
        {attention.length === 0 ? (
          <EmptyState title="Nothing outstanding" description="No open findings or incomplete episodes in scope." />
        ) : (
          <ul className="activity-feed">
            {attention.map((row) => {
              const tone = completionTone(row.completion);
              return (
                <li key={row.id}>
                  <span className="activity-marker type-user" aria-hidden="true" />
                  <div className="activity-entry">
                    <div className="activity-head">
                      <strong>{row.title || row.id}</strong>
                      <Tag tone={tone.tone}>{tone.label}</Tag>
                      {row.status === 'candidate' ? <Tag>Conditionally accepted</Tag> : null}
                    </div>
                    <div className="activity-meta">
                      <span>{row.kind}</span>
                      <span>{row.open_findings} open finding(s)</span>
                      {row.mandatory_open > 0 ? <span>{row.mandatory_open} requirement-linked</span> : null}
                      {!row.evaluated ? <span>Unevaluated</span> : null}
                      {staleText(row.stale, row.stale_reason) ? <span>{staleText(row.stale, row.stale_reason)}</span> : null}
                      {row.queue_status && row.queue_status !== "current" ? <span>{row.queue_status}</span> : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </div>
  );
}
