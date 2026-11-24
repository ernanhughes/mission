import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import type {
  PipelineMaintenanceReport,
  PipelineMaintenanceStatus,
} from "../../types/api";
import { EmptyState, ErrorState, InlineError, LoadingBlock } from "../../components/ui";
import { useToast } from "../../components/Toast";

export function MaintenanceStrip() {
  const statusQuery = useApi<PipelineMaintenanceStatus>("/api/pipeline/maintenance");
  const toast = useToast();
  const [checking, setChecking] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [lastCheck, setLastCheck] = useState<PipelineMaintenanceReport | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  const status = statusQuery.data;

  async function setEnabled(enabled: boolean) {
    setToggling(true);
    try {
      await api.post("/api/pipeline/maintenance/enabled", { enabled });
      toast.push("success", enabled ? "Automatic maintenance enabled" : "Automatic maintenance paused");
      statusQuery.reload();
    } catch (caught) {
      toast.push("error", "Could not change maintenance setting", errorMessage(caught));
    } finally {
      setToggling(false);
    }
  }

  async function checkNow() {
    setChecking(true);
    setCheckError(null);
    try {
      // Dry run: compute what would run without dispatching anything.
      const report = await api.post<PipelineMaintenanceReport>(
        "/api/pipeline/maintenance/reconcile",
        { dry_run: true },
      );
      setLastCheck(report);
    } catch (caught) {
      setCheckError(errorMessage(caught));
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="panel pipe-maintenance" aria-label="Automatic maintenance">
      <span className="eyebrow">Automatic maintenance</span>
      <h3>Deterministic upkeep runs itself</h3>
      {statusQuery.loading && !status ? <LoadingBlock label="Reading maintenance state…" compact /> : null}
      {statusQuery.error ? (
        <ErrorState message={statusQuery.error.message} onRetry={statusQuery.reload} />
      ) : null}
      {status ? (
        <div className="stack">
          <div className="inline-meta">
            <span className={`pipe-badge pipe-tone-${status.enabled ? "current" : "na"}`}>
              <span className="pipe-dot" aria-hidden="true" />
              {status.enabled ? "on" : "paused"}
            </span>
            <span className="muted small">policy {status.policy_version}</span>
            <span className="muted small">automatic: {status.auto_stages.join(", ") || "none"}</span>
            {status.active.length ? (
              <span className="muted small">
                running: {status.active.map((item) => item.execution_id).join(", ")}
              </span>
            ) : null}
            {status.recent_failures.length ? (
              <span className="muted small">recent failures: {status.recent_failures.length}</span>
            ) : null}
          </div>
          <p className="muted small">
            Eligible deterministic work (currently: verified MRI observation) runs on its own
            when evidence is missing or stale. Paid analysis, strengthening and manuscript edits
            never run automatically.
          </p>
          <div className="button-row">
            <button
              className="button button-secondary button-small"
              type="button"
              disabled={toggling}
              onClick={() => void setEnabled(!status.enabled)}
            >
              <RefreshCw size={14} /> {status.enabled ? "Pause all" : "Resume all"}
            </button>
            <button
              className="button button-secondary button-small"
              type="button"
              disabled={checking}
              onClick={() => void checkNow()}
            >
              <RefreshCw size={14} /> {checking ? "Checking…" : "Check for work"}
            </button>
          </div>
          {checkError ? <InlineError message={checkError} /> : null}
          {lastCheck ? (
            <div className="mini-block">
              <span>
                Eligible now: {lastCheck.eligible.length} · skipped {lastCheck.skipped} ·
                blocked {lastCheck.blocked} · waiting {lastCheck.waiting}
                {lastCheck.dry_run ? " (dry run — nothing dispatched)" : null}
              </span>
              {lastCheck.eligible.length ? (
                <ul className="pipe-check-list">
                  {lastCheck.eligible.slice(0, 12).map((item) => (
                    <li key={`${item.project_id}/${item.chapter_id}`}>
                      <strong>{item.project_id}</strong> · {item.chapter_id} · {item.stage_id} —{" "}
                      {item.reason}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted small">Nothing eligible right now.</p>
              )}
            </div>
          ) : null}
          {status.recent_failures.length ? (
            <div className="mini-block">
              <span>Recent failures needing attention</span>
              <ul className="pipe-check-list">
                {status.recent_failures.slice(0, 5).map((item) => (
                  <li key={item.execution_id}>
                    <code>{item.chapter_file}</code> — {item.error || "failed"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {!status && !statusQuery.loading && !statusQuery.error ? (
        <EmptyState title="Maintenance state unavailable" description="The status endpoint did not respond." />
      ) : null}
    </section>
  );
}
