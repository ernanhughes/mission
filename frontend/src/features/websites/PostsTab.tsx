import { useEffect, useState } from "react";
import { ArrowLeft, Play, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  Section,
  Stat,
  Tag,
} from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import type {
  Website,
  WebsitePost,
  WebsitePostDetail,
  WebsitePostEvaluation,
  WebsitePostList,
  WebsitePostReview,
  WebsitePostsSummary,
} from "../../types/api";

const PAGE_SIZE = 20;

const statusTones: Record<string, string | undefined> = {
  published: "accent",
  draft: undefined,
  scheduled: undefined,
  unknown: undefined,
};

const freshnessTones: Record<string, string | undefined> = {
  current: "accent",
  stale: undefined,
  never: undefined,
};

function scoreLabel(post: WebsitePost): string {
  const summary = post.evaluation;
  if (summary.freshness === "current" && typeof summary.overall === "number") {
    return `${Math.round(summary.overall)} / 1000`;
  }
  if (summary.freshness === "stale") return "Stale";
  return "Not evaluated";
}

export function PostsTab({ site }: { site: Website }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [evaluated, setEvaluated] = useState("all");
  const [sort, setSort] = useState("date_desc");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setOffset(0);
    setSelected(null);
  }, [site.id, search, status, evaluated, sort]);

  if (!site.content_section) {
    return (
      <Section title="Posts" description="Blog articles with editorial evaluation.">
        <EmptyState
          title="No blog section confirmed"
          description="This website has no confirmed blog section (post/posts/blog/articles under content/), so there is no article list."
        />
      </Section>
    );
  }

  if (selected) {
    return <PostDetail site={site} identity={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <div>
      <PostsSummary site={site} />
      <Section
        title="Articles"
        description="Same scanner and identities as the Cultivation blog count — no second contradictory total."
      >
        <div className="toolbar">
          <label className="search-field">
            <span className="sr-only">Search articles</span>
            <input
              value={search}
              placeholder="Search title or path…"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="select-field">
            <span className="sr-only">Filter by publication status</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="scheduled">Scheduled</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label className="select-field">
            <span className="sr-only">Filter by evaluation status</span>
            <select value={evaluated} onChange={(event) => setEvaluated(event.target.value)}>
              <option value="all">All evaluations</option>
              <option value="current">Current</option>
              <option value="stale">Stale</option>
              <option value="unevaluated">Not evaluated</option>
            </select>
          </label>
          <label className="select-field">
            <span className="sr-only">Sort articles</span>
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="date_desc">Newest first</option>
              <option value="title_asc">Title A–Z</option>
              <option value="title_desc">Title Z–A</option>
              <option value="score_desc">Highest score</option>
              <option value="score_asc">Lowest score</option>
            </select>
          </label>
        </div>
        <PostsList
          site={site}
          search={search}
          status={status}
          evaluated={evaluated}
          sort={sort}
          offset={offset}
          onOffset={setOffset}
          onSelect={setSelected}
        />
      </Section>
    </div>
  );
}

function PostsSummary({ site }: { site: Website }) {
  const summary = useApi<WebsitePostsSummary>(
    `/api/websites/${site.id}/posts/summary`,
  );
  if (summary.loading && !summary.data) return <LoadingBlock label="Loading summary" compact />;
  if (!summary.data) return null;
  const data = summary.data;
  return (
    <div className="stat-strip">
      <Stat label="Published articles" value={data.published} />
      <Stat label="Current evaluations" value={data.evaluated_current} />
      <Stat label="Stale evaluations" value={data.evaluated_stale} />
      <Stat label="Not evaluated" value={data.unevaluated} />
      <Stat
        label="Average score"
        value={
          data.average_score == null
            ? "—"
            : `${Math.round(data.average_score)} / 1000`
        }
        detail={
          data.average_denominator > 0
            ? `across ${data.average_denominator} current ${data.rubric_id} v${data.rubric_version} evaluation${data.average_denominator === 1 ? "" : "s"}`
            : "no current evaluations"
        }
      />
      <Stat
        label="Coverage"
        value={data.coverage_percent == null ? "—" : `${Math.round(data.coverage_percent)}%`}
      />
    </div>
  );
}

