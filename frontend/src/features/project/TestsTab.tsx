import { useMemo, useState } from "react";
import { EmptyState, Section } from "../../components/ui";
import { apiPath, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import type {
  AitestIssue,
  AitestProject,
  AitestReceipt,
  AitestTest,
} from "../../features/testing/api";

const BANDS = ["INSTANT", "FAST", "STANDARD", "MODERATE", "SLOW", "VERY_SLOW", "EXPENSIVE", "UNASSESSED"];

export function TestsTab({ mcProjectId }: { mcProjectId: string }) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [band, setBand] = useState("ALL");
  const [lifecycle, setLifecycle] = useState("ALL");

  const projects = useApi<AitestProject[]>("/api/tests/projects");
  const candidates = useMemo(() => projects.data ?? [], [projects.data]);
  const effective = projectId ?? candidates.find((p) => p.mc_project_id === mcProjectId)?.project_id ?? null;

  const inventory = useApi<AitestTest[]>(
    effective ? apiPath(`/api/tests/projects/${effective}/inventory`, { limit: 200 }) : null,
  );
  const receipts = useApi<AitestReceipt[]>(
    effective ? `/api/tests/projects/${effective}/receipts` : null,
  );
  const issues = useApi<AitestIssue[]>(
    effective ? `/api/tests/projects/${effective}/issues` : null,
  );

  const tests = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (inventory.data ?? []).filter((t) => {
      if (band !== "ALL" && t.band !== band) return false;
      if (lifecycle !== "ALL" && t.lifecycle !== lifecycle) return false;
      if (needle && !`${t.relpath} ${t.func_name}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [inventory.data, query, band, lifecycle]);

  const dist = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of inventory.data ?? []) counts[t.band] = (counts[t.band] ?? 0) + 1;
    return counts;
  }, [inventory.data]);

  const latest = receipts.data?.[0];
  const openIssues = (issues.data ?? []).filter((i) => i.status === "open");

  if (projects.error) {
    return <EmptyState title="Testing data unavailable" description={errorMessage(projects.error)} />;
  }
  if (!candidates.length) {
    return (
      <EmptyState
        title="No testing project linked"
        description="Run `aitest mission sync` in the repository, then link it with `aitest mission link`."
      />
    );
  }

  return (
    <div>
      <Section title="Test summary" description="Measured evidence, not estimates.">
        <label className="muted small">
          Testing project{" "}
          <select value={effective ?? ""} onChange={(e) => setProjectId(e.target.value || null)}>
            {candidates.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name || p.project_id}
              </option>
            ))}
          </select>
        </label>
        {latest ? (
          <dl className="stat-grid" aria-label="Latest execution">
            <div className="stat"><dt>Status</dt><dd>{latest.status}</dd></div>
            <div className="stat"><dt>Passed</dt><dd>{latest.passed}</dd></div>
            <div className="stat"><dt>Failed</dt><dd>{latest.failed}</dd></div>
            <div className="stat"><dt>Quarantined</dt><dd>{latest.quarantined}</dd></div>
            <div className="stat"><dt>Deferred</dt><dd>{latest.deferred}</dd></div>
            <div className="stat"><dt>Unobserved</dt><dd>{latest.unobserved}</dd></div>
          </dl>
        ) : (
          <p className="muted small">No execution receipts yet.</p>
        )}
      </Section>
      <Section title="Duration distribution" description="Measured duration classes across the inventory.">
        <ul className="inline-list">
          {BANDS.map((b) => (
            <li key={b}><code>{b}</code>: {dist[b] ?? 0}</li>
          ))}
        </ul>
      </Section>
      {openIssues.length ? (
        <Section title="Needs attention" description="Open testing issues for this project.">
          <ul>
            {openIssues.slice(0, 20).map((i) => (
              <li key={i.id}><strong>{i.kind}</strong> — {i.title}</li>
            ))}
          </ul>
        </Section>
      ) : null}
      <Section title="Test inventory" description="Searchable, filterable. Showing up to 200 rows.">
        <div className="inline-form" role="search">
          <label className="muted small">
            Search <input value={query} onChange={(e) => setQuery(e.target.value)} size={24} aria-label="Search tests" />
          </label>
          <label className="muted small">
            Band{" "}
            <select value={band} onChange={(e) => setBand(e.target.value)}>
              <option value="ALL">All</option>
              {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </label>
          <label className="muted small">
            Lifecycle{" "}
            <select value={lifecycle} onChange={(e) => setLifecycle(e.target.value)}>
              <option value="ALL">All</option>
              {["ACTIVE", "CANDIDATE", "DEFERRED", "QUARANTINED", "RETIRED"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        {inventory.loading ? (
          <p className="muted">Loading inventory…</p>
        ) : tests.length ? (
          <table className="data-table">
            <thead>
              <tr><th>Test</th><th>File</th><th>Duration</th><th>Class</th><th>Last result</th><th>Lifecycle</th></tr>
            </thead>
            <tbody>
              {tests.map((t) => (
                <tr key={t.logical_id}>
                  <td>{t.func_name}</td>
                  <td>{t.relpath}</td>
                  <td>{(t.duration_ms / 1000).toFixed(2)}s</td>
                  <td>{t.band}</td>
                  <td>{t.last_outcome || "—"}</td>
                  <td>{t.lifecycle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="No tests match" description="Broaden the filters." />
        )}
      </Section>
    </div>
  );
}
