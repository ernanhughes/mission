import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, FileSearch, Gauge, ListChecks, Play, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PathText,
  Section,
  SimpleStatusBadge,
  Stat,
  Tag,
} from "../components/ui";
import { formatDateTime, timeAgo, titleCase } from "../lib/format";
import type {
  IntegrationExecution,
  WriterBook,
  WriterChapter,
  WriterDecisionQueueItem,
  WriterDimension,
  WriterFinding,
  WriterWorkspace,
} from "../types/api";

const PROFILE = "technical-nonfiction-v1";
const DIMENSION_ORDER = [
  "paragraph_load",
  "sentence_load",
  "fragmentation",
  "rhythm",
  "lexical_accessibility",
  "section_structure",
];

function statusState(status: string | null | undefined): string {
  switch (String(status || "").toUpperCase()) {
    case "CURRENT":
      return "running";
    case "NEEDS_REVIEW":
      return "in_progress";
    case "STALE":
      return "stale";
    case "PARTIAL":
      return "pending";
    case "ERROR":
      return "launch_failed";
    case "NOT_RUN":
      return "not_checked";
    case "BLOCKED":
      return "blocked";
    case "NO_MANUSCRIPT":
      return "not_checked";
    case "RUNNING":
      return "in_progress";
    default:
      return "pending";
  }
}

function bandClass(band: string | null | undefined): string {
  return `band band-${String(band || "not_applicable")}`;
}

function dimensionFor(chapter: WriterChapter, id: string): WriterDimension | undefined {
  return chapter.dimensions.find((dimension) => dimension.id === id);
}

function riskLabel(risk: Record<string, any> | null | undefined): string {
  if (!risk) return "No risk recorded";
  const label =
    risk.label || risk.subdimension || risk.code || risk.kind || "Review signal";
  const value =
    risk.score != null
      ? `${risk.score} / ${titleCase(risk.status_band || "review")}`
      : titleCase(risk.severity || risk.status_band || "review");
  return `${label}: ${value}`;
}

function pipelineLabel(book: WriterBook, stage: "metadata" | "mri" | "strengthen"): string {
  const entry = book.pipeline?.[stage];
  if (!entry) return "Not tracked";
  return String(entry.status || "NOT_TRACKED").replace(/_/g, " ");
}

function scoreCell(dimension: WriterDimension | undefined) {
  if (!dimension) return <span className="muted">—</span>;
  if (dimension.score == null) {
    return <span className={bandClass(dimension.status_band)}>N/A</span>;
  }
  return (
    <span className={bandClass(dimension.status_band)}>
      {dimension.score}
      <small>{titleCase(dimension.status_band)}</small>
    </span>
  );
}

function decisionStateLabel(item: WriterDecisionQueueItem): string {
  if (item.state === "stale") return "Refresh evidence";
  if (item.state === "decided") return "Decided";
  if (item.state === "partial") {
    return `${item.decided_count} of ${item.count} decided`;
  }
  return "Undecided";
}

function severityTone(severity: string): string {
  if (severity === "high") return "danger";
  if (severity === "medium") return "accent";
  return "default";
}

function findingRow(finding: WriterFinding) {
  const location = finding.locator
    ? `${finding.locator.relative_path}:${finding.locator.line_start ?? "?"}`
    : "chapter-level";
  return (
    <article className="writer-finding" key={`${finding.code}-${finding.chapter_id}-${location}`}>
      <div className="writer-finding-head">
        <div>
          <Tag tone={finding.severity === "high" ? "danger" : finding.severity === "medium" ? "accent" : "default"}>
            {finding.severity.toUpperCase()}
          </Tag>
          <strong>{finding.code}</strong>
        </div>
        <code className="writer-locator">{location}</code>
      </div>
      <p>{finding.reason}</p>
      <div className="writer-recommendation">
        <span>Editorial guidance</span>
        <p>{finding.recommendation}</p>
      </div>
      {finding.locator?.excerpt ? (
        <blockquote className="writer-excerpt">{finding.locator.excerpt}</blockquote>
      ) : null}
    </article>
  );
}

