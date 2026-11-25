import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, InlineError, LoadingBlock, Section, Stat, Tag } from "../../components/ui";
import { errorMessage } from "../../api/client";
import type { InspectInventoryProject } from "../../types/api";
import { actionLabel, cancelInspectRun, startInspectOp, useInspectOpsInventory, useInspectOpsJobs } from "./ops";

type Filter =
  | "all"
  | "never-inspected"
  | "needs-inspection"
  | "stale"
  | "partial"
  | "failed"
  | "current"
  | "needs-enrichment"
  | "unmapped";

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "never-inspected", label: "Never inspected" },
  { id: "needs-inspection", label: "Needs inspection" },
  { id: "stale", label: "Stale" },
  { id: "partial", label: "Partial" },
  { id: "failed", label: "Failed" },
  { id: "current", label: "Current" },
  { id: "needs-enrichment", label: "Needs enrichment" },
  { id: "unmapped", label: "Unmapped" },
];

function matchesFilter(row: InspectInventoryProject, filter: Filter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "never-inspected":
      return row.execution === "never-inspected";
    case "needs-inspection":
      return row.execution === "never-inspected" || row.freshness === "source-changed";
    case "stale":
      return row.freshness === "source-changed";
    case "partial":
      return row.execution === "partial";
    case "failed":
      return row.execution === "failed";
    case "current":
      return row.freshness === "current";
    case "needs-enrichment":
      return row.enrichment === "missing" || row.enrichment === "partial";
    case "unmapped":
      return !row.mapped;
  }
}

function toneForExecution(execution: string): "accent" | "warn" | "danger" | undefined {
  if (execution === "complete") return "accent";
  if (execution === "never-inspected") return undefined;
  if (execution === "failed") return "danger";
  return "warn";
}

