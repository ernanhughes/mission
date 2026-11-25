import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { TestsQualityPanel } from "../features/testing/QualityPanel";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { EmptyState, Section } from "../components/ui";

type Summary = {
  projects: number;
  total_tests: number;
  assessed: number;
  unassessed: number;
  healthy: number;
  failing: number;
  quarantined: number;
  deferred: number;
  repair_needed: number;
};

type ProjectRow = {
  project_id: string;
  name: string;
  mc_project_id: string;
  policy: string;
  integration_state: string;
  last_status: string;
  total: number;
  unassessed: number;
  assessed: number;
  fast: number;
  slow: number;
  failing: number;
  quarantined: number;
  last_seen_at: string;
};

type Run = {
  run_id: string;
  project_id: string;
  project_name: string;
  operation: string;
  label: string;
  status: string;
  requested_at: string;
  started_at: string;
  finished_at: string;
  verification_status: string;
  counts: Record<string, number>;
  error: string;
  cancellable: boolean;
};

type Worker = {
  available: boolean;
  running: boolean;
  paused: boolean;
  state: string;
  current_project: string;
  current_job: string;
  completed_batches: number;
  last_project: string;
  last_result: string;
  last_error: string;
  updated_at: number;
};

const OPERATIONS: Array<{ id: string; label: string }> = [
  { id: "intelligent", label: "Intelligent testing" },
  { id: "fast", label: "Fast (changed) tests" },
  { id: "failed", label: "Failed tests only" },
  { id: "full", label: "Full verification" },
  { id: "discover", label: "Discover tests" },
  { id: "profile", label: "Profile unassessed" },
  { id: "diagnose", label: "Diagnose" },
];

