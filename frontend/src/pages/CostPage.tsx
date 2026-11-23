import { useMemo, useState } from "react";
import { Activity } from "lucide-react";
import { apiPath } from "../api/client";
import { useApi } from "../api/useApi";
import { Modal } from "../components/Modal";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import type {
  CostSession,
  CostSessionDetail,
  CostSessionList,
  CostSpikes,
  CostStatus,
  CostSummary,
} from "../types/api";

type Preset = "today" | "yesterday" | "7d" | "30d" | "custom";

function dublinToday(): string {
  try {
    const fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Dublin",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    return fmt.format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}

function formatMs(ms: number): string {
  if (!ms) return "—";
  try {
    return new Date(ms).toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(ms);
  }
}

function formatCost(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "$0";
  if (value < 0.01) return `$${value.toFixed(6)}`;
  return `$${value.toFixed(4)}`;
}

function formatNum(value: number): string {
  return Number(value || 0).toLocaleString();
}

export function CostPage() {
  const [preset, setPreset] = useState<Preset>("today");
  const [customFrom, setCustomFrom] = useState("2026-11-22");
  const [customTo, setCustomTo] = useState("2026-11-22");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [page, setPage] = useState(0);
  const [detailId, setDetailId] = useState<string | null>(null);
  const limit = 50;

  const summaryQuery = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      preset,
      timezone: "Europe/Dublin",
    };
    if (preset === "custom") {
      if (customFrom) params.date_from = customFrom;
      if (customTo) params.date_to = customTo;
    }
    return apiPath("/api/cost/summary", params);
  }, [preset, customFrom, customTo]);

  const sessionsQuery = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      preset,
      timezone: "Europe/Dublin",
      limit,
      offset: page * limit,
      search: appliedSearch || undefined,
      project_id: projectFilter || undefined,
    };
    if (preset === "custom") {
      if (customFrom) params.date_from = customFrom;
      if (customTo) params.date_to = customTo;
    }
    return apiPath("/api/cost/sessions", params);
  }, [preset, customFrom, customTo, page, appliedSearch, projectFilter]);

  const spikesQuery = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      preset,
      timezone: "Europe/Dublin",
    };
    if (preset === "custom") {
      if (customFrom) params.date_from = customFrom;
      if (customTo) params.date_to = customTo;
    }
    return apiPath("/api/cost/spikes", params);
  }, [preset, customFrom, customTo]);

  const status = useApi<CostStatus>("/api/cost/status");
  const summary = useApi<CostSummary>(summaryQuery);
  const sessions = useApi<CostSessionList>(sessionsQuery);
  const spikes = useApi<CostSpikes>(spikesQuery);

  const hasFilters = preset !== "today" || appliedSearch || projectFilter;

  function resetPage() {
    setPage(0);
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="System"
        title="Cost"
        description="Which projects, sessions and models consumed AI allowance, and why. Recorded cost is the balance charge (zero for Go usage within allowance); Go allowance use itself is not retained locally."
      />

      {status.data && !status.data.available ? (
        <p className="notice notice-warning">
          Cost source unavailable: {status.data.reason} ({status.data.source_path || "no path"}). The
          dashboard shows no invented zeros.
        </p>
      ) : null}

      <div className="toolbar">
        {(["today", "yesterday", "7d", "30d", "custom"] as Preset[]).map((item) => (
          <button
            key={item}
            className={`button button-small ${preset === item ? "button-primary" : "button-ghost"}`}
            onClick={() => {
              setPreset(item);
              resetPage();
            }}
          >
            {item === "today" ? "Today" : item === "yesterday" ? "Yesterday" : item === "7d" ? "7 days" : item === "30d" ? "30 days" : "Custom"}
          </button>
        ))}
        {preset === "custom" ? (
          <>
            <label className="date-field">
              <span className="sr-only">From date</span>
              <input type="date" value={customFrom} onChange={(e) => { setCustomFrom(e.target.value); resetPage(); }} />
            </label>
            <label className="date-field">
              <span className="sr-only">To date</span>
              <input type="date" value={customTo} onChange={(e) => { setCustomTo(e.target.value); resetPage(); }} />
            </label>
          </>
        ) : null}
        <label className="search-field">
          <span className="sr-only">Search sessions</span>
          <input
            value={search}
            placeholder="Search title, directory, session…"
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setAppliedSearch(search.trim());
                resetPage();
              }
            }}
          />
        </label>
        {hasFilters ? (
          <button
            className="button button-ghost button-small"
            onClick={() => {
              setPreset("today");
              setCustomFrom(dublinToday());
              setCustomTo(dublinToday());
              setSearch("");
              setAppliedSearch("");
              setProjectFilter("");
              resetPage();
            }}
          >
            Clear filters
          </button>
        ) : null}
        <span className="toolbar-count">
          {summary.data ? `${summary.data.date_label} · ${summary.data.timezone}` : "Loading…"}
        </span>
      </div>

      {summary.loading && !summary.data ? <LoadingBlock label="Loading cost" /> : null}
      {summary.error ? <ErrorState message={summary.error.message} onRetry={summary.reload} /> : null}

      {summary.data?.available === false ? (
        <EmptyState
          title="Cost source unavailable"
          description={summary.data.reason || "OpenCode database is not readable."}
          icon={<Activity size={20} />}
        />
      ) : null}

      {summary.data?.available ? (
        <>
          <div className="stat-strip">
            <Stat label="Recorded cost" value={formatCost(summary.data.totals.recorded_cost)} detail="Local balance charge; Go allowance = $0 here" />
            <Stat label="Requests" value={formatNum(summary.data.totals.requests)} detail="Assistant model calls" />
            <Stat label="Input / output" value={`${formatNum(summary.data.totals.input)} / ${formatNum(summary.data.totals.output)}`} detail={`Reasoning ${formatNum(summary.data.totals.reasoning)}`} />
            <Stat label="Cache read / write" value={`${formatNum(summary.data.totals.cache_read)} / ${formatNum(summary.data.totals.cache_write)}`} />
            <Stat label="Failures" value={formatNum((summary.data.failures.go_limit || 0) + (summary.data.failures.no_route || 0))} detail={`Go-limit ${summary.data.failures.go_limit || 0} · no-route ${summary.data.failures.no_route || 0}`} />
          </div>

          <Section
            title="What is consuming the most?"
            description={summary.data.provenance}
          >
            {(summary.data.by_project ?? []).slice(0, 10).map((project) => (
              <p key={project.project_id || project.worktree} className="row-line">
                <button
                  className="link-button"
                  onClick={() => {
                    setProjectFilter(project.project_id || project.worktree);
                    resetPage();
                  }}
                  title={project.worktree}
                >
                  {project.worktree || project.project_id || "Unknown / unattributed"}
                </button>
                <span className="muted">
                  {" "}· {formatCost(project.recorded_cost)} · {formatNum(project.requests)} calls ·{" "}
                  {project.sessions} sessions
                </span>
              </p>
            ))}
            {(summary.data.by_project ?? []).length === 0 ? (
              <p className="muted">No projects in this period. Try a wider date range.</p>
            ) : null}
            {projectFilter ? (
              <p className="muted">
                Filtering sessions by <code>{projectFilter}</code>{" "}
                <button className="link-button" onClick={() => { setProjectFilter(""); resetPage(); }}>
                  clear
                </button>
              </p>
            ) : null}
          </Section>

          <Section title="Models" description="Provider / model as recorded locally. Zero cost does not mean zero allowance.">
            <div className="stat-strip">
              {(summary.data.by_model ?? []).slice(0, 6).map((model) => (
                <Stat
                  key={`${model.provider}/${model.model}`}
                  label={`${model.provider}/${model.model}`}
                  value={formatCost(model.recorded_cost)}
                  detail={`${formatNum(model.requests)} calls · in ${formatNum(model.input)} · cache ${formatNum(model.cache_read)}`}
                />
              ))}
            </div>
          </Section>

          <Section
            title="Investigation"
            description="Deterministic checks only — no model is called. Every finding links to the underlying records."
          >
            {spikes.loading && !spikes.data ? <LoadingBlock label="Checking spikes" compact /> : null}
            {(spikes.data?.findings ?? []).map((finding) => (
              <div key={finding.id} className="panel">
                <div className="activity-head">
                  <strong>{finding.title}</strong>
                  <Tag tone={finding.severity === "warning" ? "accent" : undefined}>{finding.severity}</Tag>
                </div>
                <p className="muted">{finding.detail}</p>
                {finding.session_ids.length > 0 ? (
                  <p className="muted">
                    Sessions:{" "}
                    {finding.session_ids.slice(0, 5).map((sid) => (
                      <span key={sid}>
                        <button className="link-button" onClick={() => setDetailId(sid)}>
                          <code>{sid.slice(0, 12)}…</code>
                        </button>{" "}
                      </span>
                    ))}
                  </p>
                ) : null}
              </div>
            ))}
          </Section>
        </>
      ) : null}

      <Section
        title="Sessions"
        description={sessions.data ? `${sessions.data.total} sessions · sorted by recorded cost` : "Sessions in the selected period"}
      >
        {sessions.loading && !sessions.data ? <LoadingBlock label="Loading sessions" /> : null}
        {sessions.error ? <ErrorState message={sessions.error.message} onRetry={sessions.reload} /> : null}
        {(sessions.data?.items ?? []).map((item: CostSession) => (
          <div key={item.session_id} className="panel">
            <div className="activity-head">
              <button className="link-button" onClick={() => setDetailId(item.session_id)} title={item.session_id}>
                <strong>{item.title || "(untitled session)"}</strong>
              </button>
              <Tag>{formatCost(item.recorded_cost)}</Tag>
              <Tag>{formatNum(item.requests)} calls</Tag>
              {item.parent_id ? <Tag>child</Tag> : null}
            </div>
            <p className="muted">
              <code>{item.session_id}</code> · {item.project_worktree || item.directory || "Unknown"} ·{" "}
              {formatMs(item.time_created)} → {formatMs(item.time_updated)}
            </p>
            <p className="muted">
              in {formatNum(item.input)} · out {formatNum(item.output)} · cache {formatNum(item.cache_read)} ·
              rollup {formatCost(item.rollup_cost)}
            </p>
          </div>
        ))}
        {(sessions.data?.items ?? []).length === 0 && !sessions.loading ? (
          <EmptyState title="No sessions match" description="Try a wider date range or clear the search." icon={<Activity size={20} />} />
        ) : null}
        {(sessions.data?.total ?? 0) > (page + 1) * limit ? (
          <div className="toolbar">
            <button className="button button-secondary button-small" onClick={() => setPage(page + 1)}>
              Load more
            </button>
          </div>
        ) : null}
      </Section>

      {detailId ? <CostDetailModal sessionId={detailId} onClose={() => setDetailId(null)} /> : null}
    </div>
  );
}

