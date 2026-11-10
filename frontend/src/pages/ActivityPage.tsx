import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Activity, Copy, Eye, Filter, Plus, RefreshCw, Settings2, Sparkles } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import { Modal } from "../components/Modal";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  ProvenanceBadge,
  Section,
  SimpleStatusBadge,
  Stat,
  Tag,
} from "../components/ui";
import { copyText } from "../lib/clipboard";
import { activityLabel, formatDate, formatDateTime } from "../lib/format";
import type {
  ActivityEvent,
  GitActivityRoot,
  GitCommit,
  GitDailyProjects,
  GitRepo,
  GitReview,
  GitScanStatus,
  GitSummary,
  GitTimeline,
  Project,
  ReviewModelCatalogue,
} from "../types/api";

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

function prettyDay(dateIso: string): string {
  try {
    const noon = new Date(`${dateIso}T12:00:00`);
    return noon.toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateIso;
  }
}

type Preset = "today" | "yesterday" | "7d" | "30d" | "custom";

const activityTypes = [
  "user_note",
  "user_decision",
  "workspace_focus",
  "checkpoint",
  "task_created",
  "task_updated",
  "recommendation_reviewed",
  "application_launch",
  "application_stopped",
  "application_launch_failed",
  "application_health",
  "repository_opened",
  "git_observation",
  "adapter_observation",
  "adapter_available",
  "adapter_unavailable",
  "discovery_scan",
  "briefing_generated",
  "system",
];