function timeAgo(ts: string | number | null | undefined): string {
  if (!ts) return "—";
  const then = typeof ts === "number" ? ts * 1000 : Date.parse(ts);
  if (!Number.isFinite(then)) return "—";
  const s = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

function verificationLabel(status: string): string {
  switch (status) {
    case "FULL_PASS":
      return "Fully verified";
    case "TARGETED_PASS":
      return "Targeted pass";
    case "TEST_FAILURE":
      return "Genuine failures";
    case "TIMED_OUT":
      return "Timed out";
    case "INCOMPLETE":
      return "Incomplete";
    case "INFRASTRUCTURE_FAILURE":
      return "Infrastructure";
    case "CANCELLED":
      return "Cancelled";
    default:
      return status || "Unassessed";
  }
}

function projectStatus(row: ProjectRow, activeRun?: Run): string {
  if (activeRun) return activeRun.status === "queued" ? "Queued" : "Testing";
  if (row.integration_state === "blocked") return "Blocked";
  if (row.failing > 0) return "Needs attention";
  if (row.total === 0) return "No tests";
  if (row.unassessed === row.total) return "Unassessed";
  if (row.quarantined > 0) return "Quarantined";
  if (row.unassessed > 0) return "Partially assessed";
  return "Healthy";
}

export function TestsPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [busy, setBusy] = useState<string>("");
  const [notice, setNotice] = useState("");
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [view, setView] = useState<"execution" | "quality">("execution");

  const summary = useApi<Summary>("/api/tests/summary", { pollMs: 5000 });
  const projects = useApi<ProjectRow[]>("/api/tests/project-summaries", { pollMs: 5000 });
  const jobs = useApi<Run[]>("/api/tests/jobs", { pollMs: 3000 });
  const worker = useApi<Worker>("/api/tests/worker/status", { pollMs: 5000 });

  const refresh = useCallback(() => {
    summary.reload();
    projects.reload();
    jobs.reload();
    worker.reload();
  }, [summary, projects, jobs, worker]);

  const active = useMemo(
    () => (jobs.data ?? []).filter((j) => j.status === "running" || j.status === "queued"),
    [jobs.data],
  );
  const recent = useMemo(
    () => (jobs.data ?? []).filter((j) => j.status !== "running" && j.status !== "queued").slice(0, 8),
    [jobs.data],
  );

  const activeByProject = useMemo(() => {
    const m: Record<string, Run> = {};
    for (const j of active) m[j.project_id] = j;
    return m;
  }, [active]);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (projects.data ?? []).filter((r) => {
      if (needle && !`${r.name} ${r.project_id}`.toLowerCase().includes(needle)) return false;
      if (filter === "FAILING" && !(r.failing > 0)) return false;
      if (filter === "QUARANTINED" && !(r.quarantined > 0)) return false;
      if (filter === "UNASSESSED" && !(r.unassessed > 0)) return false;
      if (filter === "ADAPTIVE" && r.policy !== "standard" && r.policy !== "rapid") return false;
      if (filter === "EMPTY" && r.total > 0) return false;
      return true;
    });
  }, [projects.data, query, filter]);

  async function post(path: string, body?: unknown, tag = "") {
    setBusy(tag);
    setNotice("");
    try {
      await api.post(path, body ?? {});
      setNotice("Request accepted — the job is durable and will appear below.");
      refresh();
    } catch (err) {
      setNotice(errorMessage(err));
    } finally {
      setBusy("");
      setMenuFor(null);
    }
  }

  const s = summary.data;

  return (
    <div className="page">
      <div className="page-header-inline">
        <div>
          <span className="eyebrow">Tests</span>
          <h1>Testing command centre</h1>
        </div>
        <div className="inline-meta">
          <span className={`status-pill ${worker.data?.running ? "is-ok" : "is-warn"}`}>
            <span className="status-dot" aria-hidden="true" />
            {worker.data?.running
              ? `Worker online${worker.data.paused ? " (paused)" : ""}`
              : "Worker offline"}
          </span>
          <span className="muted small">
            {worker.data?.current_project
              ? `Assessing ${worker.data.current_project}`
              : `Heartbeat ${timeAgo(worker.data?.updated_at)}`}
          </span>
        </div>
      </div>

      {s ? (
        <div className="testing-stats" aria-label="Testing summary">
          {[
            ["Projects", s.projects],
            ["Tests", s.total_tests],
            ["Assessed", s.assessed],
            ["Awaiting", s.unassessed],
            ["Failing", s.failing],
            ["Quarantined", s.quarantined],
            ["Running", active.filter((j) => j.status === "running").length],
            ["Queued", active.filter((j) => j.status === "queued").length],
          ].map(([label, value]) => (
            <span key={String(label)} className="testing-stat">
              <span className="testing-stat-label">{label}</span>
              <strong>{Number(value).toLocaleString()}</strong>
            </span>
          ))}
        </div>
      ) : summary.error ? (
        <EmptyState title="Testing data unavailable" description={errorMessage(summary.error)} />
      ) : (
        <p className="muted">Loading summary…</p>
      )}

      <div className="inline-form testing-toolbar">
        <button className="button button-primary button-small" disabled={!!busy}
                onClick={() => void post("/api/tests/run-all", {}, "all")}>
          {busy === "all" ? "Submitting…" : "Test all projects"}
        </button>
        <button className="button button-secondary button-small" disabled={!!busy}
                onClick={() => void post(`/api/tests/worker/${worker.data?.paused ? "resume" : "pause"}`, {}, "pause")}>
          {worker.data?.paused ? "Resume worker" : "Pause worker"}
        </button>
        <button className="button button-secondary button-small" disabled={!!busy}
                onClick={() => void post("/api/tests/worker/restart", {}, "restart")}>
          Restart worker
        </button>
        <button className="button button-secondary button-small" disabled={!!busy}
                onClick={() => void post("/api/tests/worker/start", {}, "start")}>
          Start worker
        </button>
        <button className="button button-secondary button-small" disabled={!!busy}
                onClick={() => void post("/api/tests/worker/stop", {}, "stop")}>
          Stop worker
        </button>
      </div>
      {notice ? <p className="small muted">{notice}</p> : null}

      <div className="inline-form testing-toolbar" role="tablist" aria-label="Testing views">
        <button className={`button button-small ${view === "execution" ? "button-primary" : "button-secondary"}`}
                role="tab" aria-selected={view === "execution"}
                onClick={() => setView("execution")}>Execution</button>
        <button className={`button button-small ${view === "quality" ? "button-primary" : "button-secondary"}`}
                role="tab" aria-selected={view === "quality"}
                onClick={() => setView("quality")}>Quality</button>
      </div>

      {view === "quality" ? <TestsQualityPanel /> : null}

      {view === "execution" ? (
      <div>
      <Section title="Projects" description="Every registered testing project. Test starts a real supervised run.">
        <div className="inline-form" role="search">
          <label className="muted small">
            Search{" "}
            <input value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder="project name" size={22} aria-label="Search projects" />
          </label>
          <label className="muted small">
            Filter{" "}
            <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter projects">
              <option value="ALL">All</option>
              <option value="FAILING">Failing</option>
              <option value="QUARANTINED">Quarantined</option>
              <option value="UNASSESSED">Unassessed</option>
              <option value="ADAPTIVE">Adaptive</option>
              <option value="EMPTY">No tests</option>
            </select>
          </label>
          <span className="muted small">{rows.length} shown</span>
        </div>
        {projects.loading ? (
          <p className="muted">Loading projects…</p>
        ) : rows.length ? (
          <table className="data-table tests-table">
            <thead>
              <tr>
                <th>Project</th><th>Status</th><th>Policy</th><th>Tests</th>
                <th>Assessed</th><th>Passed</th><th>Failed</th><th>Slow</th>
                <th>Quarantined</th><th>Last assessed</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const run = activeByProject[r.project_id];
                const status = projectStatus(r, run);
                const cls = status === "Needs attention" || status === "Blocked"
                  ? "is-bad" : status === "Healthy" ? "is-ok" : "is-warn";
                return (
                  <tr key={r.project_id}>
                    <td>
                      {r.mc_project_id ? (
                        <Link to={`/projects/${r.mc_project_id}?tab=tests`}>{r.name}</Link>
                      ) : r.name}
                    </td>
                    <td><span className={`status-pill ${cls}`}>{status}</span></td>
                    <td>{r.policy === "standard" || r.policy === "rapid" ? "Adaptive" : "Observe"}</td>
                    <td>{r.total.toLocaleString()}</td>
                    <td>{r.assessed.toLocaleString()}</td>
                    <td>{Math.max(0, r.assessed - r.failing - r.quarantined).toLocaleString()}</td>
                    <td>{r.failing}</td>
                    <td>{r.slow}</td>
                    <td>{r.quarantined}</td>
                    <td>{timeAgo(r.last_seen_at)}</td>
                    <td className="actions-cell">
                      <button className="button button-primary button-small"
                              disabled={!!busy || r.integration_state === "blocked"}
                              title={r.integration_state === "blocked"
                                ? "Testing is blocked for this project"
                                : "Run testing"}
                              onClick={() => void post(`/api/tests/projects/${r.project_id}/run`,
                                                       { operation: "intelligent" }, r.project_id)}>
                        {busy === r.project_id ? "…" : "Test"}
                      </button>
                      <button className="button button-secondary button-small"
                              onClick={() => setMenuFor(menuFor === r.project_id ? null : r.project_id)}
                              aria-label={`More testing actions for ${r.name}`}>
                        ▾
                      </button>
                      {menuFor === r.project_id ? (
                        <div className="action-menu" role="menu">
                          {OPERATIONS.map((op) => (
                            <button key={op.id} role="menuitem" className="action-menu-item"
                                    disabled={!!busy}
                                    onClick={() => void post(
                                      `/api/tests/projects/${r.project_id}/run`,
                                      { operation: op.id }, r.project_id)}>
                              {op.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <EmptyState title="No projects match" description="Clear the filters or run Discover." />
        )}
      </Section>

      <Section title="Active testing" description="Live executions started from this page.">
        {active.length ? (
          <table className="data-table">
            <thead>
              <tr><th>Project</th><th>Operation</th><th>Status</th><th>Started</th><th>Elapsed</th><th /></tr>
            </thead>
            <tbody>
              {active.map((j) => {
                const started = Date.parse(j.started_at || j.requested_at);
                const secs = Number.isFinite(started) ? Math.round((Date.now() - started) / 1000) : 0;
                return (
                  <tr key={j.run_id}>
                    <td>{j.project_name}</td>
                    <td>{j.label}</td>
                    <td><span className={`status-pill ${j.status === "running" ? "is-ok" : "is-warn"}`}>
                      {j.status === "running" ? "Testing" : "Queued"}</span></td>
                    <td>{timeAgo(j.started_at || j.requested_at)}</td>
                    <td>{secs}s</td>
                    <td>
                      <button className="button button-secondary button-small"
                              onClick={() => void post(`/api/tests/jobs/${j.run_id}/cancel`, {}, j.run_id)}>
                        Cancel
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="muted small">Nothing running. Pick a project and press Test.</p>
        )}
      </Section>

      <Section title="Recent results" description="Verification outcomes are receipts, not claims.">
        {recent.length ? (
          <table className="data-table">
            <thead>
              <tr><th>Project</th><th>Operation</th><th>Verification</th><th>Executed</th>
                <th>Passed</th><th>Failed</th><th>Deferred</th><th>Finished</th></tr>
            </thead>
            <tbody>
              {recent.map((j) => (
                <tr key={j.run_id}>
                  <td>{j.project_name}</td>
                  <td>{j.label}</td>
                  <td>{verificationLabel(j.verification_status)}{j.error ? ` — ${j.error}` : ""}</td>
                  <td>{j.counts.executed ?? "—"}</td>
                  <td>{j.counts.passed ?? "—"}</td>
                  <td>{j.counts.failed ?? "—"}</td>
                  <td>{j.counts.deferred ?? "—"}</td>
                  <td>{timeAgo(j.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted small">No executions yet.</p>
        )}
      </Section>
      </div>
      ) : null}
    </div>
  );
}