function CostDetailModal({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const detail = useApi<CostSessionDetail>(`/api/cost/sessions/${encodeURIComponent(sessionId)}`);
  return (
    <Modal title={detail.data?.title || sessionId} wide onClose={onClose}>
      {detail.loading && !detail.data ? <LoadingBlock label="Loading session" /> : null}
      {detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} /> : null}
      {detail.data?.available === false ? <p className="inline-error">{detail.data.reason}</p> : null}
      {detail.data?.available ? (
        <>
          <dl className="key-values">
            <div>
              <dt>Session</dt>
              <dd><code>{detail.data.session_id}</code></dd>
            </div>
            <div>
              <dt>Project</dt>
              <dd>{detail.data.project_worktree || detail.data.project_id || "Unknown / unattributed"}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{formatMs(detail.data.time_created)} → {formatMs(detail.data.time_updated)}</dd>
            </div>
            <div>
              <dt>Rollup vs window</dt>
              <dd>
                Rollup {formatCost(detail.data.rollup_cost)} · calls in session {detail.data.calls.length} ·
                parent {detail.data.parent_id || "—"} · children {detail.data.children.length}
              </dd>
            </div>
          </dl>
          <p className="muted">{detail.data.provenance}</p>
          <Section title="Models" description="Per-message breakdown as recorded locally.">
            {(detail.data.by_model ?? []).map((m) => (
              <p key={`${m.provider}/${m.model}`} className="row-line">
                <code>{m.provider}/{m.model}</code>
                <span className="muted"> · {formatCost(m.recorded_cost)} · {formatNum(m.requests)} calls · cache {formatNum(m.cache_read)}</span>
              </p>
            ))}
          </Section>
          <Section title="Failures" description="Go-limit, no-route and subagent errors; retries need manual review.">
            {(detail.data.failures ?? []).length === 0 ? <p className="muted">No recorded failures.</p> : null}
            {(detail.data.failures ?? []).slice(0, 20).map((f, i) => (
              <p key={`${f.seq}-${i}`} className="row-line">
                <code>seq {f.seq}</code>
                <span className="muted"> · {f.kind} · {formatMs(f.time_created)}</span>
              </p>
            ))}
          </Section>
          <Section title="Calls" description="First 50 calls in sequence order; bodies are never loaded for aggregation.">
            {(detail.data.calls ?? []).slice(0, 50).map((c) => (
              <p key={c.seq} className="row-line">
                <code>seq {c.seq}</code>
                <span className="muted"> · {c.provider}/{c.model} · {formatCost(c.cost)} · in {formatNum(c.input)} · cache {formatNum(c.cache_read)}</span>
              </p>
            ))}
          </Section>
        </>
      ) : null}
    </Modal>
  );
}