export function OpsProjectsPanel() {
  const inventory = useInspectOpsInventory();
  const jobs = useInspectOpsJobs();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const counts = inventory.data?.counts ?? {};
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (inventory.data?.projects ?? []).filter((row) => {
      if (!matchesFilter(row, filter)) return false;
      if (needle && !`${row.name} ${row.inspect_id}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [inventory.data, filter, query]);

  async function runAction(repositoryId: string, operation: string, key: string) {
    setBusy(key);
    setNotice(null);
    try {
      const started = await startInspectOp(repositoryId, operation);
      setNotice(
        started.duplicate
          ? `Already running: ${started.run.run_id} (${started.run.operation}).`
          : `Started ${started.run.operation} (${started.run.run_id}).`,
      );
      inventory.reload();
      jobs.reload();
    } catch (caught) {
      setNotice(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function cancel(runId: string) {
    setBusy(`cancel:${runId}`);
    try {
      await cancelInspectRun(runId);
      jobs.reload();
      inventory.reload();
    } catch (caught) {
      setNotice(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Projects — operational control"
      description="Every known project, whether or not Inspect has examined it. Start, continue, enrich, stamp, and review inspections from here."
    >
      {inventory.loading ? <LoadingBlock label="Loading project inventory" compact /> : null}
      {inventory.error ? <InlineError message={inventory.error.message} /> : null}
      {notice ? <p className="muted small">{notice}</p> : null}
      {inventory.data ? (
        <>
          <div className="writer-stats">
            <Stat label="Projects" value={counts.total ?? rows.length} detail="in inventory" />
            <Stat label="Never inspected" value={counts.never_inspected ?? 0} detail="unknown, not failing" />
            <Stat label="Stale" value={counts.stale ?? 0} detail="source changed" />
            <Stat label="Running" value={counts.running ?? 0} detail="active jobs" />
            <Stat label="Current" value={counts.current ?? 0} detail="fresh evidence" />
          </div>
          <div className="button-row" role="group" aria-label="Inventory filters">
            {FILTERS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={filter === option.id ? "button-primary" : "button-secondary"}
                aria-pressed={filter === option.id}
                onClick={() => setFilter(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="muted small">
            <label>
              Search{" "}
              <input
                type="search"
                value={query}
                placeholder="name or id"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </p>
          {rows.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Inspection</th>
                    <th>Freshness</th>
                    <th>Caps</th>
                    <th>Enrich</th>
                    <th>Last run</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const running = row.execution === "running" || row.execution === "queued";
                    return (
                      <tr key={`${row.mission_application_id ?? "snap"}:${row.inspect_id}`}>
                        <td>
                          {row.mission_application_id ? (
                            <Link to={`/projects/${row.mission_application_id}?tab=inspect`}>
                              {row.name}
                            </Link>
                          ) : (
                            row.name
                          )}{" "}
                          <code className="mono small">{row.inspect_id}</code>{" "}
                          {row.mapped ? null : <Tag>unmapped</Tag>}
                          {row.stale_reason ? (
                            <div className="muted small">{row.stale_reason}</div>
                          ) : null}
                        </td>
                        <td>
                          <Tag tone={toneForExecution(row.execution)}>{row.execution}</Tag>
                        </td>
                        <td>{row.freshness}</td>
                        <td>{row.capabilities}</td>
                        <td>{row.enrichment}</td>
                        <td>
                          {row.last_run_status ? (
                            <span title={row.last_run_id ?? ""}>{row.last_run_status}</span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          {running ? (
                            <span className="muted small">running…</span>
                          ) : row.primary_action === "view" ? (
                            <span className="muted small">see below</span>
                          ) : row.available_actions.includes(row.primary_action) ? (
                            <button
                              type="button"
                              disabled={busy !== null}
                              onClick={() =>
                                runAction(
                                  row.mission_application_id ?? row.inspect_id,
                                  row.primary_action,
                                  `${row.inspect_id}:${row.primary_action}`,
                                )
                              }
                            >
                              {actionLabel(row.primary_action)}
                            </button>
                          ) : (
                            <span className="muted small">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No projects match"
              description="Adjust the filter or search — unmatched projects are never silently dropped from the full inventory."
            />
          )}
          {(inventory.data.unmapped ?? []).length ? (
            <p className="warn-text small">
              Unmapped snapshot projects:{" "}
              {(inventory.data.unmapped ?? []).map((u) => u.inspect_id).join(", ")} — inspected
              but not linked to a Mission application.
            </p>
          ) : null}
          <div className="button-row" aria-label="Ecosystem actions">
            <button
              type="button"
              className="button-secondary"
              disabled={busy !== null}
              onClick={() => runAction("", "validate", "eco:validate")}
            >
              Validate outputs
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={busy !== null}
              onClick={() => runAction("", "export", "eco:export")}
            >
              Publish snapshot
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={busy !== null}
              onClick={() => runAction("", "refresh", "eco:refresh")}
            >
              Refresh state
            </button>
          </div>
        </>
      ) : null}
      <h4>Jobs</h4>
      {jobs.loading ? <LoadingBlock label="Loading jobs" compact /> : null}
      {jobs.error ? <InlineError message={jobs.error.message} /> : null}
      {(jobs.data?.runs ?? []).length ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Repository</th>
                <th>Operation</th>
                <th>Status</th>
                <th>Requested</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(jobs.data?.runs ?? []).slice(0, 15).map((run) => (
                <tr key={run.run_id}>
                  <td>
                    <code className="mono small">{run.run_id}</code>
                  </td>
                  <td>{run.mission_application_id || run.repository_id || "ecosystem"}</td>
                  <td>{run.operation}</td>
                  <td>
                    {run.status}
                    {run.error ? <div className="muted small">{run.error.slice(0, 160)}</div> : null}
                  </td>
                  <td className="muted small">{run.requested_at || "—"}</td>
                  <td>
                    {run.cancellable ? (
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => cancel(run.run_id)}
                      >
                        Cancel
                      </button>
                    ) : (
                      <span className="muted small">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted small">No jobs yet — start an inspection above.</p>
      )}
    </Section>
  );
}