function PostsList(props: {
  site: Website;
  search: string;
  status: string;
  evaluated: string;
  sort: string;
  offset: number;
  onOffset: (offset: number) => void;
  onSelect: (identity: string) => void;
}) {
  const params = new URLSearchParams({
    status: props.status,
    evaluated: props.evaluated,
    sort: props.sort,
    limit: String(PAGE_SIZE),
    offset: String(props.offset),
  });
  if (props.search.trim()) params.set("search", props.search.trim());
  const list = useApi<WebsitePostList>(
    `/api/websites/${props.site.id}/posts?${params.toString()}`,
  );
  if (list.loading && !list.data) return <LoadingBlock label="Loading articles" compact />;
  if (list.error) return <ErrorState message={list.error.message} onRetry={list.reload} />;
  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  if (items.length === 0) {
    return <p className="muted">No articles match these filters.</p>;
  }
  return (
    <div>
      {items.map((post) => (
        <div key={post.identity} className="panel review-card">
          <div className="activity-head">
            <button className="link-button" onClick={() => props.onSelect(post.identity)}>
              <strong>{post.title}</strong>
            </button>
            <Tag tone={statusTones[post.post_status]}>{post.post_status}</Tag>
            <Tag tone={freshnessTones[post.evaluation.freshness]}>
              {post.evaluation.freshness === "never" ? "Not evaluated" : post.evaluation.freshness}
            </Tag>
          </div>
          <p className="muted">
            {post.date ? post.date.slice(0, 10) : "Undated"} · <code>{post.relpath}</code> ·{" "}
            {scoreLabel(post)}
          </p>
        </div>
      ))}
      <div className="toolbar">
        <button
          className="button button-ghost button-small"
          disabled={props.offset === 0}
          onClick={() => props.onOffset(Math.max(0, props.offset - PAGE_SIZE))}
        >
          ← Newer
        </button>
        <span className="toolbar-count">
          {props.offset + 1}–{props.offset + items.length} of {total}
        </span>
        <button
          className="button button-ghost button-small"
          disabled={props.offset + items.length >= total}
          onClick={() => props.onOffset(props.offset + PAGE_SIZE)}
        >
          Older →
        </button>
      </div>
    </div>
  );
}

export function PostDetail({
  site,
  identity,
  onBack,
}: {
  site: Website;
  identity: string;
  onBack: () => void;
}) {
  const toast = useToast();
  const detail = useApi<WebsitePostDetail>(
    `/api/websites/${site.id}/posts/${encodeURIComponent(identity)}`,
  );
  const [evaluating, setEvaluating] = useState(false);
  const [showContent, setShowContent] = useState(false);

  async function evaluate(force: boolean) {
    setEvaluating(true);
    try {
      await api.post(
        `/api/websites/${site.id}/posts/${encodeURIComponent(identity)}/evaluate`,
        { force },
      );
      toast.push("success", "Evaluation recorded");
      detail.reload();
    } catch (caught) {
      toast.push("error", "Evaluation failed", errorMessage(caught));
    } finally {
      setEvaluating(false);
    }
  }

  if (detail.loading && !detail.data) return <LoadingBlock label="Loading article" />;
  if (detail.error) {
    return (
      <div>
        <button className="button button-ghost button-small" onClick={onBack}>
          <ArrowLeft size={14} /> Back to articles
        </button>
        <ErrorState message={detail.error.message} onRetry={detail.reload} />
      </div>
    );
  }
  if (!detail.data) return null;
  const data = detail.data;
  const current = data.current;
  return (
    <div>
      <button className="button button-ghost button-small" onClick={onBack}>
        <ArrowLeft size={14} /> Back to articles
      </button>
      <div className="book-workspace-head">
        <div>
          <span className="eyebrow">Article</span>
          <h2>{data.post.title}</h2>
          <div className="inline-meta">
            <Tag tone={statusTones[data.post.post_status]}>{data.post.post_status}</Tag>
            <span>{data.post.date ? data.post.date.slice(0, 10) : "Undated"}</span>
            <span>
              <code>{data.post.relpath}</code>
            </span>
          </div>
        </div>
        <div className="button-row">
          <button
            className="button button-ghost button-small"
            onClick={() => setShowContent((value) => !value)}
          >
            {showContent ? "Hide source" : "Show source"}
          </button>
          <button
            className="button button-primary button-small"
            disabled={evaluating || data.post.post_status !== "published"}
            onClick={() => void evaluate(false)}
            title={
              data.post.post_status !== "published"
                ? "Only published articles can be evaluated"
                : "Run an AI editorial review"
            }
          >
            <Play size={14} /> {evaluating ? "Evaluating…" : "Evaluate with AI"}
          </button>
          {current ? (
            <button
              className="button button-secondary button-small"
              disabled={evaluating}
              onClick={() => void evaluate(true)}
            >
              <RefreshCw size={14} /> Re-evaluate
            </button>
          ) : null}
        </div>
      </div>
      {showContent ? (
        <section className="panel">
          <span className="eyebrow">Source</span>
          <pre className="article-source">{data.content}</pre>
          {data.content_truncated ? (
            <p className="muted">Source truncated for display; the evaluator reads the full file.</p>
          ) : null}
        </section>
      ) : null}
      {current ? (
        <EvaluationCard key={current.id} site={site} evaluation={current} />
      ) : (
        <p className="muted">
          No current evaluation.{" "}
          {data.evaluations.length > 0
            ? "Past evaluations are listed below; the latest no longer matches the source."
            : "Run an AI editorial review to score this article against the blog rubric."}
        </p>
      )}
      {data.evaluations.length > 1 ||
      (data.evaluations.length === 1 && data.evaluations[0].id !== current?.id) ? (
        <Section title="Review history" description="Every evaluation is kept; edits invalidate, never delete.">
          {data.evaluations.map((evaluation) => (
            <p key={evaluation.id} className="row-line">
              <Tag tone={evaluation.stale ? undefined : "accent"}>
                {evaluation.stale ? "Stale" : "Current"}
              </Tag>{" "}
              <strong>
                {evaluation.overall == null ? "No score" : `${Math.round(evaluation.overall)} / 1000`}
              </strong>{" "}
              <span className="muted">
                {formatDateTime(evaluation.created_at)} · {evaluation.actual_model ?? evaluation.requested_model ?? "unknown model"} ·{" "}
                {evaluation.rubric_id} v{evaluation.rubric_version}
              </span>
            </p>
          ))}
        </Section>
      ) : null}
    </div>
  );
}

