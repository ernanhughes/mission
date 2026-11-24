import { useMemo, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import { timeAgo } from "../../lib/format";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  Section,
  Stat,
  Tag,
} from "../../components/ui";
import { PostDetail } from "./PostsTab";
import type {
  Website,
  WebsiteCollectionQuality,
  WebsitePostReview,
  WebsiteWriterObservation,
} from "../../types/api";

type CollectionView =
  | "attention"
  | "all"
  | "stale"
  | "unevaluated"
  | "weakest"
  | "duplicates"
  | "provisional";

const VIEW_LABELS: Array<{ id: CollectionView; label: string }> = [
  { id: "attention", label: "Needs attention" },
  { id: "all", label: "All evaluated" },
  { id: "stale", label: "Stale" },
  { id: "unevaluated", label: "Not evaluated" },
  { id: "weakest", label: "Weakest scores" },
  { id: "duplicates", label: "Duplication candidates" },
  { id: "provisional", label: "Provisional" },
];

export function CollectionTab({ site }: { site: Website }) {
  const collection = useApi<WebsiteCollectionQuality>(
    site.content_section ? `/api/websites/${site.id}/collection/quality` : null,
  );
  const [view, setView] = useState<CollectionView>("attention");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const rows = useMemo(() => buildRows(collection.data, view, search), [collection.data, view, search]);

  if (!site.content_section) {
    return (
      <Section title="Collection" description="Collection quality needs a confirmed blog section.">
        <EmptyState title="No blog section" description="Confirm a blog section to build the collection map." />
      </Section>
    );
  }

  if (selected) {
    return (
      <div>
        <button className="button button-ghost button-small" type="button" onClick={() => setSelected(null)}>
          <ArrowLeft size={14} /> Back to collection
        </button>
        <PostDetail site={site} identity={selected} onBack={() => setSelected(null)} />
      </div>
    );
  }

  return (
    <div className="stack">
      <Section
        title="Collection quality"
        description="Read-only projection of stored editorial evaluations plus live file state. Never scores, never merges, never auto-evaluates."
        actions={
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={() => collection.reload()}
            disabled={collection.loading}
          >
            <RefreshCw size={14} /> {collection.loading ? "Reading…" : "Refresh"}
          </button>
        }
      >
        {collection.loading && !collection.data ? <LoadingBlock label="Reading collection evidence" /> : null}
        {collection.error ? (
          <ErrorState message={collection.error.message} onRetry={collection.reload} />
        ) : null}
        {collection.data ? (
          <>
            <div className="stat-strip">
              <Stat label="Published" value={collection.data.coverage.published} />
              <Stat label="Current" value={collection.data.coverage.evaluated_current} />
              <Stat label="Stale" value={collection.data.coverage.evaluated_stale} />
              <Stat label="Not evaluated" value={collection.data.coverage.unevaluated} />
              <Stat
                label="Coverage"
                value={
                  collection.data.coverage.coverage_percent == null
                    ? "—"
                    : `${Math.round(collection.data.coverage.coverage_percent)}%`
                }
              />
              <Stat
                label="Average score"
                value={collection.data.scores.average == null ? "—" : Math.round(collection.data.scores.average)}
                detail={
                  collection.data.scores.n_scored > 0
                    ? `across ${collection.data.scores.n_scored} current ${collection.data.scores.rubric_id} evaluation${collection.data.scores.n_scored === 1 ? "" : "s"}`
                    : "no current evaluations"
                }
              />
            </div>
            <div className="toolbar" role="group" aria-label="Collection filters">
              <label className="search-field">
                <span className="sr-only">Search collection</span>
                <input
                  value={search}
                  placeholder="Search title or path…"
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
              <label className="select-field">
                <span className="sr-only">Filter collection view</span>
                <select value={view} onChange={(event) => setView(event.target.value as CollectionView)}>
                  {VIEW_LABELS.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {rows.length === 0 ? (
              <p className="muted">No articles match this view.</p>
            ) : (
              <div className="stack">
                {rows.map((row) =>
                  row.kind === "post" ? (
                    <PostRow key={row.identity} site={site} row={row} onOpen={() => setSelected(row.identity)} />
                  ) : row.kind === "candidate" ? (
                    <CandidateCard key={row.candidate.candidate_id} candidate={row.candidate} />
                  ) : (
                    <ProvisionalCard key={row.name} name={row.name} entry={row.entry} />
                  ),
                )}
              </div>
            )}
            <p className="muted small">
              Computed {collection.data.generated_at} by {collection.data.generator}.{" "}
              {collection.data.scores.rows_capped ? "Row examination was capped; counts are bounded, not exact." : null}{" "}
              Duplication candidates stay pending until a human decides; provisional sections stay
              unavailable until paired evidence exists.
            </p>
          </>
        ) : null}
      </Section>
    </div>
  );
}

type CollectionRow =
  | {
      kind: "post";
      identity: string;
      title: string;
      relpath: string;
      state: string;
      overall: number | null;
      evaluationId: string | null;
      detail: string;
    }
  | { kind: "candidate"; candidate: WebsiteCollectionQuality["duplication_candidates"][number] }
  | { kind: "provisional"; name: string; entry: { status: string; reason: string } };

function matchesSearch(row: CollectionRow, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) return true;
  if (row.kind !== "post") return true;
  return (
    row.title.toLowerCase().includes(query) ||
    row.identity.toLowerCase().includes(query) ||
    row.relpath.toLowerCase().includes(query)
  );
}

