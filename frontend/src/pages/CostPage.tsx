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
  CostAttribution,
  CostCatalogue,
  CostEfficiency,
  CostModel,
  CostProject,
  CostSession,
  CostSessionDetail,
  CostSessionList,
  CostSpikes,
  CostStatus,
  CostSummary,
} from "../types/api";

type Preset = "today" | "yesterday" | "7d" | "30d" | "custom";
type SessionSort = "cost" | "requests" | "throughput" | "input" | "cache_read" | "output" | "updated";

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

function formatTokens(value: number): string {
  const n = Number(value || 0);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

const BILLING_LABELS: Record<string, string> = {
  "go-candidate": "Go?",
  "direct-candidate": "Direct?",
  "free-candidate": "Free?",
  mixed: "Mixed",
  unknown: "Unknown",
};

function BillingBadge({ category, reason }: { category: string; reason?: string }) {
  const label = BILLING_LABELS[category] ?? category;
  const tone = category === "unknown" || category === "mixed" ? undefined : "accent";
  return (
    <span title={reason || category}>
      <Tag tone={tone}>{label}</Tag>
    </span>
  );
}

type SortDir = "asc" | "desc";

function SortHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}) {
  return (
    <button className="link-button" onClick={onClick} title={`Sort by ${label}`}>
      {label}
      {active ? (dir === "desc" ? " ↓" : " ↑") : ""}
    </button>
  );
}

function sortRows<T>(rows: T[], key: (row: T) => number, dir: SortDir): T[] {
  const indexed = rows.map((row, i) => ({ row, i }));
  indexed.sort((a, b) => {
    const diff = dir === "desc" ? key(b.row) - key(a.row) : key(a.row) - key(b.row);
    return diff !== 0 ? diff : a.i - b.i;
  });
  return indexed.map((item) => item.row);
}

