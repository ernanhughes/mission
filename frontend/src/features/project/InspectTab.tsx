import { useMemo, useState } from "react";
import { EmptyState, InlineError, LoadingBlock, Section, Tag } from "../../components/ui";
import { errorMessage } from "../../api/client";
import { actionLabel, cancelInspectRun, startInspectOp, useInspectOpsInventory, useInspectOpsJobs } from "../../features/inspect/ops";

export function InspectTab({ mcProjectId }: { mcProjectId: string }) {
  const inventory = useInspectOpsInventory();
  const jobs = useInspectOpsJobs(mcProjectId);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const row = useMemo(
    () => (inventory.data?.projects ?? []).find((p) => p.mission_application_id === mcProjectId) ?? null,
    [inventory.data, mcProjectId],
  );

  async function run(operation: string) {
    setBusy(true);
    setNotice(null);
    try {
      const started = await startInspectOp(mcProjectId, operation);
      setNotice(
        started.duplicate
          ? `Already running: ${started.run.run_id}.`
          : `Started ${started.run.operation} (${started.run.run_id}).`,
      );
      inventory.reload();
      jobs.reload();
    } catch (caught) {
      setNotice(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (inventory.error) {
    return <EmptyState title="Inspection data unavailable" description={errorMessage(inventory.error)} />;
  }
  if (inventory.loading && !row) {
    return <LoadingBlock label="Loading inspection state" />;
  }
  if (!row) {
    return (
      <EmptyState
        title="Project not in the inspection inventory"
        description="This Mission application has no repository path linked, or the inventory is still loading. Link a repository path to enable inspection."
      />
    );
  }

  return (
    <div>
      <Section title="Inspection state" description="Has it been inspected, when, and is the evidence still current?">
        <p>
          <Tag>{row.execution}</Tag> <span className="muted small">freshness: {row.freshness}</span>{" "}
          <span className="muted small">enrichment: {row.enrichment}</span>{" "}
          <span className="muted small">evidence: {row.evidence}</span>
        </p>
        {row.stale_reason ? <p className="warn-text small">{row.stale_reason}</p> : null}
        <div className="writer-mini-scores">
          <span>capabilities: {row.capabilities}</span>
          <span>usage recipes: {row.usages}</span>
          {row.inspected_head_sha ? <span>inspected: {row.inspected_head_sha.slice(0, 12)}</span> : null}
          {row.last_run_status ? <span>last run: {row.last_run_status}</span> : null}
        </div>
        {notice ? <p className="muted small">{notice}</p> : null}
        <div className="button-row">
          {row.primary_action !== "view" && row.available_actions.includes(row.primary_action) ? (
            <button type="button" className="button-primary" disabled={busy} onClick={() => run(row.primary_action)}>
              {actionLabel(row.primary_action)}
            </button>
          ) : null}
          {row.available_actions
            .filter((action) => action !== row.primary_action && action !== "view")
            .map((action) => (
              <button key={action} type="button" className="button-secondary" disabled={busy} onClick={() => run(action)}>
                {actionLabel(action)}
              </button>
            ))}
        </div>
        {!row.reachable ? (
          <p className="warn-text small">Repository path is missing or not a git checkout — actions that need source are unavailable.</p>
        ) : null}
      </Section>

      <Section title="History" description="Latest attempted runs first; the last successful published inspection is preserved separately.">
        {jobs.loading ? <LoadingBlock label="Loading runs" compact /> : null}
        {jobs.error ? <InlineError message={jobs.error.message} /> : null}
        {(jobs.data?.runs ?? []).length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Operation</th>
                  <th>Status</th>
                  <th>Requested</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {(jobs.data?.runs ?? []).slice(0, 10).map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <code className="mono small">{run.run_id}</code>
                    </td>
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
                          disabled={busy}
                          onClick={() => {
                            setBusy(true);
                            cancelInspectRun(run.run_id)
                              .then(() => {
                                jobs.reload();
                                inventory.reload();
                              })
                              .catch((caught: unknown) => setNotice(errorMessage(caught)))
                              .finally(() => setBusy(false));
                          }}
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
          <p className="muted small">No runs yet for this project.</p>
        )}
      </Section>
    </div>
  );
}
