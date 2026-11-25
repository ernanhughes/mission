import { useState } from "react";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, ErrorState, LoadingBlock, Section } from "../../components/ui";
import type { WorkEvalState } from "../../types/api";

/**
 * W6D manual operational controls. Every action is an explicit button click:
 * rendering this panel performs only GETs (queue, state, auto flag).
 * No timers, no polling, no model calls on page load.
 */
export function ControlsPanel() {
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [episodeId, setEpisodeId] = useState("");
  const queue = useApi<{ queue: { episode_id: string; queue_status: string; stale_reason: string }[] }>(
    "/api/work-evaluation/eval-queue",
  );
  const auto = useApi<{ auto_enabled: boolean; last_run: unknown; paid_budget_usd: number }>(
    "/api/work-evaluation/auto",
  );

  async function run(label: string, path: string, body?: unknown) {
    setBusy(label);
    setRunError(null);
    setResult(null);
    try {
      const out = await api.post<Record<string, unknown>>(path, body);
      setResult(`${label}: ${String(out.status ?? "done")}`);
      queue.reload();
      auto.reload();
    } catch (caught) {
      setRunError(`${label} failed: ${caught instanceof Error ? caught.message : "request failed"}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <Section title="Continuous evaluation status">
        {auto.loading ? (
          <LoadingBlock label="Loading automation status" />
        ) : auto.error ? (
          <ErrorState message={`Automation status unavailable: ${auto.error.message}`} onRetry={auto.reload} />
        ) : (
          <p className="muted">
            Scheduled evaluation: {auto.data?.auto_enabled ? "ENABLED (governed, paid budget $0)" : "off — manual only"}.
            Paid-inference budget for automatic evaluation: $0 (cannot be raised from here).
          </p>
        )}
        <div className="activity-actions">
          <button
            type="button"
            className="button button-small button-ghost"
            disabled={busy !== null}
            onClick={() => run("Disable scheduled evaluation", "/api/work-evaluation/auto", { enabled: false })}
          >
            Pause scheduled evaluation
          </button>
        </div>
      </Section>

      <Section title="Manual triggers">
        <div className="activity-actions">
          <button
            type="button"
            className="button button-small"
            disabled={busy !== null}
            onClick={() => run("Observe now", "/api/work-observation/runs", { project_contains: "ai", limit_sessions: 500 })}
          >
            {busy === "Observe now" ? "Observing…" : "Observe now"}
          </button>
          <button
            type="button"
            className="button button-small"
            disabled={busy !== null}
            onClick={() => run("Reconstruct changed work", "/api/work-episodes/runs", { project_contains: "ai" })}
          >
            {busy === "Reconstruct changed work" ? "Reconstructing…" : "Reconstruct changed work"}
          </button>
        </div>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <input
            className="input input-small"
            style={{ maxWidth: 260 }}
            placeholder="Episode id (e.g. ep:task:AI-CORE-05)"
            aria-label="Episode id to evaluate"
            value={episodeId}
            onChange={(e) => setEpisodeId(e.target.value)}
          />
          <button
            type="button"
            className="button button-small"
            disabled={busy !== null || episodeId.trim() === ""}
            onClick={() => run("Evaluate episode", "/api/work-evaluation/runs", { episode_id: episodeId.trim(), semantic: false })}
          >
            {busy === "Evaluate episode" ? "Evaluating…" : "Evaluate episode (deterministic)"}
          </button>
        </div>
        {result ? <p className="muted">{result}</p> : null}
        {runError ? <ErrorState message={runError} /> : null}
      </Section>

      <Section title="Evaluation queue">
        {queue.loading ? (
          <LoadingBlock label="Loading evaluation queue" />
        ) : queue.error ? (
          <ErrorState message={`Queue unavailable: ${queue.error.message}`} onRetry={queue.reload} />
        ) : (queue.data?.queue ?? []).length === 0 ? (
          <EmptyState title="Queue empty" description="No episodes awaiting evaluation. An empty queue means nothing is scheduled, not that everything is verified." />
        ) : (
          <ul className="activity-feed">
            {queue.data?.queue.map((q) => (
              <li key={q.episode_id}>
                <span className="activity-marker type-user" aria-hidden="true" />
                <div className="activity-entry">
                  <div className="activity-head">
                    <strong>{q.episode_id}</strong>
                  </div>
                  <div className="activity-meta">
                    <span>{q.queue_status}</span>
                    {q.stale_reason ? <span>stale: {q.stale_reason}</span> : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Freshness">
        <EvalStateList />
      </Section>
    </div>
  );
}

function EvalStateList() {
  const state = useApi<{ state: WorkEvalState[] }>("/api/work-evaluation/eval-state");
  if (state.loading) return <LoadingBlock label="Loading freshness" />;
  if (state.error)
    return <ErrorState message={`Freshness unavailable: ${state.error.message}`} onRetry={state.reload} />;
  const rows = state.data?.state ?? [];
  if (rows.length === 0)
    return (
      <EmptyState
        title="No freshness records"
        description="No evaluation has recorded freshness yet. Run a manual evaluation to seed per-episode state."
      />
    );
  const stale = rows.filter((r) => r.stale === 1);
  return (
    <div>
      <p className="muted">
        {rows.length} episode(s) tracked · {stale.length} stale
      </p>
      <ul className="activity-feed">
        {rows.slice(0, 20).map((r) => (
          <li key={r.episode_id}>
            <span className="activity-marker type-user" aria-hidden="true" />
            <div className="activity-entry">
              <div className="activity-head">
                <strong>{r.episode_id}</strong>
              </div>
              <div className="activity-meta">
                <span>{r.queue_status}</span>
                {r.stale === 1 ? <span>stale: {r.stale_reason || "changed inputs"}</span> : <span>current</span>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function staleText(stale: boolean, reason?: string): string | null {
  if (!stale) return null;
  return `Stale${reason ? `: ${reason}` : ""}`;
}