export function WriterPage() {
  const workspace = useApi<WriterWorkspace>("/api/writer/books");
  const toast = useToast();
  const [selectedBookId, setSelectedBookId] = useState<string | null>(null);
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [running, setRunning] = useState(false);
  const [execution, setExecution] = useState<IntegrationExecution | null>(null);
  const [showAllQueue, setShowAllQueue] = useState(false);

  const books = workspace.data?.books ?? [];
  const selectedBook = useMemo(
    () => books.find((book) => book.project_id === selectedBookId) ?? books[0] ?? null,
    [books, selectedBookId],
  );
  const selectedChapter = useMemo(
    () =>
      selectedBook?.chapters.find((chapter) => chapter.chapter_id === selectedChapterId) ??
      selectedBook?.chapters[0] ??
      null,
    [selectedBook, selectedChapterId],
  );

  useEffect(() => {
    if (books.length && !books.some((book) => book.project_id === selectedBookId)) {
      setSelectedBookId(books[0].project_id);
      setSelectedChapterId(null);
    }
  }, [books, selectedBookId]);

  useEffect(() => {
    if (
      selectedBook &&
      selectedBook.chapters.length &&
      !selectedBook.chapters.some((chapter) => chapter.chapter_id === selectedChapterId)
    ) {
      setSelectedChapterId(selectedBook.chapters[0].chapter_id);
    }
  }, [selectedBook, selectedChapterId]);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.post<WriterWorkspace>("/api/writer/refresh");
      workspace.reload();
      toast.push("success", "Writer evidence refreshed", "Reader status is Writer's current report state.");
    } catch (caught) {
      toast.push("error", "Could not refresh Writer evidence", errorMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }

  async function runAudits() {
    setRunning(true);
    setExecution(null);
    try {
      let current = await api.post<IntegrationExecution>("/api/writer/audit", { profile: PROFILE });
      setExecution(current);
      for (let attempt = 0; attempt < 240; attempt += 1) {
        if (["succeeded", "failed", "cancelled"].includes(current.status)) break;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        current = await api.get<IntegrationExecution>(`/api/integrations/executions/${current.id}`);
        setExecution(current);
      }
      if (current.status === "succeeded") {
        toast.push("success", "Writer audits complete", "Reports were written only under Writer's artifact store.");
        workspace.reload();
      } else {
        toast.push("error", "Writer audit did not complete", current.error || "No report was accepted as current.");
      }
    } catch (caught) {
      toast.push("error", "Could not run Writer audits", errorMessage(caught));
    } finally {
      setRunning(false);
    }
  }

  if (workspace.loading && !workspace.data) {
    return (
      <div className="page">
        <PageHeader eyebrow="Writer" title="Book editing" description="Read-only Writer evidence." />
        <LoadingBlock label="Loading Writer editing evidence" />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Writer · Editing runtime"
        title="Book editing"
        description="Writer owns manuscript discovery, readability evidence and findings. Mission Control orchestrates Writer and preserves current, stale and not-run states."
        actions={
          <>
            <button className="button button-secondary" onClick={() => void refresh()} disabled={refreshing || running}>
              <RefreshCw size={15} /> {refreshing ? "Refreshing." : "Refresh Writer data"}
            </button>
            <button className="button button-primary" onClick={() => void runAudits()} disabled={running || refreshing}>
              <Play size={15} /> {running ? "Auditing." : "Run Writer audits"}
            </button>
          </>
        }
      />

      {workspace.error ? <ErrorState message={workspace.error.message} onRetry={workspace.reload} /> : null}
      {execution ? (
        <div className="writer-execution" role="status">
          <span className={`status-badge status-${statusState(execution.status === "succeeded" ? "CURRENT" : execution.status)}`}>
            <span className="status-dot" />
            {titleCase(execution.status)}
          </span>
          <span>
            {execution.status === "running" || execution.status === "queued"
              ? "Writer is auditing registered books. Progress is the execution record, not an invented percentage."
              : execution.error || execution.output || "Writer execution recorded."}
          </span>
          <code>{execution.id}</code>
        </div>
      ) : null}

      {workspace.data && !workspace.data.available ? (
        <InlineError
          message={
            workspace.data.error
              ? `${workspace.data.detail} ${workspace.data.error}`
              : workspace.data.detail
          }
        />
      ) : null}

      {workspace.data ? (
        <div className="writer-stats">
          <Stat label="Registered" value={workspace.data.totals.books ?? 0} detail="Writer projects observed" />
          <Stat label="With manuscript" value={workspace.data.totals.with_manuscript ?? 0} detail="Recognised Markdown chapters" />
          <Stat label="Audited" value={workspace.data.totals.audited ?? 0} detail="Stored editing reports" />
          <Stat label="Need review" value={workspace.data.totals.needs_review ?? 0} detail="Current editorial signals" />
          <Stat label="Stale" value={workspace.data.totals.stale ?? 0} detail="Source fingerprint changed" />
          <Stat label="Not run" value={workspace.data.totals.not_run ?? 0} detail="No evidence, not a pass" />
        </div>
      ) : null}

      {workspace.data?.decision_queue.length ? (
        <Section
          title="Decision queue"
          description="Writer findings grouped by code and severity, highest consequence first. Open a representative case in Workbench; Confirm, Dismiss and Defer are recorded there, never here."
          actions={
            <div className="tag-row">
              <Tag tone="accent">{workspace.data.decision_totals?.groups ?? 0} groups</Tag>
              <Tag>{workspace.data.decision_totals?.undecided ?? 0} undecided findings</Tag>
              {workspace.data.decision_totals?.confirmed ? (
                <Tag>{workspace.data.decision_totals.confirmed} confirmed</Tag>
              ) : null}
            </div>
          }
        >
          <div className="writer-decision-note">
            <ListChecks size={16} />
            <span>
              A group is one repeated editorial pattern. Reviewing the representative and choosing
              a book-wide scope in Workbench records that pattern once, not once per instance.
            </span>
          </div>
          <div className="writer-decision-queue">
            {(showAllQueue
              ? workspace.data.decision_queue
              : workspace.data.decision_queue.slice(0, 10)
            ).map((item) => (
              <article className="writer-decision-card" key={item.id}>
                <div className="writer-decision-head">
                  <Tag tone={severityTone(item.severity)}>{item.severity.toUpperCase()}</Tag>
                  <strong>{item.code}</strong>
                  <span className="writer-decision-state">{decisionStateLabel(item)}</span>
                  <span className="writer-decision-count">
                    {item.count} finding{item.count === 1 ? "" : "s"} in {item.chapter_count} chapter
                    {item.chapter_count === 1 ? "" : "s"}
                  </span>
                  {item.book_status === "PARTIAL" ? <Tag>Partial evidence</Tag> : null}
                </div>
                <div className="writer-decision-where">
                  <strong>{item.book_title}</strong>
                  <span>{item.chapter_title || item.chapter_name}</span>
                  <span className="writer-book-id">
                    {item.locator?.relative_path || item.chapter_name}
                    {item.locator?.line_start ? `:${item.locator.line_start}` : ""}
                  </span>
                </div>
                <p>{item.reason}</p>
                {item.locator?.excerpt ? (
                  <blockquote className="writer-excerpt">{item.locator.excerpt}</blockquote>
                ) : null}
                <div className="writer-decision-foot">
                  <button
                    className="button button-secondary button-small"
                    onClick={() => {
                      setSelectedBookId(item.project_id);
                      setSelectedChapterId(item.chapter_id);
                    }}
                  >
                    Inspect chapter
                  </button>
                  {item.workbench_link && item.workbench_book_ready ? (
                    <a
                      className="button button-primary button-small"
                      href={item.workbench_link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={14} /> Open in Workbench
                    </a>
                  ) : (
                    <span className="writer-decision-note">
                      {item.stale
                        ? "Refresh Writer evidence before deciding."
                        : `Workbench is on ${workspace.data?.workbench.book || "another book"}; switch it to ${item.book_title} first.`}
                    </span>
                  )}
                  {item.decision ? (
                    <span className="writer-decision-recorded">
                      {titleCase(item.decision.decision)} · {titleCase(item.decision.scope)}
                      {item.decision.reason ? ` · ${item.decision.reason}` : ""}
                    </span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
          {workspace.data.decision_queue.length > 10 ? (
            <button
              className="button button-secondary button-small"
              onClick={() => setShowAllQueue((current) => !current)}
            >
              {showAllQueue
                ? "Show the top 10"
                : `Show all ${workspace.data.decision_queue.length} groups`}
            </button>
          ) : null}
        </Section>
      ) : null}

      {workspace.data?.review_queue.length ? (
        <Section
          title="Cross-book review queue"
          description="Ordered for attention only. This is not an editorial decision, quality ranking or publication gate."
          actions={<Tag tone="accent">{workspace.data.review_queue.length} projects</Tag>}
        >
          <div className="writer-queue">
            {workspace.data.review_queue.slice(0, 8).map((item, index) => (
              <button
                className={`writer-queue-row ${selectedBook?.project_id === item.project_id ? "active" : ""}`}
                key={String(item.project_id)}
                onClick={() => {
                  setSelectedBookId(String(item.project_id));
                  setSelectedChapterId(null);
                }}
              >
                <span className="writer-queue-rank">{index + 1}</span>
                <span className="writer-queue-main">
                  <strong>{String(item.title || item.project_id)}</strong>
                  <small>{riskLabel(item.highest_risk)}</small>
                </span>
                <SimpleStatusBadge state={statusState(String(item.status))} label={String(item.status)} />
                <span className="writer-queue-time">{timeAgo(item.last_checked)}</span>
              </button>
            ))}
          </div>
        </Section>
      ) : null}

      <Section
        title="Books"
        description="The pipeline is shown as declared. Metadata, MRI and Strengthen are not inferred by Editing v1. A NOT_RUN book is not zero and not a pass."
      >
        {books.length ? (
          <div className="table-wrap">
            <table className="data-table writer-book-table">
              <thead>
                <tr>
                  <th>Book</th>
                  <th>Metadata</th>
                  <th>MRI</th>
                  <th>Strengthen</th>
                  <th>Editing</th>
                  <th>Readability</th>
                  <th>Highest risk</th>
                  <th>Last checked</th>
                </tr>
              </thead>
              <tbody>
                {books.map((book) => (
                  <tr
                    key={book.project_id}
                    className={selectedBook?.project_id === book.project_id ? "is-selected" : ""}
                    tabIndex={0}
                    onClick={() => {
                      setSelectedBookId(book.project_id);
                      setSelectedChapterId(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedBookId(book.project_id);
                        setSelectedChapterId(null);
                      }
                    }}
                  >
                    <td>
                      <strong>{book.title}</strong>
                      <div className="writer-book-id">{book.project_id} · {book.chapters_available} chapters</div>
                    </td>
                    <td className="writer-not-tracked">{pipelineLabel(book, "metadata")}</td>
                    <td className="writer-not-tracked">{pipelineLabel(book, "mri")}</td>
                    <td className="writer-not-tracked">{pipelineLabel(book, "strengthen")}</td>
                    <td>
                      <SimpleStatusBadge state={statusState(book.status)} label={book.status} />
                    </td>
                    <td>
                      {book.readability ? (
                        <div className="writer-mini-scores">
                          {book.readability.subdimensions.map((subdimension) => (
                            <span className={bandClass(subdimension.worst_band)} key={subdimension.id} title={subdimension.label}>
                              {subdimension.worst_score ?? "N/A"}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="muted">No report</span>
                      )}
                    </td>
                    <td>
                      <span className="writer-risk-text">{riskLabel(book.highest_risk)}</span>
                    </td>
                    <td>{timeAgo(book.last_checked)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No Writer editing evidence"
            description="Refresh Writer data or run Writer audits. A missing report is not a pass."
            icon={<FileSearch size={20} />}
          />
        )}
      </Section>

      {selectedBook ? (
        <Section
          title={selectedBook.title}
          description={`Writer report evidence · ${selectedBook.project_id}`}
          actions={
            <div className="button-row">
              <SimpleStatusBadge state={statusState(selectedBook.status)} label={selectedBook.status} />
              {selectedBook.report_id ? <Tag>{selectedBook.report_id}</Tag> : null}
            </div>
          }
        >
          <div className="writer-book-meta">
            <dl className="kv-list">
              <KeyValue label="Profile">{selectedBook.profile}</KeyValue>
              <KeyValue label="Scope">
                {selectedBook.scope?.whole_book ? "Whole book" : "Selected chapters"}
              </KeyValue>
              <KeyValue label="Source revision">
                {selectedBook.source_revision || "Not a Git revision"}{" "}
                {selectedBook.source_dirty == null ? "" : selectedBook.source_dirty ? "(dirty)" : "(clean)"}
              </KeyValue>
              <KeyValue label="Last checked">{formatDateTime(selectedBook.last_checked)}</KeyValue>
              <KeyValue label="Canonical fingerprint">
                <code>{selectedBook.canonical_fingerprint || "Not available"}</code>
              </KeyValue>
              <KeyValue label="Source">
                <PathText>{selectedBook.content_dir}</PathText>
              </KeyValue>
            </dl>
            {selectedBook.limitations.length ? (
              <div className="writer-limitations">
                <strong>Limitations</strong>
                <ul>
                  {selectedBook.limitations.map((limitation) => (
                    <li key={limitation}>{limitation}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {selectedBook.readability ? (
            <div className="writer-subdimensions">
              {selectedBook.readability.subdimensions.map((subdimension) => (
                <div className="writer-subdimension" key={subdimension.id}>
                  <div className="writer-subdimension-head">
                    <span>{subdimension.label}</span>
                    <span className={bandClass(subdimension.worst_band)}>
                      {subdimension.worst_score ?? "N/A"}
                      <small>{titleCase(subdimension.worst_band)}</small>
                    </span>
                  </div>
                  <div className="writer-subdimension-meta">
                    <span>{subdimension.chapters_flagged} chapter(s) flagged</span>
                    {subdimension.worst_chapter_id ? <code>{subdimension.worst_chapter_id}</code> : null}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          <div className="writer-term-note">
            <Gauge size={16} />
            <p>{selectedBook.readability?.note || "Subdimensions remain independent; no composite score is calculated."}</p>
          </div>

          <h3 className="writer-section-heading">Chapters</h3>
          {selectedBook.chapters.length ? (
            <div className="table-wrap">
              <table className="data-table writer-chapter-table">
                <thead>
                  <tr>
                    <th>Chapter</th>
                    {DIMENSION_ORDER.map((id) => (
                      <th key={id}>{titleCase(id.replace(/_/g, " "))}</th>
                    ))}
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedBook.chapters.map((chapter) => (
                    <tr
                      key={chapter.chapter_id}
                      className={selectedChapter?.chapter_id === chapter.chapter_id ? "is-selected" : ""}
                      tabIndex={0}
                      onClick={() => setSelectedChapterId(chapter.chapter_id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedChapterId(chapter.chapter_id);
                        }
                      }}
                    >
                      <td>
                        <strong>{chapter.title}</strong>
                        <div className="writer-book-id">
                          {chapter.relative_path}
                          {!chapter.current ? " · stale" : ""}
                        </div>
                      </td>
                      {DIMENSION_ORDER.map((id) => (
                        <td key={id}>{scoreCell(dimensionFor(chapter, id))}</td>
                      ))}
                      <td>
                        <SimpleStatusBadge state={statusState(chapter.status === "review_required" ? "NEEDS_REVIEW" : chapter.status === "watch" ? "PARTIAL" : "CURRENT")} label={titleCase(chapter.status)} />
                        <div className="writer-book-id">{chapter.finding_count} finding(s)</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No chapter results are attached to this report.</p>
          )}

          {selectedChapter ? (
            <div className="writer-chapter-detail">
              <div className="writer-chapter-detail-head">
                <div>
                  <span className="eyebrow">Chapter evidence</span>
                  <h3>{selectedChapter.title}</h3>
                  <div className="inline-meta">
                    <SimpleStatusBadge state={statusState(selectedChapter.status === "review_required" ? "NEEDS_REVIEW" : selectedChapter.status === "watch" ? "PARTIAL" : "CURRENT")} label={titleCase(selectedChapter.status)} />
                    <span>{selectedChapter.word_count} prose words</span>
                    <span>{selectedChapter.paragraph_count} paragraphs</span>
                    <span>{selectedChapter.sentence_count} sentences</span>
                    {!selectedChapter.current ? <Tag tone="danger">Stale</Tag> : null}
                  </div>
                </div>
                <PathText>{selectedChapter.source_path}</PathText>
              </div>

              <div className="writer-dimension-detail">
                {selectedChapter.dimensions.map((dimension) => (
                  <section className="writer-dimension" key={dimension.id}>
                    <div className="writer-dimension-head">
                      <strong>{dimension.label}</strong>
                      {scoreCell(dimension)}
                    </div>
                    <p className="muted small">{dimension.explanation}</p>
                    {dimension.limitations?.length ? (
                      <ul className="plain-list writer-dimension-limits">
                        {dimension.limitations.map((limitation) => (
                          <li key={limitation}>{limitation}</li>
                        ))}
                      </ul>
                    ) : null}
                    <details>
                      <summary>Raw metrics and scoring</summary>
                      <pre>{JSON.stringify({ metrics: dimension.raw_metrics, scoring: dimension.scoring }, null, 2)}</pre>
                    </details>
                  </section>
                ))}
              </div>

              <div className="writer-findings">
                <div className="writer-findings-head">
                  <h4>Findings</h4>
                  <span>{selectedChapter.findings.length ? `${selectedChapter.findings.length} recorded` : "No findings recorded"}</span>
                </div>
                {selectedChapter.findings.length ? (
                  selectedChapter.findings.map(findingRow)
                ) : (
                  <div className="writer-no-findings">
                    <CheckCircle2 size={16} />
                    <span>No finding was recorded for this chapter. This is not an editorial acceptance.</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </Section>
      ) : null}

      {workspace.data?.limitations.length ? (
        <Section title="Boundaries" description="What this view does not claim.">
          <ul className="plain-list writer-boundaries">
            {workspace.data.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
            <li>
              <Link className="text-link" to="/integrations">Inspect Writer integration diagnostics</Link>
            </li>
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