function buildRows(
  data: WebsiteCollectionQuality | null,
  view: CollectionView,
  search: string,
): CollectionRow[] {
  if (!data) return [];
  const stale = data.review_queues.stale_oldest_first.map((entry) => ({
    kind: "post" as const,
    identity: entry.identity,
    title: entry.title ?? entry.identity,
    relpath: entry.relpath ?? entry.identity,
    state: "stale",
    overall: entry.overall ?? null,
    evaluationId: entry.evaluation_id ?? null,
    detail: `Evaluated ${String(entry.evaluated_digest ?? "?").slice(0, 12)}… vs live ${String(entry.live_digest ?? "?").slice(0, 12)}…`,
  }));
  const unevaluated = data.review_queues.unevaluated_oldest_first.map((entry) => ({
    kind: "post" as const,
    identity: entry.identity,
    title: entry.title ?? entry.identity,
    relpath: entry.relpath ?? entry.identity,
    state: "unevaluated",
    overall: null,
    evaluationId: null,
    detail: "No stored editorial evaluation.",
  }));
  const weakest = data.scores.weakest.map((entry) => ({
    kind: "post" as const,
    identity: entry.identity,
    title: entry.title ?? entry.identity,
    relpath: entry.relpath ?? entry.identity,
    state: "weakest",
    overall: entry.overall,
    evaluationId: entry.evaluation_id,
    detail: `Weakest score ${Math.round(entry.overall)} / 1000.`,
  }));
  const candidates: CollectionRow[] = data.duplication_candidates.map((candidate) => ({
    kind: "candidate" as const,
    candidate,
  }));
  const provisional: CollectionRow[] = Object.entries(data.provisional).map(([name, entry]) => ({
    kind: "provisional" as const,
    name,
    entry,
  }));
  let rows: CollectionRow[];
  switch (view) {
    case "stale":
      rows = stale;
      break;
    case "unevaluated":
      rows = unevaluated;
      break;
    case "weakest":
      rows = weakest;
      break;
    case "duplicates":
      rows = candidates;
      break;
    case "provisional":
      rows = provisional;
      break;
    case "all": {
      const seen = new Set<string>();
      rows = [];
      for (const row of [...stale, ...unevaluated, ...weakest]) {
        if (seen.has(row.identity)) continue;
        seen.add(row.identity);
        rows.push({ ...row, state: row.state === "weakest" ? "current" : row.state });
      }
      break;
    }
    case "attention":
    default:
      rows = [...stale, ...unevaluated, ...weakest, ...candidates];
      break;
  }
  return rows.filter((row) => matchesSearch(row, search));
}

function PostRow({
  site,
  row,
  onOpen,
}: {
  site: Website;
  row: Extract<CollectionRow, { kind: "post" }>;
  onOpen: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <button className="link-button" onClick={onOpen}>
          <strong>{row.title}</strong>
        </button>
        <Tag tone={row.state === "stale" ? undefined : row.state === "unevaluated" ? "warn" : "accent"}>
          {row.state === "unevaluated" ? "Not evaluated" : row.state}
        </Tag>
        {row.overall != null ? <span className="muted small">{Math.round(row.overall)} / 1000</span> : null}
      </div>
      <p className="muted">
        <code>{row.relpath}</code> · {row.detail}
      </p>
      <div className="button-row">
        <button
          className="button button-ghost button-small"
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Hide evidence" : "Show evidence"}
        </button>
        <button className="button button-ghost button-small" type="button" onClick={onOpen}>
          Open full post
        </button>
      </div>
      {expanded ? (
        <div className="stack">
          <dl className="kv-list">
            <div className="key-value">
              <dt>Canonical identity</dt>
              <dd>
                <code>{row.identity}</code>
              </dd>
            </div>
            {row.evaluationId ? (
              <div className="key-value">
                <dt>Latest evaluation</dt>
                <dd>
                  <code>{row.evaluationId}</code>
                </dd>
              </div>
            ) : null}
          </dl>
          <HumanReviews siteId={site.id} evaluationId={row.evaluationId} />
          <WriterCheck siteId={site.id} identity={row.identity} />
        </div>
      ) : null}
    </div>
  );
}

