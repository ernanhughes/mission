import { Link } from "react-router-dom";
import { EmptyState, Section } from "../components/ui";
import { errorMessage } from "../api/client";
import { useTestsProjects, useTestsSummary } from "../features/testing/api";

const BANDS = ["INSTANT", "FAST", "STANDARD", "MODERATE", "SLOW", "VERY_SLOW", "EXPENSIVE", "UNASSESSED"];

export function TestsPage() {
  const summary = useTestsSummary();
  const projects = useTestsProjects();

  if (summary.error || projects.error) {
    return (
      <div className="page">
        <span className="eyebrow">Tests</span>
        <h1>Testing overview</h1>
        <EmptyState
          title="Testing data unavailable"
          description={errorMessage(summary.error ?? projects.error)}
        />
      </div>
    );
  }

  const s = summary.data;
  const rows = projects.data ?? [];
  return (
    <div className="page">
      <span className="eyebrow">Tests</span>
      <h1>Testing overview</h1>
      <p className="muted">
        Central visibility into AI Test evidence. Missing or stale data is shown
        explicitly — absence of data is never presented as passing.
      </p>
      {summary.loading || !s ? (
        <p className="muted">Loading summary…</p>
      ) : (
        <dl className="stat-grid" aria-label="Testing summary">
          <div className="stat"><dt>Projects</dt><dd>{s.projects}</dd></div>
          <div className="stat"><dt>Total tests</dt><dd>{s.total_tests}</dd></div>
          <div className="stat"><dt>Assessed</dt><dd>{s.assessed}</dd></div>
          <div className="stat"><dt>Unassessed</dt><dd>{s.unassessed}</dd></div>
          <div className="stat"><dt>Healthy</dt><dd>{s.healthy}</dd></div>
          <div className="stat"><dt>Failing</dt><dd>{s.failing}</dd></div>
          <div className="stat"><dt>Quarantined</dt><dd>{s.quarantined}</dd></div>
          <div className="stat"><dt>Deferred</dt><dd>{s.deferred}</dd></div>
          <div className="stat"><dt>Repair needed</dt><dd>{s.repair_needed}</dd></div>
        </dl>
      )}
      <Section title="Projects" description="One row per registered testing project.">
        {projects.loading ? (
          <p className="muted">Loading projects…</p>
        ) : rows.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>State</th>
                <th>Policy</th>
                <th>Last status</th>
                <th>Last receipt</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.project_id}>
                  <td>
                    {p.mc_project_id ? (
                      <Link to={`/projects/${p.mc_project_id}?tab=tests`}>{p.name || p.project_id}</Link>
                    ) : (
                      p.name || p.project_id
                    )}
                  </td>
                  <td>{p.integration_state}</td>
                  <td>{p.policy}</td>
                  <td>{p.last_status || "—"}</td>
                  <td>{p.last_receipt_id ? p.last_receipt_id.slice(0, 12) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState
            title="No testing projects registered"
            description="Run `aitest mission sync` in a project to register it here."
          />
        )}
      </Section>
      <Section title="Duration bands" description="Reference for the per-test bands in project inventories.">
        <ul className="inline-list">
          {BANDS.map((b) => (
            <li key={b}><code>{b}</code></li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