export function CostPage() {
  const [preset, setPreset] = useState<Preset>("today");
  const [customFrom, setCustomFrom] = useState("2026-11-22");
  const [customTo, setCustomTo] = useState("2026-11-22");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [page, setPage] = useState(0);
  const [sessionSort, setSessionSort] = useState<SessionSort>("throughput");
  const [projectSortKey, setProjectSortKey] = useState<"throughput" | "requests" | "input" | "cache_read" | "cache_write" | "output" | "recorded_cost">("throughput");
  const [projectSortDir, setProjectSortDir] = useState<SortDir>("desc");
  const [modelSortKey, setModelSortKey] = useState<"throughput" | "requests" | "input" | "cache_read" | "cache_write" | "output" | "recorded_cost">("throughput");
  const [modelSortDir, setModelSortDir] = useState<SortDir>("desc");
  const [detailId, setDetailId] = useState<string | null>(null);
  const limit = 50;

  const boundParams = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      preset,
      timezone: "Europe/Dublin",
    };
    if (preset === "custom") {
      if (customFrom) params.date_from = customFrom;
      if (customTo) params.date_to = customTo;
    }
    return params;
  }, [preset, customFrom, customTo]);

  const summaryQuery = useMemo(() => apiPath("/api/cost/summary", boundParams), [boundParams]);

  const sessionsQuery = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      ...boundParams,
      limit,
      offset: page * limit,
      search: appliedSearch || undefined,
      project_id: projectFilter || undefined,
      sort: sessionSort,
    };
    return apiPath("/api/cost/sessions", params);
  }, [boundParams, page, appliedSearch, projectFilter, sessionSort]);

  const spikesQuery = useMemo(() => apiPath("/api/cost/spikes", boundParams), [boundParams]);
  const efficiencyQuery = useMemo(() => apiPath("/api/cost/efficiency", boundParams), [boundParams]);
  const attributionQuery = useMemo(() => apiPath("/api/cost/attribution", boundParams), [boundParams]);

  const status = useApi<CostStatus>("/api/cost/status");
  const summary = useApi<CostSummary>(summaryQuery);
  const sessions = useApi<CostSessionList>(sessionsQuery);
  const spikes = useApi<CostSpikes>(spikesQuery);
  const efficiency = useApi<CostEfficiency>(efficiencyQuery);
  const attribution = useApi<CostAttribution>(attributionQuery);
  const catalogue = useApi<CostCatalogue>("/api/cost/catalogue");

  const hasFilters = preset !== "today" || appliedSearch || projectFilter || sessionSort !== "throughput";

  function resetPage() {
    setPage(0);
  }

  function toggleProjectSort(key: typeof projectSortKey) {
    if (key === projectSortKey) {
      setProjectSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setProjectSortKey(key);
      setProjectSortDir("desc");
    }
  }

  function toggleModelSort(key: typeof modelSortKey) {
    if (key === modelSortKey) {
      setModelSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setModelSortKey(key);
      setModelSortDir("desc");
    }
  }

  const sortedProjects = useMemo(() => {
    const rows = summary.data?.by_project ?? [];
    const num = (v: unknown) => Number(v) || 0;
    const key = (row: CostProject) => {
      switch (projectSortKey) {
        case "requests": return num(row.requests);
        case "input": return num(row.input);
        case "cache_read": return num(row.cache_read);
        case "cache_write": return num(row.cache_write);
        case "output": return num(row.output);
        case "recorded_cost": return num(row.recorded_cost);
        case "throughput":
        default: return num(row.throughput);
      }
    };
    return sortRows(rows, key, projectSortDir);
  }, [summary.data, projectSortKey, projectSortDir]);

  const sortedModels = useMemo(() => {
    const rows = summary.data?.by_model ?? [];
    const num = (v: unknown) => Number(v) || 0;
    const key = (row: CostModel) => {
      switch (modelSortKey) {
        case "requests": return num(row.requests);
        case "input": return num(row.input);
        case "cache_read": return num(row.cache_read);
        case "cache_write": return num(row.cache_write);
        case "output": return num(row.output);
        case "recorded_cost": return num(row.recorded_cost);
        case "throughput":
        default: return num(row.throughput);
      }
    };
    return sortRows(rows, key, modelSortDir);
  }, [summary.data, modelSortKey, modelSortDir]);

  return (
    <div className="page">
      <PageHeader
        eyebrow="System"
        title="Cost"
        description="AI resource consumption by project, session, model and provider. Cost is secondary: recorded dollars are the balance charge (zero for Go usage within allowance); throughput and cache behaviour show the real load."
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
        <label className="select-field">
          <span className="sr-only">Sort sessions</span>
          <select value={sessionSort} onChange={(e) => { setSessionSort(e.target.value as SessionSort); resetPage(); }}>
            <option value="throughput">Sort: throughput</option>
            <option value="requests">Sort: requests</option>
            <option value="cost">Sort: recorded cost</option>
            <option value="input">Sort: uncached input</option>
            <option value="cache_read">Sort: cached reads</option>
            <option value="output">Sort: output</option>
            <option value="updated">Sort: recently active</option>
          </select>
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
              setSessionSort("throughput");
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
            <Stat label="Throughput" value={formatTokens(summary.data.totals.throughput)} detail={`in ${formatTokens(summary.data.totals.input)} · cache ${formatTokens(summary.data.totals.cache_read)} · out ${formatTokens(summary.data.totals.output)}`} />
            <Stat label="Requests" value={formatNum(summary.data.totals.requests)} detail="Assistant model calls" />
            <Stat label="Recorded cost" value={formatCost(summary.data.totals.recorded_cost)} detail="Balance charge; Go allowance = $0 here" />
            <Stat label="Cache read / write" value={`${formatTokens(summary.data.totals.cache_read)} / ${formatTokens(summary.data.totals.cache_write)}`} detail={`Reasoning ${formatTokens(summary.data.totals.reasoning)} (diagnostic, in throughput via output)`} />
            <Stat label="Failures" value={formatNum((summary.data.failures.go_limit || 0) + (summary.data.failures.no_route || 0))} detail={`Go-limit ${summary.data.failures.go_limit || 0} · no-route ${summary.data.failures.no_route || 0}`} />
          </div>

          <Section
            title="Top consumers"
            description="Sortable by every token category. Throughput = uncached input + output + cached reads + writes (provider accounting; reasoning shown separately). Cached tokens are reused context, not newly processed input."
          >
            <div className="toolbar" aria-label="Sort projects">
              <span className="toolbar-count">Sort projects:</span>
              {(["throughput", "requests", "input", "cache_read", "output", "recorded_cost"] as const).map((key) => (
                <SortHeader
                  key={key}
                  label={key === "recorded_cost" ? "cost" : key}
                  active={projectSortKey === key}
                  dir={projectSortDir}
                  onClick={() => toggleProjectSort(key)}
                />
              ))}
            </div>
            {sortedProjects.slice(0, 10).map((project) => (
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
                  {" "}· {formatTokens(project.throughput)} tokens · {formatNum(project.requests)} calls ·{" "}
                  {formatTokens(project.input)} new in · {formatTokens(project.cache_read)} cached · {formatCost(project.recorded_cost)}
                </span>
              </p>
            ))}
            {sortedProjects.length === 0 ? (
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

          <Section
            title="Models"
            description="Actual provider / model recorded per request, not the selected default. Billing badges are heuristic: authoritative billing_source is not retained locally, so Unknown stays Unknown."
          >
            <div className="toolbar" aria-label="Sort models">
              <span className="toolbar-count">Sort models:</span>
              {(["throughput", "requests", "input", "cache_read", "output", "recorded_cost"] as const).map((key) => (
                <SortHeader
                  key={key}
                  label={key === "recorded_cost" ? "cost" : key}
                  active={modelSortKey === key}
                  dir={modelSortDir}
                  onClick={() => toggleModelSort(key)}
                />
              ))}
            </div>
            <div className="stat-strip">
              {sortedModels.slice(0, 6).map((model) => (
                <Stat
                  key={`${model.provider}/${model.model}`}
                  label={`${model.provider}/${model.model}`}
                  value={formatTokens(model.throughput)}
                  detail={`${formatNum(model.requests)} calls · new ${formatTokens(model.input)} · cached ${formatTokens(model.cache_read)} · ${formatCost(model.recorded_cost)}`}
                />
              ))}
            </div>
            {sortedModels.slice(0, 12).map((model) => (
              <p key={`${model.provider}/${model.model}`} className="row-line">
                <code>{model.provider}/{model.model}</code>{" "}
                <BillingBadge category={model.billing_category} reason={model.billing_reason} />
                <span className="muted">
                  {" "}· {formatTokens(model.throughput)} tokens · {formatNum(model.requests)} calls · {formatCost(model.recorded_cost)}
                </span>
              </p>
            ))}
            <p className="muted">
              Go? = likely Go allowance route · Direct? = likely separately billed · Free? = free-candidate ·
              Mixed/Unknown = see reason. Zero dollars never implies a route on its own.
              {catalogue.data && !catalogue.data.go_available ? ` Catalogue: ${catalogue.data.go_detail}` : null}
              {catalogue.data?.pi_available ? ` Pi lists ${catalogue.data.pi_models.length} model(s).` : null}
            </p>
          </Section>

          <Section
            title="Model efficiency"
            description="Advisory only. No model is switched, no paid call is made, nothing is reconfigured. Verify quality and latency on a sample before moving anything."
          >
            {efficiency.loading && !efficiency.data ? <LoadingBlock label="Checking efficiency" compact /> : null}
            {efficiency.error && !efficiency.data ? (
              <p className="muted">Model efficiency data unavailable: the backend does not provide this feature.</p>
            ) : null}
            {efficiency.data?.available === false ? <p className="muted">{efficiency.data.reason}</p> : null}
            {(efficiency.data?.recommendations ?? []).length === 0 && !efficiency.loading ? (
              <p className="muted">No high-usage workloads in this window.</p>
            ) : null}
            {(efficiency.data?.recommendations ?? []).map((rec) => (
              <div key={rec.id} className="panel">
                <div className="activity-head">
                  <strong>{rec.title}</strong>
                  <BillingBadge category={rec.billing_category} />
                  <Tag tone={rec.severity === "warning" ? "accent" : undefined}>{rec.severity}</Tag>
                </div>
                <p className="muted">{rec.detail}</p>
                {rec.session_ids.length > 0 ? (
                  <p className="muted">
                    Evidence:{" "}
                    {rec.session_ids.slice(0, 5).map((sid) => (
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

          <Section
            title="Attribution"
            description="Which calls cannot be tied to a project. Unknown is labelled Unknown, never guessed."
          >
            {attribution.loading && !attribution.data ? <LoadingBlock label="Checking attribution" compact /> : null}
            {attribution.error && !attribution.data ? (
              <p className="muted">Attribution data unavailable: the backend does not provide this feature.</p>
            ) : null}
            {attribution.data?.available ? (
              <>
                <p className="muted">
                  {formatNum(attribution.data.unknown_requests)} requests in {formatNum(attribution.data.unknown_sessions)}{" "}
                  session(s) are unattributed in this window. Direct application calls that bypass OpenCode sessions
                  leave no local rows at all.
                </p>
                <p className="muted">Missing before any caller can be identified: {attribution.data.missing.slice(0, 3).join("; ")}…</p>
              </>
            ) : null}
          </Section>
        </>
      ) : null}

      <Section
        title="Sessions"
        description={sessions.data ? `${sessions.data.total} sessions · sorted by ${sessionSort}` : "Sessions in the selected period"}
      >
        {sessions.loading && !sessions.data ? <LoadingBlock label="Loading sessions" /> : null}
        {sessions.error ? <ErrorState message={sessions.error.message} onRetry={sessions.reload} /> : null}
        {(sessions.data?.items ?? []).map((item: CostSession) => (
          <div key={item.session_id} className="panel">
            <div className="activity-head">
              <button className="link-button" onClick={() => setDetailId(item.session_id)} title={item.session_id}>
                <strong>{item.title || "(untitled session)"}</strong>
              </button>
              <BillingBadge category={item.billing_category} reason={item.billing_reason} />
              <Tag>{formatTokens(item.throughput)}</Tag>
              <Tag>{formatNum(item.requests)} calls</Tag>
              {item.parent_id ? <Tag>child</Tag> : null}
            </div>
            <p className="muted">
              <code>{item.session_id}</code> · {item.project_worktree || item.directory || "Unknown"} ·{" "}
              {item.agent ? `${item.agent} · ` : ""}{formatMs(item.time_created)} → {formatMs(item.time_updated)}
            </p>
            <p className="muted">
              new {formatTokens(item.input)} · cached {formatTokens(item.cache_read)} · out {formatTokens(item.output)} ·{" "}
              {formatCost(item.recorded_cost)}
              {(item.models ?? []).length > 1 ? ` · models: ${(item.models ?? []).map((m) => m.split("/")[1] ?? m).join(", ")}` : null}
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

      {detailId ? (
        <CostDetailModal sessionId={detailId} onClose={() => setDetailId(null)} onNavigate={setDetailId} />
      ) : null}
    </div>
  );
}

function CostDetailModal({
  sessionId,
  onClose,
  onNavigate,
}: {
  sessionId: string;
  onClose: () => void;
  onNavigate: (sessionId: string) => void;
}) {
  const detail = useApi<CostSessionDetail>(`/api/cost/sessions/${encodeURIComponent(sessionId)}`);
  const d = detail.data;
  return (
    <Modal title={d?.title || sessionId} wide onClose={onClose}>
      {detail.loading && !d ? <LoadingBlock label="Loading session" /> : null}
      {detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} /> : null}
      {d && !d.available ? <p className="inline-error">{d.reason}</p> : null}
      {d?.available ? (
        <>
          <dl className="key-values">
            <div>
              <dt>Session</dt>
              <dd><code>{d.session_id}</code></dd>
            </div>
            <div>
              <dt>Project</dt>
              <dd>{d.project_worktree || d.project_id || "Unknown / unattributed"}</dd>
            </div>
            <div>
              <dt>Agent / billing</dt>
              <dd>
                {d.agent || "—"}{" "}
                <BillingBadge category={d.by_model[0]?.billing_category ?? "unknown"} reason={d.by_model[0]?.billing_reason} />
              </dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{formatMs(d.time_created)} → {formatMs(d.time_updated)}</dd>
            </div>
            <div>
              <dt>Family</dt>
              <dd>
                parent{" "}
                {d.parent_id ? (
                  <button className="link-button" onClick={() => d.parent_id && onNavigate(d.parent_id)}>
                    <code>{d.parent_id.slice(0, 12)}…</code>
                  </button>
                ) : (
                  "—"
                )}{" "}
                · children {d.children.length}
                {d.children.length > 0 ? (
                  <>
                    {": "}
                    {d.children.slice(0, 5).map((child) => (
                      <span key={child}>
                        <button className="link-button" onClick={() => onNavigate(child)}>
                          <code>{child.slice(0, 12)}…</code>
                        </button>{" "}
                      </span>
                    ))}
                  </>
                ) : null}
              </dd>
            </div>
            <div>
              <dt>Rollup vs window</dt>
              <dd>
                Rollup {formatCost(d.rollup_cost)} · calls in session {d.calls.length} ·
                throughput {formatTokens(d.calls.reduce((n, c) => n + (c.throughput || 0), 0))}
              </dd>
            </div>
          </dl>
          <p className="muted">{d.provenance}</p>
          <Section title="Models" description="Actual provider / model recorded per request.">
            {(d.by_model ?? []).map((m) => (
              <p key={`${m.provider}/${m.model}`} className="row-line">
                <code>{m.provider}/{m.model}</code>{" "}
                <BillingBadge category={m.billing_category} reason={m.billing_reason} />
                <span className="muted"> · {formatTokens(m.throughput)} tokens · {formatNum(m.requests)} calls · cache {formatTokens(m.cache_read)} · {formatCost(m.recorded_cost)}</span>
              </p>
            ))}
          </Section>
          <Section title="Failures" description="Go-limit, no-route and subagent errors; retries need manual review.">
            {(d.failures ?? []).length === 0 ? <p className="muted">No recorded failures.</p> : null}
            {(d.failures ?? []).slice(0, 20).map((f, i) => (
              <p key={`${f.seq}-${i}`} className="row-line">
                <code>seq {f.seq}</code>
                <span className="muted"> · {f.kind} · {formatMs(f.time_created)}</span>
              </p>
            ))}
          </Section>
          <Section title="Calls" description="First 50 calls in sequence order; bodies are never loaded for aggregation.">
            {(d.calls ?? []).slice(0, 50).map((c) => (
              <p key={c.seq} className="row-line">
                <code>seq {c.seq}</code>
                <span className="muted"> · {c.provider}/{c.model} · {formatTokens(c.throughput)} tokens · in {formatTokens(c.input)} · cache {formatTokens(c.cache_read)} · {formatCost(c.cost)}</span>
              </p>
            ))}
          </Section>
        </>
      ) : null}
    </Modal>
  );
}