function HumanReviews({ siteId, evaluationId }: { siteId: string; evaluationId: string | null }) {
  const reviews = useApi<WebsitePostReview[]>(
    evaluationId ? `/api/websites/${siteId}/evaluations/${evaluationId}/reviews` : null,
  );
  if (!evaluationId) return null;
  if (reviews.loading && !reviews.data) return <p className="muted small">Reading human reviews…</p>;
  const items = reviews.data ?? [];
  if (items.length === 0) return <p className="muted small">No human reviews recorded on the latest evaluation.</p>;
  const latest = items[items.length - 1];
  return (
    <p className="muted small">
      Human review: {items.length} recorded
      {latest ? ` · latest “${latest.decision}” by ${latest.reviewer} ${timeAgo(latest.created_at)}` : ""}.
    </p>
  );
}

function WriterCheck({ siteId, identity }: { siteId: string; identity: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WebsiteWriterObservation | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setFailed(null);
    try {
      const envelope = await api.post<WebsiteWriterObservation>(
        `/api/websites/${siteId}/posts/${encodeURIComponent(identity)}/writer-observation`,
        {},
      );
      setResult(envelope);
    } catch (caught) {
      setFailed(errorMessage(caught));
      toast.push("error", "Writer observation failed", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mini-block">
      <span>Writer observation (deterministic, on demand)</span>
      {!result && failed === null ? (
        <p className="muted small">
          No stored Writer evidence is kept. Running the check observes the live body now —
          it never modifies the article.
        </p>
      ) : null}
      <div className="button-row">
        <button
          className="button button-secondary button-small"
          type="button"
          disabled={busy}
          onClick={() => void run()}
        >
          {busy ? "Observing…" : result ? "Re-run Writer check" : "Run Writer check"}
        </button>
      </div>
      {failed ? <p className="resume-blocker">{failed}</p> : null}
      {result ? (
        <dl className="kv-list">
          <div className="key-value">
            <dt>Writer result</dt>
            <dd>
              <Tag tone={result.status === "complete" || result.status === "empty" ? "accent" : undefined}>
                {result.status}
              </Tag>{" "}
              <span className="muted">
                {result.findings.length} finding{result.findings.length === 1 ? "" : "s"} ·{" "}
                {result.dimensions.length} dimension{result.dimensions.length === 1 ? "" : "s"}
              </span>
            </dd>
          </div>
          <div className="key-value">
            <dt>Digest binding</dt>
            <dd>
              <code title={result.work_object.source_hash}>
                {result.work_object.source_hash.slice(0, 12)}…
              </code>{" "}
              <span className="muted">bound to the observed body bytes</span>
            </dd>
          </div>
          {result.findings.slice(0, 5).map((finding, index) => (
            <div className="key-value" key={`${finding.code}-${index}`}>
              <dt>{finding.code}</dt>
              <dd>{finding.claim}</dd>
            </div>
          ))}
          {result.limitations.slice(0, 2).map((limitation, index) => (
            <p className="muted small" key={index}>
              {limitation}
            </p>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function CandidateCard({
  candidate,
}: {
  candidate: WebsiteCollectionQuality["duplication_candidates"][number];
}) {
  const evidence = candidate.evidence as Record<string, unknown>;
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>
          {candidate.kind === "shared_title" ? "Shared title" : "Shared verbatim passage"}
        </strong>
        <Tag tone="warn">{candidate.decision}</Tag>
      </div>
      <p className="muted small">{candidate.note}</p>
      <p className="muted small">
        <code>{String(evidence["digest"] ?? "").slice(0, 16)}…</code>
      </p>
    </div>
  );
}

function ProvisionalCard({
  name,
  entry,
}: {
  name: string;
  entry: { status: string; reason: string };
}) {
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>{name.replace(/_/g, " ")}</strong>
        <Tag>{entry.status}</Tag>
      </div>
      <p className="muted small">{entry.reason}</p>
    </div>
  );
}
