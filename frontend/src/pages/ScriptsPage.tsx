import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Archive, CheckCircle2, Eye, RefreshCw, Search } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import { formatDateTime } from "../lib/format";
import type { CultivationGoal, IntelligenceCoverage, LibrarySynthesis, ScriptBatch, ScriptCandidate, ScriptContent, ScriptMigration, ScriptRecord, ScriptRelationship, ScriptReview, ScriptStatus, ScriptWork } from "../types/api";

const STATUSES = ["discovered", "draft", "in_review", "ready", "completed"] as const;

function numericKey(row: ScriptRecord): number {
  if (row.script_number === null || row.script_number === undefined) return Number.MAX_SAFE_INTEGER;
  return row.script_number;
}

function weekLabel(status: ScriptStatus | null): string {
  return status?.week?.label ?? "";
}

export function ScriptsPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const status = useApi<ScriptStatus>("/api/scripts/status");
  const goals = useApi<CultivationGoal[]>("/api/cultivation/goals");
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [statusFilter, setStatusFilter] = useState(params.get("status") ?? "");
  const [completionFilter, setCompletionFilter] = useState(params.get("completed") ?? "all");
  const [showMissing, setShowMissing] = useState(params.get("missing") !== "hide");
  const [duplicatesOnly, setDuplicatesOnly] = useState(params.get("duplicates") === "only");
  const [sort, setSort] = useState<"number" | "modified">((params.get("sort") as "number" | "modified") || "number");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(params.get("id"));
  const [bulkStatus, setBulkStatus] = useState("ready");
  const [bulkHistorical, setBulkHistorical] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(
    () =>
      apiPath("/api/scripts", {
        status: statusFilter || undefined,
        search: search.trim() || undefined,
        completed: completionFilter === "completed" ? true : completionFilter === "incomplete" ? false : undefined,
        duplicate: duplicatesOnly ? true : undefined,
        limit: 500,
      }),
    [statusFilter, search, completionFilter, duplicatesOnly],
  );
  const scripts = useApi<ScriptRecord[]>(query);

  useEffect(() => {
    const next: Record<string, string> = {};
    if (search.trim()) next.search = search.trim();
    if (statusFilter) next.status = statusFilter;
    if (completionFilter !== "all") next.completed = completionFilter;
    if (!showMissing) next.missing = "hide";
    if (duplicatesOnly) next.duplicates = "only";
    if (sort !== "number") next.sort = sort;
    if (detailId) next.id = detailId;
    setParams(next, { replace: true });
  }, [search, statusFilter, completionFilter, showMissing, duplicatesOnly, sort, detailId, setParams]);

  const visible = useMemo(() => {
    const rows = [...(scripts.data ?? [])];
    const filtered = rows.filter((row) => (showMissing ? true : !row.missing));
    filtered.sort((a, b) => {
      if (sort === "modified") return (b.mtime_ns || 0) - (a.mtime_ns || 0);
      const diff = numericKey(a) - numericKey(b);
      if (diff !== 0) return diff;
      return a.current_relpath.localeCompare(b.current_relpath);
    });
    return filtered;
  }, [scripts.data, showMissing, sort]);

  const counts = status.data?.counts;
  const weekly = useMemo(
    () => (goals.data ?? []).find((goal) => goal.id === "weekly_script") ?? null,
    [goals.data],
  );

  async function sync() {
    setSyncing(true);
    setError(null);
    try {
      await api.post("/api/scripts/sync");
      toast.push("success", "Library synced");
      status.reload();
      scripts.reload();
      goals.reload();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Sync failed", message);
    } finally {
      setSyncing(false);
    }
  }

  async function setLifecycle(id: string, next: string, note = "") {
    try {
      await api.patch(`/api/scripts/${id}/status`, { status: next, note });
      toast.push("success", `Marked ${next.replace(/_/g, " ")}`);
      scripts.reload();
      status.reload();
      goals.reload();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  async function setArchived(id: string, archived: boolean) {
    try {
      await api.patch(`/api/scripts/${id}/archive`, { archived });
      toast.push("success", archived ? "Archived" : "Restored");
      scripts.reload();
      status.reload();
    } catch (caught) {
      toast.push("error", "Archive failed", errorMessage(caught));
    }
  }

  async function bulkApply(event: FormEvent) {
    event.preventDefault();
    if (selected.size === 0) {
      toast.push("info", "Select at least one script");
      return;
    }
    try {
      const result = await api.post<{ count: number; skipped: string[] }>("/api/scripts/bulk/status", {
        script_ids: [...selected],
        status: bulkStatus,
        as_historical: bulkStatus === "completed" ? bulkHistorical : false,
        note: bulkStatus === "completed" && bulkHistorical ? "Historical baseline; classified in bulk." : "",
      });
      toast.push("success", `Updated ${result.count} script${result.count === 1 ? "" : "s"}`);
      setSelected(new Set());
      scripts.reload();
      status.reload();
      goals.reload();
    } catch (caught) {
      toast.push("error", "Bulk update failed", errorMessage(caught));
    }
  }

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const stale = status.data?.status === "stale" || status.data?.status === "unavailable";

  return (
    <div className="page cultivation-scope">
      <PageHeader
        eyebrow="Cultivation"
        title="Scripts"
        description="Your actual script collection. Existence is inventory; only explicit acceptance counts as completed."
        actions={
          <>
            <span className="toolbar-count">
              {stale ? "Stale — last known kept" : status.data?.status === "never_synced" ? "Never synced" : `Synced ${status.data?.last_sync_at ? formatDateTime(status.data.last_sync_at) : "—"}`}
            </span>
            <button className="button button-secondary button-small" onClick={() => void sync()} disabled={syncing}>
              <RefreshCw size={14} /> {syncing ? "Syncing…" : "Sync library"}
            </button>
          </>
        }
      />
      {status.error ? <ErrorState message={status.error.message} onRetry={status.reload} /> : null}
      {status.data && !status.data.exists ? (
        <p className="notice notice-warning">Script directory unavailable: {status.data.last_error ?? status.data.root}. Last known counts preserved.</p>
      ) : null}
      {stale && status.data?.exists ? (
        <p className="notice notice-warning">Source data is stale — showing the last known observation. Sync to refresh.</p>
      ) : null}
      <InlineError message={error} />

      <div className="stat-strip">
        <Stat label="Discovered" value={counts?.total ?? "—"} />
        <Stat label="Completed" value={`${counts?.completed ?? "—"} / 100`} />
        <Stat label="Ready" value={counts?.ready ?? counts?.by_status?.ready ?? "—"} />
        <Stat label="Needs review" value={counts?.needs_review ?? "—"} />
        <Stat label="Missing" value={counts?.missing ?? "—"} />
        <Stat label="This week" value={`${weekly?.progress?.current ?? 0} / 1 · ${weekLabel(status.data)}`} />
      </div>
      <p className="muted">
        Root: <code>{status.data?.root ?? "—"}</code>
        {status.data?.last_sync_at ? ` · Last sync ${formatDateTime(status.data.last_sync_at)}` : " · Never synced"}
      </p>

      <Section
        title="Library"
        description="Numeric sort puts Script002 before Script010. Duplicates are warnings, never merges."
        actions={
          <span className="toolbar-count">
            {visible.length} shown{selected.size ? ` · ${selected.size} selected` : ""}
          </span>
        }
      >
        <div className="toolbar">
          <label className="search-field">
            <Search size={15} aria-hidden="true" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title or filename" aria-label="Search scripts" />
          </label>
          <label className="select-field">
            <span className="sr-only">Filter by lifecycle</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All lifecycles</option>
              {STATUSES.map((item) => (
                <option value={item} key={item}>
                  {item.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="select-field">
            <span className="sr-only">Filter by completion</span>
            <select value={completionFilter} onChange={(event) => setCompletionFilter(event.target.value)}>
              <option value="all">Completed + incomplete</option>
              <option value="completed">Completed only</option>
              <option value="incomplete">Incomplete only</option>
            </select>
          </label>
          <label className="select-field">
            <span className="sr-only">Sort order</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as "number" | "modified")}>
              <option value="number">Sort: number</option>
              <option value="modified">Sort: modified</option>
            </select>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showMissing} onChange={(event) => setShowMissing(event.target.checked)} /> Show missing
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={duplicatesOnly} onChange={(event) => setDuplicatesOnly(event.target.checked)} /> Duplicates only
          </label>
        </div>

        <form className="inline-form" onSubmit={(event) => void bulkApply(event)}>
          <select value={bulkStatus} onChange={(event) => setBulkStatus(event.target.value)} aria-label="Bulk lifecycle">
            {STATUSES.map((item) => (
              <option value={item} key={item}>
                Mark {item.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          {bulkStatus === "completed" ? (
            <label className="checkbox">
              <input type="checkbox" checked={bulkHistorical} onChange={(event) => setBulkHistorical(event.target.checked)} /> Historical baseline (no weekly credit)
            </label>
          ) : null}
          <button className="button button-primary button-small" type="submit" disabled={selected.size === 0}>
            Apply to {selected.size || "selection"}
          </button>
        </form>

        {scripts.loading && !scripts.data ? <LoadingBlock label="Loading scripts" compact /> : null}
        {scripts.error ? <ErrorState message={scripts.error.message} onRetry={scripts.reload} /> : null}
        {visible.length === 0 && !scripts.loading ? (
          <EmptyState title="No scripts" description="Sync the library or clear the filters." icon={<Eye size={20} />} />
        ) : null}
        {visible.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th aria-label="Select"><input type="checkbox" checked={selected.size > 0 && selected.size === visible.length} onChange={() => setSelected(selected.size === visible.length ? new Set() : new Set(visible.map((row) => row.id)))} aria-label="Select all shown" /></th>
                  <th>Number</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Modified</th>
                  <th>Review</th>
                  <th>Completed</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id} className={row.missing ? "row-muted" : undefined}>
                    <td><input type="checkbox" checked={selected.has(row.id)} onChange={() => toggle(row.id)} aria-label={`Select ${row.title}`} /></td>
                    <td>{row.script_number ?? "—"}</td>
                    <td>
                      <button className="link-button" onClick={() => setDetailId(row.id)}>
                        <strong>{row.title}</strong>
                      </button>
                      <div className="muted small"><code>{row.current_relpath}</code></div>
                      {row.missing ? <Tag>Missing</Tag> : null}
                      {row.archived ? <Tag>Archived</Tag> : null}
                      {row.duplicate_number_group || row.duplicate_content_group ? (
                        <span className="warn-text small"> <AlertTriangle size={12} /> duplicate candidate</span>
                      ) : null}
                    </td>
                    <td>{row.status.replace(/_/g, " ")}</td>
                    <td title={formatDateTime(row.last_seen_at)}>{row.mtime_ns ? new Date(row.mtime_ns / 1e6).toLocaleDateString() : "—"}</td>
                    <td>{row.latest_review ? (row.latest_review.freshness === "CURRENT" ? "Reviewed" : "Stale review") : "Not reviewed"}</td>
                    <td>{row.completed_at ? formatDateTime(row.completed_at) : "—"}</td>
                    <td>
                      <div className="activity-actions">
                        <button className="button button-ghost button-small" onClick={() => setDetailId(row.id)}>Open</button>
                        {row.status !== "completed" ? (
                          <button className="button button-ghost button-small" onClick={() => void setLifecycle(row.id, "completed", "Explicit acceptance from library.")}>
                            <CheckCircle2 size={13} /> Complete
                          </button>
                        ) : null}
                        <button className="button button-ghost button-small" onClick={() => void setArchived(row.id, !row.archived)}>
                          <Archive size={13} /> {row.archived ? "Restore" : "Archive"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Section>

      {detailId ? (
        <ScriptDetail
          id={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => {
            scripts.reload();
            status.reload();
            goals.reload();
          }}
        />
      ) : null}

      <OrganiseSection
        onChanged={() => {
          scripts.reload();
          status.reload();
          goals.reload();
        }}
      />

      <IntelligenceSection
        onChanged={() => {
          scripts.reload();
          status.reload();
          goals.reload();
        }}
      />

      <CandidateSection
        onChanged={() => {
          scripts.reload();
          status.reload();
          goals.reload();
        }}
      />
    </div>
  );
}

function ScriptDetail(props: { id: string; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const detail = useApi<ScriptRecord>(`/api/scripts/${props.id}`);
  const content = useApi<ScriptContent>(`/api/scripts/${props.id}/content`);
  const reviews = useApi<{ reviews: ScriptReview[] }>(`/api/scripts/${props.id}/reviews`);
  const [reviewing, setReviewing] = useState(false);
  const [usageCount, setUsageCount] = useState("");
  const [rating, setRating] = useState("");
  const [target, setTarget] = useState("");
  const [effect, setEffect] = useState("");

  async function lifecycle(next: string) {
    try {
      await api.patch(`/api/scripts/${props.id}/status`, { status: next, note: `Explicit ${next} from detail view.` });
      toast.push("success", `Marked ${next.replace(/_/g, " ")}`);
      detail.reload();
      content.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  async function requestReview() {
    setReviewing(true);
    try {
      await api.post(`/api/scripts/${props.id}/reviews`, {});
      toast.push("success", "AI review recorded");
      detail.reload();
      reviews.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Review failed", errorMessage(caught));
    } finally {
      setReviewing(false);
    }
  }

  async function saveEffectiveness(event: FormEvent) {
    event.preventDefault();
    try {
      await api.patch(`/api/scripts/${props.id}/effectiveness`, {
        usage_count: usageCount === "" ? undefined : Number(usageCount),
        personal_rating: rating === "" ? undefined : Number(rating),
        personal_target: target || undefined,
        personal_effect: effect || undefined,
      });
      toast.push("success", "Effectiveness recorded — your judgement, not the AI's");
      setUsageCount("");
      setRating("");
      setTarget("");
      setEffect("");
      detail.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Save failed", errorMessage(caught));
    }
  }

  async function archive(next: boolean) {
    try {
      await api.patch(`/api/scripts/${props.id}/archive`, { archived: next });
      toast.push("success", next ? "Archived" : "Restored");
      detail.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Archive failed", errorMessage(caught));
    }
  }

  const row = detail.data;
  return (
    <Section
      title={row ? row.title : "Script detail"}
      description={row ? `${row.current_relpath} · ${row.id}` : "Loading script record."}
      actions={
        <button className="button button-ghost button-small" onClick={props.onClose}>
          Close
        </button>
      }
    >
      {detail.loading && !row ? <LoadingBlock label="Loading script" compact /> : null}
      {detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} /> : null}
      {row ? (
        <>
          <div className="stat-strip">
            <Stat label="Number" value={row.script_number ?? "—"} />
            <Stat label="Lifecycle" value={row.status.replace(/_/g, " ")} />
            <Stat label="Completed" value={row.completed_at ? formatDateTime(row.completed_at) : "—"} />
            <Stat label="Review" value={row.review_status} />
          </div>
          <p className="muted">
            Filename: <code>{row.current_relpath}</code> · Original: <code>{row.original_relpath}</code>
            <br />
            Fingerprint: <code>{row.content_sha256.slice(0, 16)}…</code> · Size {row.file_size} bytes
            {row.missing ? " · Missing from scan" : ""} {row.archived ? " · Archived" : ""}
          </p>
          {row.duplicate_number_group || row.duplicate_content_group ? (
            <p className="notice notice-warning">
              <AlertTriangle size={13} /> Shares {row.duplicate_number_group ? "a script number" : ""}{row.duplicate_number_group && row.duplicate_content_group ? " and " : ""}{row.duplicate_content_group ? "identical content" : ""} with {(row.duplicate_number_group ?? row.duplicate_content_group ?? []).filter((id) => id !== row.id).length} other record(s). Related, never merged.
            </p>
          ) : null}
          <div className="toolbar">
            {(["draft", "in_review", "ready", "completed"] as const).map((next) =>
              next === row.status ? null : (
                <button key={next} className="button button-secondary button-small" onClick={() => void lifecycle(next)}>
                  Mark {next.replace(/_/g, " ")}
                </button>
              ),
            )}
            <button className="button button-ghost button-small" onClick={() => void archive(!row.archived)}>
              {row.archived ? "Restore" : "Archive"}
            </button>
          </div>
          <h4>Preview</h4>
          {content.loading && !content.data ? <LoadingBlock label="Loading preview" compact /> : null}
          {content.data ? (
            <pre className="code-block">{content.data.content.slice(0, 8000)}{content.data.truncated ? "\n…(truncated)" : ""}</pre>
          ) : null}
          <h4>History</h4>
          {(row.events ?? []).slice(0, 20).map((event) => (
            <p key={event.id} className="row-line">
              <span className="tag">{event.event_type.replace(/_/g, " ")}</span>{" "}
              {event.from_value || event.to_value ? (
                <span className="muted">{event.from_value ?? "—"} → {event.to_value ?? "—"}</span>
              ) : null}{" "}
              {event.note ? <span>{event.note}</span> : null}{" "}
              <span className="muted">{formatDateTime(event.created_at)}</span>
            </p>
          ))}

          <h4>AI review</h4>
          {row.latest_review ? (
            <p className="muted">
              Latest: {row.latest_review.freshness === "CURRENT" ? <Tag tone="accent">Current</Tag> : <Tag>Stale</Tag>}{" "}
              {row.latest_review.readiness ? <span>Readiness: <strong>{String(row.latest_review.readiness).replace(/_/g, " ")}</strong></span> : null}{" "}
              <span className="muted">· {row.latest_review.model} · {formatDateTime(row.latest_review.created_at)}</span>
              {row.latest_review.purpose ? <><br />Purpose: {row.latest_review.purpose}</> : null}
            </p>
          ) : (
            <p className="muted">Not reviewed — no scores assigned until Pi has assessed this script.</p>
          )}
          <div className="toolbar">
            <button className="button button-secondary button-small" onClick={() => void requestReview()} disabled={reviewing}>
              {reviewing ? "Reviewing…" : "Request AI review"}
            </button>
            <span className="muted small">Read-only: reviews never modify the script, its status, or completion.</span>
          </div>
          {(reviews.data?.reviews ?? []).slice(0, 5).map((review) => (
            <div key={review.id} className="panel review-card">
              <div className="activity-head">
                <strong>{review.freshness === "CURRENT" ? "Current review" : "Stale review"}</strong>
                {review.freshness === "CURRENT" ? <Tag tone="accent">Current</Tag> : <Tag>Stale — script changed since</Tag>}
                <span className="muted">{review.model} · {formatDateTime(review.created_at)}</span>
              </div>
              <p><strong>Purpose:</strong> {String(review.assessment.purpose ?? "—")}</p>
              <p><strong>Strengths:</strong> {(Array.isArray(review.assessment.strengths) ? review.assessment.strengths : []).join("; ") || "—"}</p>
              <p><strong>Weaknesses:</strong> {(Array.isArray(review.assessment.weaknesses) ? review.assessment.weaknesses : []).join("; ") || "—"}</p>
              <p><strong>Suggested changes:</strong> {(Array.isArray(review.assessment.suggested_changes) ? review.assessment.suggested_changes : []).join("; ") || "—"}</p>
              <p className="muted">
                Suitability: {String(review.assessment.suitability ?? "—")} · Readiness: {String(review.assessment.readiness ?? "—").replace(/_/g, " ")} ·
                Duration: {typeof review.assessment.estimated_spoken_seconds === "number" ? `${review.assessment.estimated_spoken_seconds}s (AI)` : "—"}
                {typeof review.assessment.rule_spoken_seconds === "number" ? ` / ${review.assessment.rule_spoken_seconds}s (150 wpm rule)` : ""}
              </p>
            </div>
          ))}

          <h4>Personal effectiveness</h4>
          <p className="muted">
            {row.usage_count > 0 || row.personal_rating != null || row.personal_target || row.personal_effect
              ? <>Listens: <strong>{row.usage_count}</strong>
                {row.personal_rating != null ? <> · Rating: <strong>{row.personal_rating}/5</strong></> : null}
                {row.personal_target ? <> · Target: <strong>{row.personal_target}</strong></> : null}
                {row.personal_effect ? <> · Effect: <strong>{row.personal_effect}</strong></> : null}
                {row.last_used_at ? <> · Last used {formatDateTime(row.last_used_at)}</> : null}</>
              : "Not measured — only your experience can establish whether a script works."}
          </p>
          <form className="inline-form" onSubmit={(event) => void saveEffectiveness(event)}>
            <input value={usageCount} onChange={(event) => setUsageCount(event.target.value)} placeholder="Listens" inputMode="numeric" aria-label="Listen count" />
            <input value={rating} onChange={(event) => setRating(event.target.value)} placeholder="Rating 1–5" inputMode="decimal" aria-label="Personal rating" />
            <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Target (awareness, focus…)" aria-label="Personal target" />
            <input value={effect} onChange={(event) => setEffect(event.target.value)} placeholder="Effect (calmer, focused…)" aria-label="Personal effect" />
            <button className="button button-primary button-small" type="submit">
              Record effectiveness
            </button>
          </form>
        </>
      ) : null}
    </Section>
  );
}

const RELATIONSHIP_KINDS = ["exact_duplicate", "possible_duplicate", "revision", "alternate", "independent"] as const;

function OrganiseSection(props: { onChanged: () => void }) {
  const toast = useToast();
  const [relationships, setRelationships] = useState<ScriptRelationship[] | null>(null);
  const [works, setWorks] = useState<{ works: ScriptWork[]; work_count: number; file_count: number; completed_files: number; completed_works: number } | null>(null);
  const [migrations, setMigrations] = useState<ScriptMigration[] | null>(null);
  const [preview, setPreview] = useState<{ migration_id: string; manifest_hash: string; manifest: { items: Array<{ id: string; current: string; proposed: string; current_number: number | null; proposed_number: number; sha256: string; status: string }>; references: Array<{ source: string; line: number; match: string }>; collisions: Array<{ destination: string; reason: string }> } } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmKind, setConfirmKind] = useState<string>("alternate");

  async function loadAll() {
    try {
      const [rel, wrk, mig] = await Promise.all([
        api.get<{ relationships: ScriptRelationship[] }>("/api/scripts/relationships"),
        api.get<{ works: ScriptWork[]; work_count: number; file_count: number; completed_files: number; completed_works: number }>("/api/scripts/works"),
        api.get<{ migrations: ScriptMigration[] }>("/api/scripts/migrations"),
      ]);
      setRelationships(rel.relationships);
      setWorks(wrk);
      setMigrations(mig.migrations);
    } catch (caught) {
      toast.push("error", "Organise data failed", errorMessage(caught));
    }
  }

  async function discover() {
    setBusy("discover");
    try {
      await api.post("/api/scripts/relationships/discover");
      toast.push("success", "Relationship proposals refreshed");
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Discovery failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function confirm(rel: ScriptRelationship) {
    setBusy(`confirm-${rel.source_id}-${rel.target_id}`);
    try {
      await api.post("/api/scripts/relationships/confirm", {
        source_id: rel.source_id,
        target_id: rel.target_id,
        kind: rel.kind === "possible_duplicate" ? confirmKind : rel.kind,
        confirmed: true,
        note: "Confirmed from Scripts library.",
      });
      toast.push("success", "Relationship confirmed");
      await loadAll();
    } catch (caught) {
      toast.push("error", "Confirm failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function plan() {
    setBusy("preview");
    try {
      const result = await api.post<{ migration_id: string; manifest_hash: string; manifest: OrganisePreviewManifest }>("/api/scripts/migrations/preview");
      setPreview(result);
      toast.push("success", "Migration preview ready — no files changed");
      await loadAll();
    } catch (caught) {
      toast.push("error", "Preview failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!preview) return;
    setBusy("approve");
    try {
      await api.post(`/api/scripts/migrations/${preview.migration_id}/approve`, { expected_hash: preview.manifest_hash });
      toast.push("success", "Migration approved — fingerprints bound");
      await loadAll();
    } catch (caught) {
      toast.push("error", "Approval failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function apply() {
    if (!preview) return;
    if (!window.confirm("Apply this migration? Files will be renamed; registry identities are preserved.")) return;
    setBusy("apply");
    try {
      await api.post(`/api/scripts/migrations/${preview.migration_id}/apply`, { expected_hash: preview.manifest_hash });
      toast.push("success", "Migration applied");
      setPreview(null);
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Apply failed — no silent continuation; check history", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function rollback(id: string) {
    if (!window.confirm("Roll back this migration to the original filenames?")) return;
    setBusy(`rollback-${id}`);
    try {
      await api.post(`/api/scripts/migrations/${id}/rollback`);
      toast.push("success", "Migration rolled back");
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Rollback failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Organise library"
      description="Preview-first renumbering. Relationships are proposals until confirmed; nothing is merged or deleted."
      actions={
        <>
          <button className="button button-secondary button-small" onClick={() => void loadAll()}>
            Load organisation data
          </button>
          <button className="button button-secondary button-small" onClick={() => void discover()} disabled={busy === "discover"}>
            {busy === "discover" ? "Discovering…" : "Review relationships"}
          </button>
          <button className="button button-secondary button-small" onClick={() => void plan()} disabled={busy === "preview"}>
            {busy === "preview" ? "Planning…" : "Preview renumbering"}
          </button>
        </>
      }
    >
      {works ? (
        <p className="muted">
          {works.file_count} files in {works.work_count} work(s) · {works.completed_files} completed file(s) · {works.completed_works} completed work(s). File count and work count stay distinguishable.
        </p>
      ) : (
        <p className="muted">Load organisation data to see works, relationships and migration history.</p>
      )}

      {relationships && relationships.length > 0 ? (
        <>
          <h4>Relationships ({relationships.filter((rel) => !rel.confirmed).length} unconfirmed)</h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Scripts</th>
                  <th>Kind</th>
                  <th>Confidence</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {relationships.slice(0, 50).map((rel) => (
                  <tr key={`${rel.source_id}-${rel.target_id}-${rel.kind}`}>
                    <td>
                      <code>{rel.source_id.slice(0, 12)}…</code> ↔ <code>{rel.target_id.slice(0, 12)}…</code>
                      <div className="muted small">{rel.evidence || rel.note}</div>
                    </td>
                    <td>{rel.kind.replace(/_/g, " ")}</td>
                    <td>{rel.confidence}</td>
                    <td>{rel.confirmed ? <Tag tone="accent">Confirmed</Tag> : <Tag>Proposed</Tag>}</td>
                    <td>
                      {!rel.confirmed ? (
                        <div className="activity-actions">
                          <select value={confirmKind} onChange={(event) => setConfirmKind(event.target.value)} aria-label="Relationship kind">
                            {RELATIONSHIP_KINDS.map((kind) => (
                              <option value={kind} key={kind}>{kind.replace(/_/g, " ")}</option>
                            ))}
                          </select>
                          <button className="button button-ghost button-small" onClick={() => void confirm(rel)} disabled={busy?.startsWith("confirm-")}>
                            Confirm
                          </button>
                        </div>
                      ) : (
                        <span className="muted small">Reviewed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {works && works.works.length > 0 ? (
        <>
          <h4>Works ({works.work_count})</h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Work</th>
                  <th>Versions</th>
                  <th>Canonical</th>
                </tr>
              </thead>
              <tbody>
                {works.works.slice(0, 30).map((work) => (
                  <tr key={work.work_id}>
                    <td>Work {work.work_number} <span className="muted">({work.size} version{work.size === 1 ? "" : "s"})</span></td>
                    <td>{work.members.map((member) => member.relpath).join(", ")}</td>
                    <td><code>{work.canonical_id.slice(0, 12)}…</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {preview ? (
        <>
          <h4>Migration preview (read-only)</h4>
          <p className="muted">
            {preview.manifest.items.length} file(s) · {preview.manifest.collisions.length} collision(s) · {preview.manifest.references.length} reference(s). Hash {preview.manifest_hash.slice(0, 12)}… binds approval.
          </p>
          {preview.manifest.collisions.length ? (
            <p className="notice notice-warning">Collisions must be resolved before approval can be applied.</p>
          ) : null}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Current</th>
                  <th>Proposed</th>
                  <th>Fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {preview.manifest.items.slice(0, 20).map((item) => (
                  <tr key={item.id}>
                    <td><code>{item.current}</code></td>
                    <td><code>{item.proposed}</code></td>
                    <td><code>{item.sha256.slice(0, 12)}…</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.manifest.items.length > 20 ? <p className="muted">Showing 20 of {preview.manifest.items.length}.</p> : null}
          <div className="toolbar">
            <button className="button button-primary button-small" onClick={() => void approve()} disabled={busy === "approve" || preview.manifest.collisions.length > 0}>
              {busy === "approve" ? "Approving…" : "Confirm migration"}
            </button>
            <button className="button button-secondary button-small" onClick={() => void apply()} disabled={busy === "apply" || preview.manifest.collisions.length > 0}>
              {busy === "apply" ? "Applying…" : "Apply approved migration"}
            </button>
          </div>
        </>
      ) : null}

      {migrations && migrations.length > 0 ? (
        <>
          <h4>Migration history</h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Items</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {migrations.map((migration) => (
                  <tr key={migration.id}>
                    <td><code>{migration.id.slice(0, 16)}…</code></td>
                    <td>{migration.status}{migration.error ? ` — ${migration.error.slice(0, 80)}` : ""}</td>
                    <td>{migration.item_count}</td>
                    <td>{formatDateTime(migration.created_at)}</td>
                    <td>
                      {(migration.status === "applied" || migration.status === "failed") && (
                        <button className="button button-ghost button-small" onClick={() => void rollback(migration.id)} disabled={busy === `rollback-${migration.id}`}>
                          Roll back
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </Section>
  );
}

type OrganisePreviewManifest = {
  items: Array<{ id: string; current: string; proposed: string; current_number: number | null; proposed_number: number; sha256: string; status: string }>;
  references: Array<{ source: string; line: number; match: string }>;
  collisions: Array<{ destination: string; reason: string }>;
};

function CandidateSection(props: { onChanged: () => void }) {
  const toast = useToast();
  const [candidates, setCandidates] = useState<ScriptCandidate[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reviseText, setReviseText] = useState("");
  const [reviseNote, setReviseNote] = useState("");

  async function loadAll() {
    try {
      const result = await api.get<{ candidates: ScriptCandidate[] }>("/api/scripts/candidates");
      setCandidates(result.candidates);
    } catch (caught) {
      toast.push("error", "Candidates failed", errorMessage(caught));
    }
  }

  async function critique(id: string, model?: string) {
    setBusy(`critique-${id}`);
    try {
      const result = await api.post<{ deterministic?: unknown; pi?: { skipped?: boolean } }>(`/api/scripts/candidates/${id}/critique${model ? `?model=${encodeURIComponent(model)}` : ""}`);
      toast.push(result.pi?.skipped ? "info" : "success", result.pi?.skipped ? "Deterministic critique only — AI consent not granted" : "Critique recorded");
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Critique failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function revise(id: string) {
    if (!reviseText.trim()) {
      toast.push("info", "Edit the text first");
      return;
    }
    setBusy(`revise-${id}`);
    try {
      await api.post(`/api/scripts/candidates/${id}/revise`, { content: reviseText, note: reviseNote || "Manual revision." });
      toast.push("success", "New version created — previous version kept");
      setReviseText("");
      setReviseNote("");
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Revision failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function setStatus(id: string, next: string) {
    if (next === "accepted" && !window.confirm("Accept this candidate as recording-ready? Promotion to the library remains a separate explicit step.")) return;
    try {
      await api.patch(`/api/scripts/candidates/${id}/status`, { status: next });
      toast.push("success", `Candidate ${next}`);
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Status failed", errorMessage(caught));
    }
  }

  async function promote(id: string) {
    if (!window.confirm("Promote? This writes the next numbered script file and registers it as discovered (never completed).")) return;
    setBusy(`promote-${id}`);
    try {
      const result = await api.post<ScriptCandidate>(`/api/scripts/candidates/${id}/promote`);
      toast.push("success", `Promoted as ${result.promoted_relpath} — discovered, not completed`);
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Promotion failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Ascendance candidates"
      description="Recording-ready drafts live here — never in the numbered library until an explicit promotion."
      actions={
        <button className="button button-secondary button-small" onClick={() => void loadAll()}>
          Load candidates
        </button>
      }
    >
      {(candidates ?? []).length === 0 ? <p className="muted">No candidates yet. Drafts appear here with validation, critique, and promotion controls.</p> : null}
      {(candidates ?? []).map((candidate) => {
        const validation = candidate.validation as Record<string, unknown>;
        const assessment = candidate.critique as { deterministic?: { findings?: Array<{ area: string; note: string }>; strengths?: string[] }; pi?: { skipped?: boolean; error?: string; reason?: string; model?: string; findings?: Array<{ area: string; note: string }> } };
        const open = openId === candidate.id;
        return (
          <div key={candidate.id} className="panel review-card">
            <div className="activity-head">
              <strong>{candidate.title} {candidate.version}</strong>
              <Tag tone={candidate.status === "accepted" ? "accent" : undefined}>{candidate.status}</Tag>
              <span className="muted">{candidate.word_count} words · ~{Math.round(candidate.est_seconds / 60)} min · {String((candidate.provenance as Record<string, unknown>)?.generator ?? "")}</span>
              {candidate.promoted_relpath ? <span className="muted">Promoted: <code>{candidate.promoted_relpath}</code></span> : null}
              <button className="button button-ghost button-small" onClick={() => { setOpenId(open ? null : candidate.id); if (!open) setReviseText(candidate.content); }}>
                {open ? "Hide" : "Open"}
              </button>
            </div>
            {validation && (validation.hard_fail || (validation.safety_hits as unknown[])?.length || (validation.cues_missing as unknown[])?.length) ? (
              <p className="notice notice-warning">Validation: {[
                validation.hard_fail ? "fails hard gate" : null,
                ((validation.safety_hits as unknown[]) ?? []).length ? `safety: ${((validation.safety_hits as unknown[]) ?? []).join(", ")}` : null,
                ((validation.cues_missing as unknown[]) ?? []).length ? `missing cues: ${((validation.cues_missing as unknown[]) ?? []).join(", ")}` : null,
              ].filter(Boolean).join(" · ")}</p>
            ) : (
              <p className="muted">Validation passed: cues present, no safety hits, within duration.</p>
            )}
            {open ? (
              <>
                <pre className="code-block">{candidate.content.slice(0, 6000)}{candidate.content.length > 6000 ? "\n…(truncated)" : ""}</pre>
                {assessment?.deterministic ? (
                  <p className="muted">Deterministic critique: {(assessment.deterministic.findings ?? []).length} finding(s); strengths: {(assessment.deterministic.strengths ?? []).join("; ") || "—"}</p>
                ) : null}
                {assessment?.pi?.skipped ? <p className="muted">Pi critique skipped: {String(assessment.pi.reason ?? assessment.pi.error ?? "no consent")}.</p> : null}
                {assessment?.pi && !assessment.pi.skipped ? <p className="muted">Pi critique by {String(assessment.pi.model ?? "unknown model")}: {(assessment.pi.findings ?? []).length} finding(s).</p> : null}
                <div className="toolbar">
                  <button className="button button-secondary button-small" onClick={() => void critique(candidate.id)} disabled={busy === `critique-${candidate.id}`}>
                    {busy === `critique-${candidate.id}` ? "Critiquing…" : "Run critique"}
                  </button>
                  <button className="button button-ghost button-small" onClick={() => void setStatus(candidate.id, "accepted")} disabled={candidate.status === "promoted" || candidate.status === "rejected"}>Accept</button>
                  <button className="button button-ghost button-small" onClick={() => void setStatus(candidate.id, "rejected")} disabled={candidate.status === "promoted" || candidate.status === "rejected"}>Reject</button>
                  <button className="button button-primary button-small" onClick={() => void promote(candidate.id)} disabled={busy === `promote-${candidate.id}` || candidate.status !== "accepted"}>
                    {busy === `promote-${candidate.id}` ? "Promoting…" : "Promote to library"}
                  </button>
                </div>
                <label className="field">
                  <span>Revise (creates {candidate.version.replace(/v(\d+)/, (_, n) => `v${Number(n) + 1}`)}; original kept)</span>
                  <textarea className="code-input" rows={6} value={reviseText} onChange={(event) => setReviseText(event.target.value)} />
                </label>
                <div className="inline-form">
                  <input value={reviseNote} onChange={(event) => setReviseNote(event.target.value)} placeholder="What changed and why" aria-label="Revision note" />
                  <button className="button button-secondary button-small" onClick={() => void revise(candidate.id)} disabled={busy === `revise-${candidate.id}` || !reviseText.trim()}>
                    Save as new version
                  </button>
                </div>
              </>
            ) : null}
          </div>
        );
      })}
    </Section>
  );
}

function IntelligenceSection(props: { onChanged: () => void }) {
  const toast = useToast();
  const [coverage, setCoverage] = useState<IntelligenceCoverage | null>(null);
  const [purposes, setPurposes] = useState<Record<string, { ai: number; user: number }> | null>(null);
  const [batches, setBatches] = useState<ScriptBatch[] | null>(null);
  const [syntheses, setSyntheses] = useState<LibrarySynthesis[] | null>(null);
  const [detail, setDetail] = useState<LibrarySynthesis | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [batchScope, setBatchScope] = useState("missing");
  const [batchModel, setBatchModel] = useState("");
  const [synthKind, setSynthKind] = useState("full");

  async function loadAll() {
    try {
      const [cov, bat, syn] = await Promise.all([
        api.get<{ coverage: IntelligenceCoverage; purposes: { tags: Record<string, { ai: number; user: number }> } }>("/api/scripts/intelligence/coverage"),
        api.get<{ batches: ScriptBatch[] }>("/api/scripts/batches"),
        api.get<{ syntheses: LibrarySynthesis[] }>("/api/scripts/syntheses"),
      ]);
      setCoverage(cov.coverage);
      setPurposes(cov.purposes.tags);
      setBatches(bat.batches);
      setSyntheses(syn.syntheses);
    } catch (caught) {
      toast.push("error", "Intelligence data failed", errorMessage(caught));
    }
  }

  async function startBatch() {
    setBusy("batch");
    try {
      await api.post("/api/scripts/batches", { scope: batchScope, model: batchModel || undefined });
      toast.push("success", "Review batch created — step it to completion");
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Batch failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function stepBatch(id: string) {
    setBusy(`step-${id}`);
    try {
      await api.post(`/api/scripts/batches/${id}/step`, { limit: 2 });
      await loadAll();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Batch step failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function cancelBatch(id: string) {
    if (!window.confirm("Cancel this batch? Completed reviews are kept; pending items stop.")) return;
    try {
      await api.post(`/api/scripts/batches/${id}/cancel`);
      toast.push("info", "Batch cancelled — resume with a new batch");
      await loadAll();
    } catch (caught) {
      toast.push("error", "Cancel failed", errorMessage(caught));
    }
  }

  async function retryBatch(id: string) {
    try {
      await api.post(`/api/scripts/batches/${id}/retry`);
      toast.push("success", "Failed items queued for retry");
      await loadAll();
    } catch (caught) {
      toast.push("error", "Retry failed", errorMessage(caught));
    }
  }

  async function requestSynthesis() {
    setBusy("synth");
    try {
      const result = await api.post<LibrarySynthesis>("/api/scripts/syntheses", { kind: synthKind, model: batchModel || undefined });
      toast.push("success", `Synthesis recorded (${result.freshness})`);
      setDetail(result);
      await loadAll();
    } catch (caught) {
      toast.push("error", "Synthesis failed", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  const active = (batches ?? []).find((batch) => !["cancelled", "complete"].includes(batch.status)) ?? null;

  return (
    <Section
      title="Library intelligence"
      description="Read-only analysis over review evidence. Batches run bounded steps; synthesis never rewrites scripts."
      actions={
        <button className="button button-secondary button-small" onClick={() => void loadAll()}>
          Load intelligence
        </button>
      }
    >
      {coverage ? (
        <div className="stat-strip">
          <Stat label="Registered" value={coverage.total} />
          <Stat label="Current reviews" value={coverage.current} />
          <Stat label="Stale" value={coverage.stale} />
          <Stat label="Never reviewed" value={coverage.never} />
          <Stat label="Median duration" value={coverage.durations.median_seconds != null ? `${Math.round(coverage.durations.median_seconds / 60)} min` : "—"} />
        </div>
      ) : (
        <p className="muted">Load intelligence to see review coverage. Nothing is reviewed until you run a batch.</p>
      )}
      {purposes && Object.keys(purposes).length > 0 ? (
        <p className="muted">
          Purposes: {Object.entries(purposes).map(([tag, counts]) => `${tag} (${counts.ai} AI${counts.user ? `, ${counts.user} confirmed` : ""})`).join(" · ")}
        </p>
      ) : null}

      <h4>Review batches</h4>
      <div className="inline-form">
        <select value={batchScope} onChange={(event) => setBatchScope(event.target.value)} aria-label="Batch scope">
          <option value="missing">Missing reviews</option>
          <option value="stale">Stale reviews</option>
          <option value="all">All scripts</option>
        </select>
        <input value={batchModel} onChange={(event) => setBatchModel(event.target.value)} placeholder="Model override (optional)" aria-label="Batch model override" />
        <button className="button button-primary button-small" onClick={() => void startBatch()} disabled={busy === "batch" || active != null} title={active ? "A batch is already active" : undefined}>
          {busy === "batch" ? "Starting…" : "Start batch"}
        </button>
      </div>
      {(batches ?? []).slice(0, 5).map((batch) => (
        <div key={batch.id} className="panel review-card">
          <div className="activity-head">
            <strong>{batch.id.slice(0, 12)}…</strong>
            <Tag tone={batch.status === "complete" ? "accent" : undefined}>{batch.status}</Tag>
            <span className="muted">
              {batch.counts.reviewed}/{batch.counts.total} reviewed ({batch.counts.reused} reused, {batch.counts.failed} failed, {batch.counts.pending} pending)
              {batch.model ? ` · ${batch.model}` : " · default model"}
            </span>
          </div>
          <div className="toolbar">
            {batch.status !== "complete" && batch.status !== "cancelled" ? (
              <button className="button button-secondary button-small" onClick={() => void stepBatch(batch.id)} disabled={busy === `step-${batch.id}`}>
                {busy === `step-${batch.id}` ? "Reviewing…" : "Run next step"}
              </button>
            ) : null}
            {batch.counts.failed > 0 && batch.status !== "cancelled" && batch.status !== "complete" ? (
              <button className="button button-ghost button-small" onClick={() => void retryBatch(batch.id)}>Retry failures</button>
            ) : null}
            {batch.status !== "complete" && batch.status !== "cancelled" ? (
              <button className="button button-ghost button-small" onClick={() => void cancelBatch(batch.id)}>Cancel</button>
            ) : null}
          </div>
          {batch.items.filter((item) => item.status === "failed").slice(0, 5).map((item) => (
            <p key={item.script_id} className="row-line">
              <span className="tag">failed</span> <code>{item.relpath ?? item.script_id}</code>{" "}
              <span className="muted">{item.error}</span>
            </p>
          ))}
        </div>
      ))}

      <h4>Synthesis reports</h4>
      <div className="inline-form">
        <select value={synthKind} onChange={(event) => setSynthKind(event.target.value)} aria-label="Synthesis kind">
          <option value="full">Full library synthesis</option>
          <option value="ascendance">Ascendance design report</option>
        </select>
        <button className="button button-primary button-small" onClick={() => void requestSynthesis()} disabled={busy === "synth"}>
          {busy === "synth" ? "Synthesising…" : "Generate synthesis"}
        </button>
      </div>
      {(syntheses ?? []).slice(0, 10).map((report) => (
        <div key={report.id} className="panel review-card">
          <div className="activity-head">
            <strong>{report.kind === "ascendance" ? "Ascendance design" : "Library synthesis"}</strong>
            {report.freshness === "CURRENT" ? <Tag tone="accent">Current</Tag> : <Tag>Stale — reviews changed</Tag>}
            <span className="muted">{formatDateTime(report.created_at)}</span>
            <button className="button button-ghost button-small" onClick={() => setDetail(detail?.id === report.id ? null : report)}>
              {detail?.id === report.id ? "Hide" : "Open"}
            </button>
          </div>
          {detail?.id === report.id ? (
            <SynthesisDetail report={detail} onChanged={() => { props.onChanged(); }} />
          ) : null}
        </div>
      ))}
    </Section>
  );
}

function SynthesisDetail(props: { report: LibrarySynthesis; onChanged: () => void }) {
  const data = props.report.report as Record<string, unknown>;
  const manifest = props.report.manifest as Record<string, unknown>;
  const reviewRefs = (manifest.review_refs ?? []) as Array<{ script_id: string }>;
  const str = (value: unknown) => (typeof value === "string" ? value : "");
  const list = (value: unknown) => (Array.isArray(value) ? value.map((item) => String(item)) : []);
  return (
    <div>
      <p className="muted">
        Evidence: {reviewRefs.length} review(s) · unique contents {(manifest.unique_contents as number | undefined) ?? "—"} ·{" "}
        manifest <code>{props.report.manifest_hash.slice(0, 12)}…</code>
      </p>
      {props.report.kind === "ascendance" ? (
        <>
          <p><strong>Opening:</strong> {str(data.opening)}</p>
          <p><strong>Awareness trigger:</strong> {str(data.awareness_trigger)}</p>
          <p><strong>Emotional orientation:</strong> {str(data.emotional_orientation)}</p>
          <p><strong>Identity language:</strong> {str(data.identity_language)}</p>
          <p><strong>Recognition mechanism:</strong> {str(data.recognition_mechanism)}</p>
          <p><strong>Closing:</strong> {str(data.closing)}</p>
          <h5>Preserve</h5>
          <ul>{list(data.preserve).map((item, index) => <li key={index}>{item}</li>)}</ul>
          <h5>Remove</h5>
          <ul>{list(data.remove).map((item, index) => <li key={index}>{item}</li>)}</ul>
          <h5>Five-minute structure</h5>
          <ol>{list(data.five_minute_structure).map((item, index) => <li key={index}>{item}</li>)}</ol>
        </>
      ) : (
        <>
          <p><strong>Strengths:</strong> {list(data.strengths).join("; ") || "—"}</p>
          <p><strong>Weaknesses:</strong> {list(data.weaknesses).join("; ") || "—"}</p>
          <p><strong>Walking-suitable:</strong> {list(data.walking_suitable).join(", ") || "—"}</p>
          <p><strong>Review priorities:</strong> {list(data.review_priorities).join(", ") || "—"}</p>
          <h5>Themes</h5>
          <ul>{(Array.isArray(data.themes) ? data.themes : []).map((theme, index) => {
            const item = theme as Record<string, unknown>;
            return <li key={index}><strong>{String(item.name ?? "")}</strong> — {String(item.description ?? "")} <span className="muted">({String(item.confidence ?? "unconfirmed")})</span></li>;
          })}</ul>
        </>
      )}
    </div>
  );
}