function commitTime(ts: number): string {
  if (!ts) return "Unknown time";
  return new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function dayKey(ts: number): string {
  if (!ts) return "Unknown date";
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function ActivityPage() {
  const toast = useToast();
  const [tab, setTab] = useState<"commits" | "events">("commits");

  // ---- timeline filters
  const [preset, setPreset] = useState<Preset>("today");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [repoId, setRepoId] = useState("");
  const [root, setRoot] = useState("");
  const [category, setCategory] = useState("");
  const [author, setAuthor] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 100;

  const query = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      preset,
      limit,
      offset: page * limit,
      repo_id: repoId || undefined,
      root: root || undefined,
      category: category || undefined,
      author: author || undefined,
      review_status: reviewStatus || undefined,
      search: appliedSearch || undefined,
    };
    if (preset === "custom") {
      if (customFrom) params.date_from = Math.floor(new Date(`${customFrom}T00:00:00`).getTime() / 1000);
      if (customTo) params.date_to = Math.floor(new Date(`${customTo}T23:59:59`).getTime() / 1000);
    }
    return apiPath("/api/git-activity/timeline", params);
  }, [preset, page, repoId, root, category, author, reviewStatus, appliedSearch, customFrom, customTo]);

  const timeline = useApi<GitTimeline>(tab === "commits" ? query : null, { pollMs: 60000 });
  const summary = useApi<GitSummary>(tab === "commits" ? "/api/git-activity/summary" : null, { pollMs: 60000 });
  const repos = useApi<GitRepo[]>(tab === "commits" ? "/api/git-activity/repos?limit=500" : null);
  const roots = useApi<GitActivityRoot[]>(tab === "commits" ? "/api/git-activity/roots" : null);
  const scan = useApi<GitScanStatus>(tab === "commits" ? "/api/git-activity/scan" : null, { pollMs: 5000 });

  // ---- selection & modals
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<{ repoId: string; sha: string } | null>(null);
  const [promptFor, setPromptFor] = useState<{ repoId: string; sha: string } | null>(null);
  const [reviewFor, setReviewFor] = useState<{ repoId: string; sha: string } | null>(null);
  const [rangeOpen, setRangeOpen] = useState(false);
  const [repoPanel, setRepoPanel] = useState<string | null>(null);
  const [rootsOpen, setRootsOpen] = useState(false);

  const grouped = useMemo(() => {
    const groups = new Map<string, GitCommit[]>();
    for (const item of timeline.data?.items ?? []) {
      const key = dayKey(item.committer_ts);
      groups.set(key, [...(groups.get(key) ?? []), item]);
    }
    return Array.from(groups.entries());
  }, [timeline.data]);

  function resetPage() {
    setPage(0);
  }

  async function refresh() {
    try {
      await api.post("/api/git-activity/scan");
      toast.push("success", "Activity sync requested", "Indexing runs in the background.");
      scan.reload();
    } catch (caught) {
      toast.push("error", "Sync failed", errorMessage(caught));
    }
  }

  function toggleSelect(key: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const hasFilters = repoId || root || category || author || reviewStatus || appliedSearch || preset !== "today";

  return (
    <div className="page">
      <PageHeader
        eyebrow="Activity"
        title="Activity"
        description="What changed across every project and book, with contextual AI review of the actual diffs."
        actions={
          tab === "commits" ? (
            <>
              <button className="button button-secondary button-small" onClick={() => setRootsOpen(true)}>
                <Settings2 size={14} /> Configure
              </button>
              <button className="button button-primary button-small" onClick={() => void refresh()}>
                <RefreshCw size={14} /> Refresh
              </button>
            </>
          ) : undefined
        }
      />

      <div className="toolbar" role="tablist" aria-label="Activity views">
        <button
          role="tab"
          aria-selected={tab === "commits"}
          className={`button button-small ${tab === "commits" ? "button-primary" : "button-ghost"}`}
          onClick={() => setTab("commits")}
        >
          Commits
        </button>
        <button
          role="tab"
          aria-selected={tab === "events"}
          className={`button button-small ${tab === "events" ? "button-primary" : "button-ghost"}`}
          onClick={() => setTab("events")}
        >
          Notes &amp; events
        </button>
      </div>

      {tab === "commits" ? (
        <CommitsView
          timeline={timeline}
          summary={summary}
          repos={repos}
          roots={roots}
          scan={scan}
          grouped={grouped}
          preset={preset}
          setPreset={(value) => {
            setPreset(value);
            resetPage();
          }}
          customFrom={customFrom}
          setCustomFrom={setCustomFrom}
          customTo={customTo}
          setCustomTo={setCustomTo}
          repoId={repoId}
          setRepoId={(value) => {
            setRepoId(value);
            resetPage();
          }}
          root={root}
          setRoot={(value) => {
            setRoot(value);
            resetPage();
          }}
          category={category}
          setCategory={(value) => {
            setCategory(value);
            resetPage();
          }}
          author={author}
          setAuthor={setAuthor}
          reviewStatus={reviewStatus}
          setReviewStatus={(value) => {
            setReviewStatus(value);
            resetPage();
          }}
          search={search}
          setSearch={setSearch}
          applySearch={() => {
            setAppliedSearch(search.trim());
            resetPage();
          }}
          hasFilters={Boolean(hasFilters)}
          clearFilters={() => {
            setRepoId("");
            setRoot("");
            setCategory("");
            setAuthor("");
            setReviewStatus("");
            setSearch("");
            setAppliedSearch("");
            setPreset("today");
            setCustomFrom("");
            setCustomTo("");
            resetPage();
          }}
          page={page}
          setPage={setPage}
          selected={selected}
          toggleSelect={toggleSelect}
          clearSelected={() => setSelected(new Set())}
          openDetail={setDetail}
          openPrompt={setPromptFor}
          openReview={setReviewFor}
          openRange={() => setRangeOpen(true)}
          openRepo={setRepoPanel}
          reload={() => {
            timeline.reload();
            summary.reload();
          }}
        />
      ) : (
        <EventsView />
      )}

      {detail ? (
        <CommitDetailModal
          repoId={detail.repoId}
          sha={detail.sha}
          onClose={() => setDetail(null)}
          onPrompt={(repoId, sha) => {
            setDetail(null);
            setPromptFor({ repoId, sha });
          }}
          onReview={(repoId, sha) => {
            setDetail(null);
            setReviewFor({ repoId, sha });
          }}
        />
      ) : null}
      {promptFor ? (
        <PromptModal repoId={promptFor.repoId} sha={promptFor.sha} onClose={() => setPromptFor(null)} />
      ) : null}
      {reviewFor ? (
        <ReviewModal
          repoId={reviewFor.repoId}
          sha={reviewFor.sha}
          onClose={() => setReviewFor(null)}
          onDone={() => timeline.reload()}
        />
      ) : null}
      {rangeOpen ? (
        <RangeModal
          repos={repos.data ?? []}
          selected={selected}
          onClose={() => setRangeOpen(false)}
          onDone={() => {
            setSelected(new Set());
            setRangeOpen(false);
          }}
        />
      ) : null}
      {repoPanel ? <RepoPanelModal repoId={repoPanel} onClose={() => setRepoPanel(null)} /> : null}
      {rootsOpen ? (
        <RootsModal roots={roots.data ?? []} onClose={() => setRootsOpen(false)} onChanged={() => roots.reload()} />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ commits
function CommitsView(props: {
  timeline: ReturnType<typeof useApi<GitTimeline>>;
  summary: ReturnType<typeof useApi<GitSummary>>;
  repos: ReturnType<typeof useApi<GitRepo[]>>;
  roots: ReturnType<typeof useApi<GitActivityRoot[]>>;
  scan: ReturnType<typeof useApi<GitScanStatus>>;
  grouped: Array<[string, GitCommit[]]>;
  preset: Preset;
  setPreset: (value: Preset) => void;
  customFrom: string;
  setCustomFrom: (value: string) => void;
  customTo: string;
  setCustomTo: (value: string) => void;
  repoId: string;
  setRepoId: (value: string) => void;
  root: string;
  setRoot: (value: string) => void;
  category: string;
  setCategory: (value: string) => void;
  author: string;
  setAuthor: (value: string) => void;
  reviewStatus: string;
  setReviewStatus: (value: string) => void;
  search: string;
  setSearch: (value: string) => void;
  applySearch: () => void;
  hasFilters: boolean;
  clearFilters: () => void;
  page: number;
  setPage: (value: number) => void;
  selected: Set<string>;
  toggleSelect: (key: string) => void;
  clearSelected: () => void;
  openDetail: (value: { repoId: string; sha: string }) => void;
  openPrompt: (value: { repoId: string; sha: string }) => void;
  openReview: (value: { repoId: string; sha: string }) => void;
  openRange: () => void;
  openRepo: (repoId: string) => void;
  reload: () => void;
}) {
  const {
    timeline,
    summary,
    repos,
    roots,
    scan,
    grouped,
    preset,
    setPreset,
    customFrom,
    setCustomFrom,
    customTo,
    setCustomTo,
    selected,
  } = props;
  const scanning = Boolean(scan.data?.running);
  const partial = Boolean(timeline.data?.partial);

  return (
    <>
      {scanning ? (
        <p className="notice">
          Indexing repositories in the background{scan.data?.repos_indexed ? ` — ${scan.data.repos_indexed} indexed` : ""}
          {typeof scan.data?.commits_new === "number" && scan.data.commits_new > 0 ? `, ${scan.data.commits_new} new commits` : ""}.
          The timeline below shows indexed evidence so far.
        </p>
      ) : null}
      {partial && !scanning ? (
        <p className="notice notice-warning">
          Historical backfill is still running ({summary.data?.backfill_pending ?? "?"} repositories pending).
          Counts may grow; this page does not claim zero activity for missing history.
        </p>
      ) : null}
      {scan.data?.error ? <p className="notice notice-error">Last scan reported: {scan.data.error}</p> : null}

      {summary.data ? (
        <div className="stat-strip">
          <Stat label="Commits today" value={summary.data.commits_today} />
          <Stat label="Projects active today" value={summary.data.projects_today} />
          <Stat label="Commits this week" value={summary.data.commits_week} />
          <Stat label="Commits reviewed" value={summary.data.commits_reviewed} />
          <Stat
            label="Index"
            value={`${summary.data.repos_indexed} repos / ${summary.data.commits_indexed} commits`}
            detail={summary.data.complete ? "Complete" : `${summary.data.backfill_pending} repos backfilling`}
          />
        </div>
      ) : null}

      <DailyProjectPanel />

      <div className="toolbar">
        {(["today", "yesterday", "7d", "30d", "custom"] as Preset[]).map((item) => (
          <button
            key={item}
            className={`button button-small ${preset === item ? "button-primary" : "button-ghost"}`}
            onClick={() => setPreset(item)}
          >
            {item === "today" ? "Today" : item === "yesterday" ? "Yesterday" : item === "7d" ? "7 days" : item === "30d" ? "30 days" : "Custom"}
          </button>
        ))}
        {preset === "custom" ? (
          <>
            <label className="date-field">
              <span className="sr-only">From date</span>
              <input type="date" value={customFrom} onChange={(event) => setCustomFrom(event.target.value)} />
            </label>
            <label className="date-field">
              <span className="sr-only">To date</span>
              <input type="date" value={customTo} onChange={(event) => setCustomTo(event.target.value)} />
            </label>
          </>
        ) : null}
        <label className="select-field">
          <span className="sr-only">Filter by project</span>
          <select value={props.repoId} onChange={(event) => props.setRepoId(event.target.value)}>
            <option value="">All projects</option>
            {(repos.data ?? []).map((repo) => (
              <option value={repo.id} key={repo.id}>
                {repo.name}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by root</span>
          <select value={props.root} onChange={(event) => props.setRoot(event.target.value)}>
            <option value="">All roots</option>
            {(roots.data ?? []).map((item) => (
              <option value={item.path} key={item.path}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by category</span>
          <select value={props.category} onChange={(event) => props.setCategory(event.target.value)}>
            <option value="">All categories</option>
            <option value="software">Software</option>
            <option value="books">Books</option>
            {Array.from(new Set((roots.data ?? []).map((item) => item.category)))
              .filter((item) => item !== "software" && item !== "books")
              .map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by review status</span>
          <select value={props.reviewStatus} onChange={(event) => props.setReviewStatus(event.target.value)}>
            <option value="">Reviewed + awaiting</option>
            <option value="reviewed">Reviewed</option>
            <option value="awaiting">Awaiting review</option>
          </select>
        </label>
        <label className="search-field">
          <Filter size={14} aria-hidden="true" />
          <span className="sr-only">Search commits</span>
          <input
            value={props.search}
            placeholder="Search message, repo, author…"
            onChange={(event) => props.setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") props.applySearch();
            }}
          />
        </label>
        <label className="search-field">
          <span className="sr-only">Filter by author</span>
          <input
            value={props.author}
            placeholder="Author…"
            onChange={(event) => {
              props.setAuthor(event.target.value);
            }}
          />
        </label>
        {props.hasFilters ? (
          <button className="button button-ghost button-small" onClick={props.clearFilters}>
            Clear filters
          </button>
        ) : null}
        <span className="toolbar-count">{timeline.data?.total ?? 0} commits</span>
      </div>

      {selected.size > 0 ? (
        <div className="toolbar">
          <span className="toolbar-count">{selected.size} selected</span>
          <button className="button button-secondary button-small" onClick={props.openRange}>
            Prepare range review
          </button>
          <button className="button button-ghost button-small" onClick={props.clearSelected}>
            Clear selection
          </button>
        </div>
      ) : null}

      <div className="activity-layout">
        <div>
          {timeline.loading && !timeline.data ? <LoadingBlock label="Loading activity" /> : null}
          {timeline.error ? <ErrorState message={timeline.error.message} onRetry={timeline.reload} /> : null}
          {timeline.data && timeline.data.items.length === 0 ? (
            <EmptyState
              title={partial || scanning ? "Indexing activity" : "No commits match"}
              description={
                partial || scanning
                  ? "The index is still being built. Recent commits appear here as soon as they are indexed."
                  : "Try a wider date range, or run Refresh to index newly changed repositories."
              }
              icon={<Activity size={20} />}
            />
          ) : null}
          {grouped.map(([day, commits]) => (
            <section className="activity-day" key={day}>
              <h2>{day}</h2>
              <ul className="activity-feed">
                {commits.map((commit) => {
                  const key = `${commit.repo_id}:${commit.sha}`;
                  return (
                    <li key={key}>
                      <span className={`activity-marker type-${commit.review_count > 0 ? "verified_observation" : "user"}`} aria-hidden="true" />
                      <div className="activity-entry">
                        <div className="activity-head">
                          <input
                            type="checkbox"
                            aria-label={`Select ${commit.short_sha}`}
                            checked={selected.has(key)}
                            onChange={() => props.toggleSelect(key)}
                          />
                          <strong>{commitTime(commit.committer_ts)}</strong>
                          <button className="link-button" onClick={() => props.openRepo(commit.repo_id)} title={commit.repo_path}>
                            {commit.repo_name}
                          </button>
                          <span className="activity-type">{commit.subject}</span>
                        </div>
                        <div className="activity-meta">
                          <span title={commit.sha}>{commit.short_sha}</span>
                          {(commit.branches ?? []).slice(0, 3).map((branch) => (
                            <span key={branch}>{branch}</span>
                          ))}
                          <span>
                            {commit.files_changed} files, +{commit.insertions}/-{commit.deletions}
                          </span>
                          {commit.is_merge ? <span>merge</span> : null}
                          {!commit.reachable ? <span>unreachable</span> : null}
                          <span>{commit.author_name}</span>
                          {commit.review_count > 0 ? (
                            <Tag tone="accent">Reviewed × {commit.review_count}</Tag>
                          ) : (
                            <Tag>Awaiting review</Tag>
                          )}
                        </div>
                        <div className="activity-actions">
                          <button className="button button-ghost button-small" onClick={() => props.openDetail({ repoId: commit.repo_id, sha: commit.sha })}>
                            <Eye size={13} /> View diff
                          </button>
                          <button className="button button-ghost button-small" onClick={() => props.openPrompt({ repoId: commit.repo_id, sha: commit.sha })}>
                            <Copy size={13} /> Copy review prompt
                          </button>
                          <button className="button button-ghost button-small" onClick={() => props.openReview({ repoId: commit.repo_id, sha: commit.sha })}>
                            <Sparkles size={13} /> Review with AI
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
          {(timeline.data?.total ?? 0) > (props.page + 1) * 100 ? (
            <div className="toolbar">
              <button className="button button-secondary button-small" onClick={() => props.setPage(props.page + 1)}>
                Load more
              </button>
            </div>
          ) : null}
        </div>

        <aside className="activity-side">
          <Section title="Index status" description="Persistent local Git index.">
            {scan.data ? (
              <dl className="key-values">
                <div>
                  <dt>Status</dt>
                  <dd>{scan.data.running ? "Scanning" : scan.data.status}</dd>
                </div>
                <div>
                  <dt>Repositories</dt>
                  <dd>{scan.data.total_repos ?? "—"}</dd>
                </div>
                <div>
                  <dt>Commits</dt>
                  <dd>{scan.data.total_commits ?? "—"}</dd>
                </div>
                <div>
                  <dt>Backfill pending</dt>
                  <dd>{scan.data.backfill_pending ?? "—"}</dd>
                </div>
              </dl>
            ) : (
              <p className="muted">Index status unavailable.</p>
            )}
            {(scan.data?.errors ?? []).slice(0, 5).map((item) => (
              <p className="inline-error" key={item.path}>
                {item.path}: {item.error}
              </p>
            ))}
          </Section>
          <Section title="Projects" description="Discovered repositories.">
            {(repos.data ?? []).slice(0, 12).map((repo) => (
              <p key={repo.id} className="row-line">
                <button className="link-button" onClick={() => props.openRepo(repo.id)}>
                  {repo.name}
                </button>
                <span className="muted"> · {repo.total_commits} commits</span>
              </p>
            ))}
            {(repos.data ?? []).length > 12 ? <p className="muted">+ {(repos.data ?? []).length - 12} more — filter by project above.</p> : null}
            {(repos.data ?? []).length === 0 ? <p className="muted">No repositories indexed yet. Press Refresh.</p> : null}
          </Section>
        </aside>
      </div>
    </>
  );
}

// ------------------------------------------------- daily project review
function DailyProjectPanel() {
  const toast = useToast();
  const [date, setDate] = useState<string>(() => dublinToday());
  const timezone = "Europe/Dublin";
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [promptFor, setPromptFor] = useState<{ repoId: string; mode: "explain" | "review" } | null>(null);
  const [reviewFor, setReviewFor] = useState<{ repoId: string; mode: "explain" | "review" } | null>(null);

  const daily = useApi<GitDailyProjects>(apiPath("/api/git-activity/daily/projects", { date, timezone }));

  useEffect(() => {
    if (selectedRepo && daily.data && !daily.data.projects.some((p) => p.repo_id === selectedRepo)) {
      setSelectedRepo(null);
    }
  }, [daily.data, selectedRepo]);

  const projects = daily.data?.projects ?? [];
  const selected = projects.find((p) => p.repo_id === selectedRepo) ?? null;
  const totalCommits = daily.data?.total_commits ?? 0;

  function today() {
    setDate(dublinToday());
  }

  return (
    <Section
      title={`Daily Project Review — ${prettyDay(date)}`}
      description={`Timezone ${timezone} · start-inclusive / end-exclusive day bounds · server-side scope, not timeline pagination`}
    >
      <div className="toolbar">
        <label className="date-field">
          <span className="sr-only">Daily review date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Daily review date" />
        </label>
        <button className="button button-ghost button-small" onClick={today}>
          Today
        </button>
        <span className="toolbar-count">
          {daily.loading && !daily.data ? "Loading…" : `${daily.data?.total_repos ?? 0} projects · ${totalCommits} commits`}
        </span>
        {daily.data?.partial ? <Tag>Partial index — backfill pending</Tag> : null}
      </div>
      {daily.error ? <InlineError message={daily.error.message} /> : null}
      <div className="toolbar" role="tablist" aria-label="Active projects">
        <button
          role="tab"
          aria-selected={selectedRepo === null}
          className={`button button-small ${selectedRepo === null ? "button-primary" : "button-ghost"}`}
          onClick={() => setSelectedRepo(null)}
        >
          All active{projects.length ? ` (${projects.length})` : ""}
        </button>
        {projects.map((p) => (
          <button
            key={p.repo_id}
            role="tab"
            aria-selected={selectedRepo === p.repo_id}
            title={`${p.commit_count} commits · snapshot ${p.snapshot_fingerprint}`}
            className={`button button-small ${selectedRepo === p.repo_id ? "button-primary" : "button-ghost"}`}
            onClick={() => setSelectedRepo(p.repo_id)}
          >
            {p.repo_name} ({p.commit_count})
          </button>
        ))}
      </div>
      {projects.length === 0 && !daily.loading ? (
        <p className="muted">No indexed commits on this day. The timeline below shows the current filter; the daily scope is computed server-side.</p>
      ) : null}
      {selectedRepo === null ? (
        <div className="stat-strip">
          <Stat label="Projects active" value={daily.data?.total_repos ?? 0} />
          <Stat label="Commits" value={totalCommits} />
          <Stat label="Daily reviews" value={projects.filter((p) => p.review_status !== "not_reviewed").length} />
        </div>
      ) : selected ? (
        <div className="panel">
          <div className="activity-head">
            <strong>Selected: {selected.repo_name}</strong>
            <Tag>{selected.commit_count} commits</Tag>
            <Tag>
              {selected.files_changed} files touched{selected.files_changed_estimated ? " (est.)" : ""}
            </Tag>
            {selected.review_status === "not_reviewed" ? (
              <Tag>Not reviewed</Tag>
            ) : (
              <Tag tone="accent">
                {selected.review_status}
                {selected.review_mode ? ` · ${selected.review_mode}` : ""}
                {selected.review_verdict ? ` · ${selected.review_verdict}` : ""}
                {selected.review_stale ? " · stale" : ""}
              </Tag>
            )}
          </div>
          <p className="muted">
            {selected.commit_count} commits · {selected.files_changed} changed-file touches · +{selected.insertions}/
            -{selected.deletions} · snapshot {selected.snapshot_fingerprint}
            {selected.coverage_warning ? ` · ${selected.coverage_warning}` : ""}
          </p>
          {selected.review_stale ? (
            <p className="notice notice-warning">
              Previous daily review is out of date — new commits were indexed after it completed. Run another review for
              the current snapshot.
            </p>
          ) : null}
          <p className="muted">Summarise the day&apos;s development, identify significant architectural changes, and highlight unfinished or potentially problematic work.</p>
          <div className="toolbar">
            <button
              className="button button-secondary button-small"
              disabled={!selected}
              onClick={() => selected && setReviewFor({ repoId: selected.repo_id, mode: "explain" })}
            >
              <Sparkles size={13} /> Explain with AI
            </button>
            <button
              className="button button-secondary button-small"
              disabled={!selected}
              onClick={() => selected && setReviewFor({ repoId: selected.repo_id, mode: "review" })}
            >
              <Sparkles size={13} /> Review with AI
            </button>
            <button
              className="button button-ghost button-small"
              disabled={!selected}
              onClick={() => selected && setPromptFor({ repoId: selected.repo_id, mode: "review" })}
            >
              <Copy size={13} /> Create prompt
            </button>
          </div>
        </div>
      ) : null}
      {promptFor ? (
        <DailyPromptModal
          repoId={promptFor.repoId}
          date={date}
          timezone={timezone}
          initialMode={promptFor.mode}
          onClose={() => setPromptFor(null)}
        />
      ) : null}
      {reviewFor ? (
        <DailyReviewModal
          repoId={reviewFor.repoId}
          date={date}
          timezone={timezone}
          initialMode={reviewFor.mode}
          onClose={() => setReviewFor(null)}
          onDone={() => daily.reload()}
        />
      ) : null}
    </Section>
  );
}

function DailyPromptModal(props: { repoId: string; date: string; timezone: string; initialMode: "explain" | "review"; onClose: () => void }) {
  const toast = useToast();
  const [mode, setMode] = useState<"explain" | "review">(props.initialMode);
  const [profile, setProfile] = useState("code");
  const [copying, setCopying] = useState(false);
  type DailyPromptResult = {
    markdown: string;
    prompt_hash: string;
    diff_hash: string;
    context_fingerprint: string;
    size_chars: number;
    truncated: boolean;
    redactions: string[];
    redaction_count: number;
    coverage: Record<string, unknown>;
    commit_shas: string[];
    snapshot_fingerprint: string;
  };
  // POST-based prompt builder: fetch on demand so no model call is ever made on open.
  const [result, setResult] = useState<DailyPromptResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function build(currentMode: "explain" | "review", currentProfile: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.post<DailyPromptResult>("/api/git-activity/daily/prompt", {
        repo_id: props.repoId,
        date: props.date,
        timezone: props.timezone,
        mode: currentMode,
        profile: currentProfile,
      });
      setResult(data);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void build(mode, profile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, profile]);

  async function copy() {
    if (!result) return;
    setCopying(true);
    try {
      await copyText(result.markdown);
      toast.push("success", "Daily prompt copied", `${result.size_chars} chars — paste into any model.`);
    } catch (caught) {
      toast.push("error", "Copy failed", errorMessage(caught));
    } finally {
      setCopying(false);
    }
  }

  function download() {
    if (!result) return;
    const blob = new Blob([result.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `daily-${mode}-${props.date}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Modal title={`Daily prompt — ${mode === "explain" ? "Explain" : "Review"} ${props.date}`} wide onClose={props.onClose}>
      <p className="muted">No model call is made. Uses the same evidence package as direct AI execution for the full project-day.</p>
      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as "explain" | "review")}>
            <option value="explain">Explain with AI</option>
            <option value="review">Review with AI</option>
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Profile</span>
          <select value={profile} onChange={(e) => setProfile(e.target.value)}>
            <option value="code">Code review</option>
            <option value="prose">Prose / manuscript review</option>
          </select>
        </label>
        {result ? (
          <>
            <span className="toolbar-count">
              {result.size_chars} chars{result.truncated ? " · partial coverage" : " · full coverage"} · {result.redaction_count} redactions ·{" "}
              {result.commit_shas.length} commits · snapshot {(result.snapshot_fingerprint ?? "").slice(0, 8)}
            </span>
            <button className="button button-primary button-small" onClick={() => void copy()} disabled={copying}>
              <Copy size={13} /> {copying ? "Copying…" : "Copy"}
            </button>
            <button className="button button-secondary button-small" onClick={download}>
              Save .md
            </button>
          </>
        ) : null}
      </div>
      {loading && !result ? <LoadingBlock label="Building daily package" /> : null}
      {error ? <InlineError message={error} /> : null}
      {result ? <pre className="diff-block">{result.markdown.slice(0, 20000)}</pre> : null}
      {result && result.markdown.length > 20000 ? (
        <p className="muted">Preview shows the first 20,000 characters; Copy and Save include the full package.</p>
      ) : null}
    </Modal>
  );
}

function DailyReviewModal(props: {
  repoId: string;
  date: string;
  timezone: string;
  initialMode: "explain" | "review";
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const catalogue = useApi<ReviewModelCatalogue>("/api/git-activity/models");
  const [model, setModel] = useState("");
  const [profile, setProfile] = useState("code");
  const [mode, setMode] = useState<"explain" | "review">(props.initialMode);
  const [submitting, setSubmitting] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = useApi<GitReview>(activeId ? `/api/git-activity/reviews/${activeId}` : null, { pollMs: 2500 });
  const previous = useApi<GitReview[]>(
    apiPath("/api/git-activity/daily/reviews", { repo_id: props.repoId, date: props.date, timezone: props.timezone }),
  );

  useEffect(() => {
    if (catalogue.data?.selected && !model) setModel(catalogue.data.selected);
  }, [catalogue.data, model]);

  useEffect(() => {
    if (active.data && (active.data.status === "completed" || active.data.status === "failed")) {
      previous.reload();
      props.onDone();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active.data?.status]);

  async function submit() {
    setSubmitting(true);
    try {
      const created = await api.post<GitReview>("/api/git-activity/daily/reviews", {
        repo_id: props.repoId,
        date: props.date,
        timezone: props.timezone,
        mode,
        profile,
        model: model || undefined,
      });
      setActiveId(created.id);
      toast.push("success", mode === "explain" ? "Explanation requested" : "Review requested", "The local model is examining the full day.");
    } catch (caught) {
      toast.push("error", "Daily review failed", errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={`Daily ${mode === "explain" ? "explanation" : "review"} — ${props.date}`} wide onClose={props.onClose}>
      <p className="muted">
        {mode === "explain"
          ? "Explains what the day's work accomplished, grouped into workstreams. Grounded in the full day's diffs."
          : "Critically examines the day's combined changes for defects, regressions and architectural problems."}{" "}
        Local-only execution; nothing is committed or pushed.
      </p>
      {!catalogue.data ? <LoadingBlock label="Loading models" compact /> : <p className="muted">{catalogue.data.detail}</p>}
      <div className="form-stack">
        <label className="field">
          <span>Mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as "explain" | "review")}>
            <option value="explain">Explain with AI</option>
            <option value="review">Review with AI</option>
          </select>
        </label>
        <label className="field">
          <span>Model</span>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">Select a model…</option>
            {(catalogue.data?.models ?? []).map((item) => (
              <option value={item.id} key={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Profile</span>
          <select value={profile} onChange={(e) => setProfile(e.target.value)}>
            <option value="code">Code review</option>
            <option value="prose">Prose / manuscript review</option>
          </select>
        </label>
        <button className="button button-primary" onClick={() => void submit()} disabled={submitting || !model}>
          <Sparkles size={14} /> {submitting ? "Submitting…" : mode === "explain" ? "Explain day" : "Review day"}
        </button>
      </div>
      {active.data ? <ReviewCard review={active.data} /> : null}
      <Section title="Previous daily reviews" description={`${previous.data?.length ?? 0} recorded for this day`}>
        {(previous.data ?? []).map((review) => (
          <ReviewCard key={review.id} review={review} />
        ))}
      </Section>
    </Modal>
  );
}

// ------------------------------------------------------------ commit detail
function CommitDetailModal(props: {
  repoId: string;
  sha: string;
  onClose: () => void;
  onPrompt: (repoId: string, sha: string) => void;
  onReview: (repoId: string, sha: string) => void;
}) {
  const detail = useApi<{
    repo: GitRepo;
    commit: {
      sha: string;
      short_sha: string;
      subject: string;
      body: string;
      author_name: string;
      author_email: string;
      committer_ts: number;
      committer_tz: string;
      parents: string[];
      branches: string[];
      files_changed: number;
      insertions: number;
      deletions: number;
      is_merge: boolean;
      is_root: boolean;
      reachable: boolean;
    };
    reviews: GitReview[];
  }>(apiPath(`/api/git-activity/commits/${props.repoId}/${props.sha}`));
  const diff = useApi<{
    patch: string;
    truncated: boolean;
    total_bytes: number;
    files: Array<{ path: string; insertions: number | null; deletions: number | null; binary: boolean; status: string }>;
    mode: string;
    fingerprint: string;
  }>(apiPath(`/api/git-activity/commits/${props.repoId}/${props.sha}/diff`));

  return (
    <Modal title={detail.data ? detail.data.commit.subject : "Commit"} wide onClose={props.onClose}>
      {detail.loading && !detail.data ? <LoadingBlock label="Loading commit" /> : null}
      {detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} /> : null}
      {detail.data ? (
        <>
          <dl className="key-values">
            <div>
              <dt>SHA</dt>
              <dd>
                <code>{detail.data.commit.sha}</code>
              </dd>
            </div>
            <div>
              <dt>Author</dt>
              <dd>
                {detail.data.commit.author_name} &lt;{detail.data.commit.author_email}&gt;
              </dd>
            </div>
            <div>
              <dt>Committed</dt>
              <dd>
                {new Date(detail.data.commit.committer_ts * 1000).toLocaleString()} {detail.data.commit.committer_tz}
              </dd>
            </div>
            <div>
              <dt>Parents</dt>
              <dd>{detail.data.commit.parents.length ? detail.data.commit.parents.join(", ") : "(root commit)"}</dd>
            </div>
            <div>
              <dt>Stats</dt>
              <dd>
                {detail.data.commit.files_changed} files, +{detail.data.commit.insertions}/-{detail.data.commit.deletions}
                {detail.data.commit.is_merge ? " · merge (first-parent comparison)" : ""}
              </dd>
            </div>
          </dl>
          {detail.data.commit.body ? <pre className="pre-wrap">{detail.data.commit.body}</pre> : null}
          <div className="toolbar">
            <button className="button button-secondary button-small" onClick={() => props.onPrompt(props.repoId, props.sha)}>
              <Copy size={13} /> Copy review prompt
            </button>
            <button className="button button-primary button-small" onClick={() => props.onReview(props.repoId, props.sha)}>
              <Sparkles size={13} /> Review with AI
            </button>
          </div>
          <Section title="Changed files" description={diff.data ? `${diff.data.files.length} files · ${diff.data.mode}` : undefined}>
            {diff.loading && !diff.data ? <LoadingBlock label="Loading diff" compact /> : null}
            {(diff.data?.files ?? []).map((file) => (
              <p key={file.path} className="row-line">
                <code>{file.path}</code>
                <span className="muted">
                  {file.binary ? "binary" : `+${file.insertions ?? 0}/-${file.deletions ?? 0}`}
                </span>
              </p>
            ))}
          </Section>
          <Section title="Diff" description={diff.data ? `fingerprint ${diff.data.fingerprint}${diff.data.truncated ? " · truncated to context budget" : ""}` : undefined}>
            {diff.data ? <pre className="diff-block">{diff.data.patch.slice(0, 30000)}</pre> : null}
            {diff.data && diff.data.patch.length > 30000 ? (
              <p className="muted">Showing the first 30,000 characters of a larger patch.</p>
            ) : null}
          </Section>
          <Section title="Reviews" description={`${detail.data.reviews.length} recorded`}>
            {detail.data.reviews.length === 0 ? <p className="muted">No reviews yet for this commit.</p> : null}
            {detail.data.reviews.map((review) => (
              <ReviewCard key={review.id} review={review} />
            ))}
          </Section>
        </>
      ) : null}
    </Modal>
  );
}

// ------------------------------------------------------------------ prompt
function PromptModal(props: { repoId: string; sha: string; onClose: () => void }) {
  const toast = useToast();
  const [profile, setProfile] = useState("code");
  const [copying, setCopying] = useState(false);
  const prompt = useApi<{
    markdown: string;
    prompt_hash: string;
    diff_hash: string;
    context_fingerprint: string;
    size_chars: number;
    truncated: boolean;
    redactions: string[];
    redaction_count: number;
    coverage: Record<string, unknown>;
    files: Array<{ path: string }>;
    diff_mode: string;
    diff_bytes: number;
  }>(apiPath(`/api/git-activity/commits/${props.repoId}/${props.sha}/prompt`, { profile }));

  async function copy() {
    if (!prompt.data) return;
    setCopying(true);
    try {
      await copyText(prompt.data.markdown);
      toast.push("success", "Review prompt copied", `${prompt.data.size_chars} chars — paste into GPT-6, Claude or Codex.`);
    } catch (caught) {
      toast.push("error", "Copy failed", errorMessage(caught));
    } finally {
      setCopying(false);
    }
  }

  function download() {
    if (!prompt.data) return;
    const blob = new Blob([prompt.data.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `review-${props.sha.slice(0, 8)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Modal title="Copy review prompt" wide onClose={props.onClose}>
      <p className="muted">No model call is made. The package contains project context, commit metadata and the exact diff.</p>
      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Review profile</span>
          <select value={profile} onChange={(event) => setProfile(event.target.value)}>
            <option value="code">Code review</option>
            <option value="prose">Prose / manuscript review</option>
          </select>
        </label>
        {prompt.data ? (
          <>
            <span className="toolbar-count">
              {prompt.data.size_chars} chars{prompt.data.truncated ? " · partial coverage" : " · full coverage"} ·{" "}
              {prompt.data.redaction_count} redactions
            </span>
            <button className="button button-primary button-small" onClick={() => void copy()} disabled={copying}>
              <Copy size={13} /> {copying ? "Copying…" : "Copy"}
            </button>
            <button className="button button-secondary button-small" onClick={download}>
              Save .md
            </button>
          </>
        ) : null}
      </div>
      {prompt.loading && !prompt.data ? <LoadingBlock label="Building review package" /> : null}
      {prompt.error ? <ErrorState message={prompt.error.message} onRetry={prompt.reload} /> : null}
      {prompt.data ? <pre className="diff-block">{prompt.data.markdown.slice(0, 20000)}</pre> : null}
      {prompt.data && prompt.data.markdown.length > 20000 ? (
        <p className="muted">Preview shows the first 20,000 characters; Copy and Save include the full package.</p>
      ) : null}
    </Modal>
  );
}

// ------------------------------------------------------------------ review
function ReviewModal(props: { repoId: string; sha: string; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const catalogue = useApi<ReviewModelCatalogue>("/api/git-activity/models");
  const existing = useApi<GitReview[]>(
    apiPath("/api/git-activity/reviews", { repo_id: props.repoId, sha: props.sha }),
  );
  const [model, setModel] = useState("");
  const [profile, setProfile] = useState("code");
  const [submitting, setSubmitting] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = useApi<GitReview>(activeId ? `/api/git-activity/reviews/${activeId}` : null, { pollMs: 2500 });

  useEffect(() => {
    if (catalogue.data?.selected && !model) setModel(catalogue.data.selected);
  }, [catalogue.data, model]);

  useEffect(() => {
    if (active.data && (active.data.status === "completed" || active.data.status === "failed")) {
      existing.reload();
      props.onDone();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active.data?.status]);

  async function submit() {
    setSubmitting(true);
    try {
      const created = await api.post<GitReview>("/api/git-activity/reviews", {
        repo_id: props.repoId,
        sha: props.sha,
        model: model || undefined,
        profile,
      });
      setActiveId(created.id);
      toast.push("success", "Review requested", "The local model is reviewing the diff.");
    } catch (caught) {
      toast.push("error", "Review failed", errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Review with AI" wide onClose={props.onClose}>
      <p className="muted">
        Executes through the configured local model only. A non-loopback endpoint is refused — the request fails closed
        instead of falling back to a remote or premium model. Nothing is committed, pushed or modified.
      </p>
      {!catalogue.data ? <LoadingBlock label="Loading models" compact /> : <p className="muted">{catalogue.data.detail}</p>}
      <div className="form-stack">
        <label className="field">
          <span>Model</span>
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            <option value="">Select a model…</option>
            {(catalogue.data?.models ?? []).map((item) => (
              <option value={item.id} key={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Profile</span>
          <select value={profile} onChange={(event) => setProfile(event.target.value)}>
            <option value="code">Code review</option>
            <option value="prose">Prose / manuscript review</option>
          </select>
        </label>
        <button className="button button-primary" onClick={() => void submit()} disabled={submitting || !model}>
          <Sparkles size={14} /> {submitting ? "Submitting…" : "Submit review"}
        </button>
      </div>
      {active.data ? <ReviewCard review={active.data} /> : null}
      <Section title="Previous reviews" description={`${existing.data?.length ?? 0} recorded`}>
        {(existing.data ?? []).map((review) => (
          <ReviewCard key={review.id} review={review} />
        ))}
      </Section>
    </Modal>
  );
}

function ReviewCard(props: { review: GitReview }) {
  const { review } = props;
  const toast = useToast();
  const [feedback, setFeedback] = useState("");

  async function sendFeedback(rating: string) {
    try {
      await api.post(`/api/git-activity/reviews/${review.id}/feedback`, { rating, detail: feedback });
      toast.push("success", "Feedback recorded");
      setFeedback("");
    } catch (caught) {
      toast.push("error", "Feedback failed", errorMessage(caught));
    }
  }

  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>{review.verdict ?? review.status}</strong>
        <span className="activity-type">
          {review.requested_model}
          {review.observed_model && review.observed_model !== review.requested_model ? ` → ${review.observed_model}` : ""}
        </span>
        <SimpleStatusBadge state={review.status === "completed" ? "running" : review.status === "failed" ? "misconfigured" : "not_checked"} label={review.status} />
      </div>
      <p className="muted">
        {formatDateTime(review.created_at)} · route {review.model_route || "configured-local-openai"} · prompt{" "}
        {review.prompt_hash.slice(0, 8)} · diff {review.diff_hash.slice(0, 8)}
      </p>
      {review.error ? <InlineError message={review.error} /> : null}
      {review.summary ? <pre className="pre-wrap">{review.summary.slice(0, 8000)}</pre> : null}
      {(review.findings ?? []).length > 0 ? (
        <ul>
          {(review.findings ?? []).slice(0, 20).map((finding, index) => (
            <li key={index} className="muted">
              {typeof finding === "string" ? finding : (finding.observation ?? JSON.stringify(finding))}
            </li>
          ))}
        </ul>
      ) : null}
      {review.status === "completed" ? (
        <div className="toolbar">
          <input
            value={feedback}
            placeholder="Feedback note (optional)…"
            onChange={(event) => setFeedback(event.target.value)}
            aria-label="Feedback note"
          />
          {["useful", "correct", "false_positive", "missed_issue"].map((rating) => (
            <button key={rating} className="button button-ghost button-small" onClick={() => void sendFeedback(rating)}>
              {rating}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------- range
function RangeModal(props: { repos: GitRepo[]; selected: Set<string>; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    markdown: string;
    size_chars: number;
    truncated: boolean;
    redaction_count: number;
    coverage: Record<string, unknown>;
  } | null>(null);

  const byRepo = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const key of props.selected) {
      const separator = key.indexOf(":");
      const repoId = key.slice(0, separator);
      const sha = key.slice(separator + 1);
      groups.set(repoId, [...(groups.get(repoId) ?? []), sha]);
    }
    return groups;
  }, [props.selected]);

  async function build() {
    const entries = Array.from(byRepo.entries());
    if (entries.length !== 1) {
      toast.push("error", "Select commits from one project", "Range review covers a single repository.");
      return;
    }
    const [repoId, shas] = entries[0];
    setBusy(true);
    try {
      const package_ = await api.post<{
        markdown: string;
        size_chars: number;
        truncated: boolean;
        redaction_count: number;
        coverage: Record<string, unknown>;
      }>("/api/git-activity/range/prompt", { repo_id: repoId, shas });
      setResult(package_);
    } catch (caught) {
      toast.push("error", "Range prompt failed", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Range review" wide onClose={props.onClose}>
      <p className="muted">
        {props.selected.size} commits selected across {byRepo.size} {byRepo.size === 1 ? "project" : "projects"}.
        Non-contiguous selections are exported as separate per-commit sections with explicit comparison semantics —
        never a silently merged diff.
      </p>
      <button className="button button-primary button-small" onClick={() => void build()} disabled={busy}>
        {busy ? "Building…" : "Build range prompt"}
      </button>
      {result ? (
        <>
          <p className="muted">
            {result.size_chars} chars{result.truncated ? " · partial coverage" : ""} · {result.redaction_count} redactions
          </p>
          <div className="toolbar">
            <button
              className="button button-secondary button-small"
              onClick={() => {
                void copyText(result.markdown).then(() => toast.push("success", "Range prompt copied"));
              }}
            >
              <Copy size={13} /> Copy
            </button>
          </div>
          <pre className="diff-block">{result.markdown.slice(0, 20000)}</pre>
        </>
      ) : null}
    </Modal>
  );
}

// --------------------------------------------------------------- repo panel
function RepoPanelModal(props: { repoId: string; onClose: () => void }) {
  const toast = useToast();
  const repo = useApi<GitRepo>(`/api/git-activity/repos/${props.repoId}`);
  const context = useApi<{
    has_agents: boolean;
    has_description: boolean;
    context_status: string;
    agents_path: string | null;
    description_path: string | null;
    nested_agents: Array<{ path: string }>;
  }>(`/api/git-activity/context/${props.repoId}`);
  const commits = useApi<GitTimeline>(apiPath("/api/git-activity/timeline", { repo_id: props.repoId, preset: "30d", limit: 20 }));
  const [proposalKind, setProposalKind] = useState("description");
  const [proposal, setProposal] = useState<{ proposal: string; path: string; exists: boolean } | null>(null);
  const [editing, setEditing] = useState("");
  const [applying, setApplying] = useState(false);

  async function propose() {
    try {
      const result = await api.post<{ proposal: string; path: string; exists: boolean }>(
        `/api/git-activity/context/${props.repoId}/propose`,
        { kind: proposalKind },
      );
      setProposal(result);
      setEditing(result.proposal);
    } catch (caught) {
      toast.push("error", "Proposal failed", errorMessage(caught));
    }
  }

  async function apply() {
    setApplying(true);
    try {
      await api.post(`/api/git-activity/context/${props.repoId}/apply`, {
        kind: proposalKind,
        content: editing,
        confirm: true,
      });
      toast.push("success", "Context updated", "The document was written after explicit approval.");
      setProposal(null);
      context.reload();
    } catch (caught) {
      toast.push("error", "Apply failed", errorMessage(caught));
    } finally {
      setApplying(false);
    }
  }

  return (
    <Modal title={repo.data?.name ?? "Project"} wide onClose={props.onClose}>
      {repo.data ? (
        <dl className="key-values">
          <div>
            <dt>Path</dt>
            <dd>
              <code>{repo.data.path}</code>
            </dd>
          </div>
          <div>
            <dt>Root</dt>
            <dd>{repo.data.root_path}</dd>
          </div>
          <div>
            <dt>Branch</dt>
            <dd>{repo.data.branch ?? "—"} · {repo.data.head_sha?.slice(0, 8) ?? "—"}</dd>
          </div>
          <div>
            <dt>Context</dt>
            <dd>
              {context.data
                ? `${context.data.context_status} (AGENTS.md ${context.data.has_agents ? "present" : "missing"}, DESCRIPTION.md ${context.data.has_description ? "present" : "missing"})`
                : "…"}
            </dd>
          </div>
        </dl>
      ) : null}
      <Section title="Prepare project context" description="Proposals are reviewable diffs. Nothing is written without approval.">
        <div className="toolbar">
          <label className="select-field">
            <select value={proposalKind} onChange={(event) => setProposalKind(event.target.value)}>
              <option value="description">DESCRIPTION.md</option>
              <option value="agents">AGENTS.md</option>
            </select>
          </label>
          <button className="button button-secondary button-small" onClick={() => void propose()}>
            Prepare proposal
          </button>
        </div>
        {proposal ? (
          <>
            <p className="muted">
              Target: <code>{proposal.path}</code> ({proposal.exists ? "update" : "new file"})
            </p>
            <textarea rows={14} value={editing} onChange={(event) => setEditing(event.target.value)} aria-label="Proposed context" />
            <div className="toolbar">
              <button className="button button-primary button-small" onClick={() => void apply()} disabled={applying || !editing.trim()}>
                {applying ? "Applying…" : "Approve and apply"}
              </button>
            </div>
          </>
        ) : null}
      </Section>
      <Section title="Recent commits" description="Last 20 indexed commits in this project.">
        {(commits.data?.items ?? []).map((commit) => (
          <p key={commit.sha} className="row-line">
            <code>{commit.short_sha}</code> {commit.subject}
            <span className="muted"> · {commitTime(commit.committer_ts)}</span>
          </p>
        ))}
      </Section>
    </Modal>
  );
}

// ------------------------------------------------------------------- roots
function RootsModal(props: { roots: GitActivityRoot[]; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("software");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/git-activity/roots", { path, name, category });
      toast.push("success", "Root added");
      setPath("");
      setName("");
      props.onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function toggle(item: GitActivityRoot, field: "enabled" | "git_enabled") {
    try {
      await api.patch(`/api/git-activity/roots?path=${encodeURIComponent(item.path)}`, {
        [field]: !item[field],
      });
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  async function remove(item: GitActivityRoot) {
    if (!window.confirm(`Stop monitoring ${item.path}? Indexed history and reviews are retained.`)) return;
    try {
      await api.delete(`/api/git-activity/roots?path=${encodeURIComponent(item.path)}&retain_history=true`);
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Remove failed", errorMessage(caught));
    }
  }

  return (
    <Modal title="Activity roots" wide onClose={props.onClose}>
      <p className="muted">
        Repositories are discovered beneath these roots. Removing a root stops monitoring but retains indexed history
        and reviews.
      </p>
      {props.roots.map((item) => (
        <div key={item.path} className="panel">
          <div className="activity-head">
            <strong>{item.name}</strong>
            <Tag>{item.category}</Tag>
            {!item.enabled ? <Tag>disabled</Tag> : null}
            {!item.git_enabled ? <Tag>git off</Tag> : null}
          </div>
          <p className="muted">
            <code>{item.path}</code>
          </p>
          <p className="muted">
            Last sync: {item.last_git_sync_at ? formatDateTime(item.last_git_sync_at) : "never"}
            {item.last_git_error ? ` · error: ${item.last_git_error}` : ""}
          </p>
          <div className="toolbar">
            <button className="button button-ghost button-small" onClick={() => void toggle(item, "enabled")}>
              {item.enabled ? "Disable" : "Enable"}
            </button>
            <button className="button button-ghost button-small" onClick={() => void toggle(item, "git_enabled")}>
              {item.git_enabled ? "Pause git sync" : "Resume git sync"}
            </button>
            <button className="button button-ghost button-small" onClick={() => void remove(item)}>
              Remove
            </button>
          </div>
        </div>
      ))}
      <Section title="Add root" description="Must be an existing readable directory.">
        <form className="form-stack" onSubmit={(event) => void add(event)}>
          <InlineError message={error} />
          <label className="field">
            <span>Directory</span>
            <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\Projects" required />
          </label>
          <label className="field">
            <span>Display name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Projects" />
          </label>
          <label className="field">
            <span>Category</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="software">Software</option>
              <option value="books">Books</option>
              <option value="research">Research</option>
              <option value="experiments">Experiments</option>
              <option value="documentation">Documentation</option>
            </select>
          </label>
          <button className="button button-primary" type="submit" disabled={saving || !path.trim()}>
            <Plus size={14} /> {saving ? "Adding…" : "Add root"}
          </button>
        </form>
      </Section>
    </Modal>
  );
}

// --------------------------------------------------------------- old events
function EventsView() {
  const projects = useApi<Project[]>("/api/projects");
  const [projectId, setProjectId] = useState("");
  const [type, setType] = useState("");
  const [date, setDate] = useState("");
  const [noteProject, setNoteProject] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteDetail, setNoteDetail] = useState("");
  const [noteEvidence, setNoteEvidence] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const since = date ? new Date(`${date}T00:00:00`).toISOString() : undefined;
  const path = apiPath("/api/activity", {
    project_id: projectId || undefined,
    type: type || undefined,
    since,
    limit: 200,
  });
  const activity = useApi<ActivityEvent[]>(path);
  const grouped = useMemo(() => {
    const groups = new Map<string, ActivityEvent[]>();
    for (const event of activity.data ?? []) {
      const key = new Date(event.occurred_at).toLocaleDateString();
      groups.set(key, [...(groups.get(key) ?? []), event]);
    }
    return Array.from(groups.entries());
  }, [activity.data]);

  async function addNote(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setNoteError(null);
    try {
      await api.post("/api/activity/notes", {
        project_id: noteProject || null,
        title: noteTitle,
        detail: noteDetail,
        evidence_ref: noteEvidence || null,
      });
      toast.push("success", "Note added to activity");
      setNoteTitle("");
      setNoteDetail("");
      setNoteEvidence("");
      activity.reload();
    } catch (caught) {
      setNoteError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Filter by project</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">All projects</option>
            {(projects.data ?? []).map((project) => (
              <option value={project.id} key={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by type</span>
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All types</option>
            {activityTypes.map((item) => (
              <option value={item} key={item}>
                {activityLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className="date-field">
          <Filter size={14} aria-hidden="true" />
          <span className="sr-only">Since date</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        {projectId || type || date ? (
          <button
            className="button button-ghost button-small"
            onClick={() => {
              setProjectId("");
              setType("");
              setDate("");
            }}
          >
            Clear filters
          </button>
        ) : null}
        <span className="toolbar-count">{activity.data?.length ?? 0} events</span>
      </div>

      <div className="activity-layout">
        <div>
          {activity.loading && !activity.data ? <LoadingBlock label="Loading activity" /> : null}
          {activity.error ? <ErrorState message={activity.error.message} onRetry={activity.reload} /> : null}
          {activity.data && activity.data.length === 0 ? (
            <EmptyState
              title="No activity matches"
              description="Add a note, save a checkpoint or run discovery to create a record."
              icon={<Activity size={20} />}
            />
          ) : null}
          {grouped.map(([day, events]) => (
            <section className="activity-day" key={day}>
              <h2>{formatDate(day)}</h2>
              <ul className="activity-feed">
                {events.map((event) => (
                  <li key={event.id}>
                    <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
                    <div className="activity-entry">
                      <div className="activity-head">
                        <strong>{event.title}</strong>
                        <span className="activity-type">{activityLabel(event.type)}</span>
                      </div>
                      <div className="activity-meta">
                        <span>{formatDateTime(event.occurred_at)}</span>
                        {event.project_name ? <span>{event.project_name}</span> : null}
                        {event.application_name ? <span>{event.application_name}</span> : null}
                        <span>{event.source}</span>
                        <ProvenanceBadge value={event.provenance} />
                      </div>
                      {event.detail ? <p className="activity-detail">{event.detail}</p> : null}
                      {event.evidence_ref ? (
                        <details className="evidence-list">
                          <summary>Evidence</summary>
                          <code>{event.evidence_ref}</code>
                        </details>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <aside className="activity-side">
          <Section title="Add a note" description="Notes are explicitly user-authored.">
            <form className="form-stack" onSubmit={(event) => void addNote(event)}>
              <InlineError message={noteError} />
              <label className="field">
                <span>Project (optional)</span>
                <select value={noteProject} onChange={(event) => setNoteProject(event.target.value)}>
                  <option value="">Workspace-wide</option>
                  {(projects.data ?? []).map((project) => (
                    <option value={project.id} key={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Title</span>
                <input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} required />
              </label>
              <label className="field">
                <span>Detail</span>
                <textarea rows={4} value={noteDetail} onChange={(event) => setNoteDetail(event.target.value)} />
              </label>
              <label className="field">
                <span>Evidence reference (optional)</span>
                <input
                  value={noteEvidence}
                  onChange={(event) => setNoteEvidence(event.target.value)}
                  placeholder="C:\Projects\...\report.json"
                />
              </label>
              <button className="button button-primary" type="submit" disabled={saving || !noteTitle.trim()}>
                <Plus size={14} /> {saving ? "Saving…" : "Add note"}
              </button>
            </form>
          </Section>

          <Section title="Provenance key">
            <dl className="provenance-key">
              <div>
                <dt>
                  <ProvenanceBadge value="verified_observation" />
                </dt>
                <dd>Read from a local system or process in this run.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="external_claim" />
                </dt>
                <dd>A statement made by another application, not independently verified.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="derived_observation" />
                </dt>
                <dd>Deterministically derived from recorded evidence.</dd>
              </div>
              <div>
                <dt>
                  <ProvenanceBadge value="ai_recommendation" />
                </dt>
                <dd>Advisory model output. It never replaces a human decision.</dd>
              </div>
            </dl>
          </Section>
        </aside>
      </div>
    </>
  );
}