function EvaluationCard({
  site,
  evaluation,
}: {
  site: Website;
  evaluation: WebsitePostEvaluation;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const reviews = useApi<WebsitePostReview[]>(
    `/api/websites/${site.id}/evaluations/${evaluation.id}/reviews`,
  );
  const reviewByFinding = new Map((reviews.data ?? []).map((row) => [row.finding_id, row]));

  async function recordReview(findingId: string, decision: string) {
    setBusy(findingId + decision);
    try {
      await api.post(`/api/websites/${site.id}/evaluations/${evaluation.id}/reviews`, {
        finding_id: findingId,
        decision,
        reason: "",
        reviewer: "author",
      });
      toast.push("success", `Finding ${decision.toLowerCase()} recorded`);
      reviews.reload();
    } catch (caught) {
      toast.push("error", "Could not record review", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  if (evaluation.status !== "CURRENT") {
    return (
      <section className="panel review-card">
        <div className="activity-head">
          <strong>Evaluation {evaluation.status.toLowerCase()}</strong>
          <Tag>{evaluation.status}</Tag>
        </div>
        <p className="muted">
          {(evaluation.execution as Record<string, unknown>).error as string ??
            "No scores were recorded."}
        </p>
        <p className="muted">
          Model: {evaluation.actual_model ?? evaluation.requested_model ?? "unknown"} ·{" "}
          {formatDateTime(evaluation.created_at)}
        </p>
      </section>
    );
  }

  return (
    <section className="panel review-card">
      <div className="activity-head">
        <strong>
          {evaluation.overall == null ? "No score" : `${Math.round(evaluation.overall)} / 1000`}
        </strong>
        <Tag tone="accent">{evaluation.stale ? "Stale" : "Current"}</Tag>
        <Tag>
          {evaluation.rubric_id} v{evaluation.rubric_version}
        </Tag>
      </div>
      <p className="muted">
        {formatDateTime(evaluation.created_at)} ·{" "}
        {evaluation.actual_model ?? evaluation.requested_model ?? "unknown model"}
      </p>
      <p>{evaluation.assessment}</p>
      <div>
        <h4>Dimension scores</h4>
        {evaluation.dimensions.map((dim) => (
          <div key={dim.id} className="dim-row">
            <span className="dim-label">
              {dim.label} <span className="muted">{dim.score ?? "—"} / {dim.max_points}</span>
            </span>
            <span
              className="dim-bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={dim.max_points}
              aria-valuenow={dim.score ?? 0}
              aria-label={`${dim.label}: ${dim.score ?? "no score"} of ${dim.max_points}`}
            >
              <span
                style={{
                  width: `${dim.score == null ? 0 : Math.min(100, (dim.score / dim.max_points) * 100)}%`,
                }}
              />
            </span>
            {dim.explanation ? <p className="muted small">{dim.explanation}</p> : null}
          </div>
        ))}
      </div>
      <div className="two-col">
        <div>
          <h4>Strongest aspects</h4>
          <ul>
            {evaluation.strengths.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Most important weaknesses</h4>
          <ul>
            {evaluation.weaknesses.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
      <div>
        <h4>Top three improvements</h4>
        {evaluation.improvements.map((item) => (
          <ImprovementCard
            key={item.finding_id || item.rank}
            site={site}
            evaluationId={evaluation.id}
            item={item}
            review={reviewByFinding.get(item.finding_id) ?? null}
            busy={busy}
            onReview={recordReview}
          />
        ))}
      </div>
      {evaluation.findings.length > 0 ? (
        <div>
          <h4>Additional findings</h4>
          {evaluation.findings.map((finding) => (
            <FindingCard
              key={finding.finding_id}
              site={site}
              evaluationId={evaluation.id}
              finding={finding}
              review={reviewByFinding.get(finding.finding_id) ?? null}
              busy={busy}
              onReview={recordReview}
            />
          ))}
        </div>
      ) : null}
      {evaluation.uncertainty ? (
        <p className="muted">Uncertainty: {evaluation.uncertainty}</p>
      ) : null}
      {evaluation.limitations.length > 0 ? (
        <p className="muted">Limitations: {evaluation.limitations.join("; ")}</p>
      ) : null}
    </section>
  );
}

function QuoteNote({ quote, anchored }: { quote: string | null; anchored: boolean }) {
  if (!quote) return null;
  return (
    <blockquote className="writer-excerpt">
      {quote}
      {!anchored ? (
        <span className="tag">Unanchored — not found verbatim in the source</span>
      ) : null}
    </blockquote>
  );
}

function ReviewButtons({
  findingId,
  review,
  busy,
  onReview,
}: {
  findingId: string;
  review: WebsitePostReview | null;
  busy: string | null;
  onReview: (findingId: string, decision: string) => void;
}) {
  return (
    <div className="button-row">
      {review ? (
        <Tag tone="accent">{review.decision}</Tag>
      ) : (
        (["ACCEPT", "REJECT", "DEFER"] as const).map((decision) => (
          <button
            key={decision}
            className="button button-ghost button-small"
            disabled={busy !== null}
            onClick={() => onReview(findingId, decision)}
          >
            {busy === findingId + decision ? "…" : decision === "ACCEPT" ? "Accept" : decision === "REJECT" ? "Reject" : "Defer"}
          </button>
        ))
      )}
    </div>
  );
}

function ImprovementCard(props: {
  site: Website;
  evaluationId: string;
  item: WebsitePostEvaluation["improvements"][number];
  review: WebsitePostReview | null;
  busy: string | null;
  onReview: (findingId: string, decision: string) => void;
}) {
  const { item } = props;
  const findingId = item.finding_id || `improvement-${item.rank}`;
  return (
    <article className="writer-finding">
      <div className="writer-finding-head">
        <strong>
          #{item.rank} {item.title}
        </strong>
      </div>
      <p>
        <strong>Problem:</strong> {item.problem}
      </p>
      <p>
        <strong>Why it matters:</strong> {item.why_it_matters}
      </p>
      <p>
        <strong>Suggested improvement:</strong> {item.suggestion}
      </p>
      {item.source_heading ? (
        <p className="muted small">Near: {item.source_heading}</p>
      ) : null}
      <QuoteNote quote={item.source_quote} anchored={item.quote_anchored} />
      <ReviewButtons
        findingId={findingId}
        review={props.review}
        busy={props.busy}
        onReview={props.onReview}
      />
    </article>
  );
}

function FindingCard(props: {
  site: Website;
  evaluationId: string;
  finding: WebsitePostEvaluation["findings"][number];
  review: WebsitePostReview | null;
  busy: string | null;
  onReview: (findingId: string, decision: string) => void;
}) {
  const { finding } = props;
  return (
    <article className="writer-finding">
      <div className="writer-finding-head">
        <strong>{finding.title}</strong>
        <Tag>{finding.kind}</Tag>
      </div>
      <p>{finding.detail}</p>
      {finding.source_heading ? (
        <p className="muted small">Near: {finding.source_heading}</p>
      ) : null}
      <QuoteNote quote={finding.source_quote} anchored={finding.quote_anchored} />
      <ReviewButtons
        findingId={finding.finding_id}
        review={props.review}
        busy={props.busy}
        onReview={props.onReview}
      />
    </article>
  );
}
