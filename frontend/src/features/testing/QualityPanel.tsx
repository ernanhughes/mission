import { useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, Section } from "../../components/ui";

type QualityRow = {
  project_id: string;
  name: string;
  mode: string;
  tests_evaluated: number;
  findings: Record<string, number>;
  recommendations: Record<string, number>;
  verification_gaps: number;
  redundancy_candidates: number;
  coverage_percent: number | null;
  mutations_attempted: number;
  mutations_killed: number;
  latest_at: string;
  cost_ms: number;
};

function timeAgo(ts: string): string {
  if (!ts) return "—";
  const then = Date.parse(ts);
  if (!Number.isFinite(then)) return "—";
  const s = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function TestsQualityPanel() {
  const rows = useApi<QualityRow[]>("/api/tests/quality/projects", { pollMs: 8000 });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function evaluate(row: QualityRow) {
    setBusy(row.project_id);
    setNotice("");
    try {
      await api.post(`/api/tests/projects/${row.project_id}/run`, { operation: "quality" });
      setNotice(`Quality assessment queued for ${row.name}.`);
      rows.reload();
    } catch (err) {
      setNotice(errorMessage(err));
    } finally {
      setBusy("");
    }
  }

  if (rows.error) {
    return <EmptyState title="Quality data unavailable" description={errorMessage(rows.error)} />;
  }
  const data = rows.data ?? [];
  return (
    <Section
      title="Quality assessment"
      description="Deterministic structural evidence. Candidates only — never a deletion decision."
    >
      {notice ? <p className="small muted">{notice}</p> : null}
      {rows.loading ? (
        <p className="muted">Loading quality summaries…</p>
      ) : data.length ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Project</th><th>Mode</th><th>Tests evaluated</th>
              <th>Structural candidates</th><th>Review candidates</th>
              <th>Verification gaps</th><th>Redundancy</th>
              <th>Coverage</th><th>Mutants killed</th><th>Assessed</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r: QualityRow) => {
              const findings = Object.values(r.findings || {})
                .reduce((a: number, b: number) => a + b, 0);
              const reviews = Object.entries(r.recommendations || {})
                .filter(([kind]) => kind !== "KEEP" && kind !== "KEEP_ESSENTIAL")
                .reduce((a: number, [, count]) => a + Number(count), 0);
              return (
                <tr key={r.project_id}>
                  <td>{r.name}</td>
                  <td>{r.mode || "—"}</td>
                  <td>{r.tests_evaluated}</td>
                  <td>{findings}</td>
                  <td>{reviews}</td>
                  <td>{r.verification_gaps}</td>
                  <td>{r.redundancy_candidates}</td>
                  <td>{r.coverage_percent == null ? "—" : `${r.coverage_percent.toFixed(1)}%`}</td>
                  <td>{r.mutations_attempted ? `${r.mutations_killed}/${r.mutations_attempted}` : "—"}</td>
                  <td>{timeAgo(r.latest_at)}</td>
                  <td>
                    <button className="button button-primary button-small"
                            disabled={!!busy}
                            onClick={() => void evaluate(r)}>
                      {busy === r.project_id ? "…" : "Evaluate"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <EmptyState
          title="No project has been quality-assessed yet"
          description="Press Evaluate, or run `aitest quality assess --root <repo>`."
        />
      )}
      <p className="muted small">
        Structural findings are heuristic candidates. Coverage is execution evidence,
        not verification. Surviving mutants may be uncovered or equivalent code.
        Permanent test deletion is not authorised in this programme.
        <Link to="/tests"> Back to execution</Link>
      </p>
    </Section>
  );
}
