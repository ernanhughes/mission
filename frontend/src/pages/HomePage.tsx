import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  ChevronRight,
  CircleDot,
  Clock3,
  Crosshair,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { ApplicationCard } from "../features/applications/ApplicationCard";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  ProvenanceBadge,
  Section,
  SkeletonCard,
  SimpleStatusBadge,
  Stat,
} from "../components/ui";
import {
  activityLabel,
  formatDate,
  formatDateTime,
  projectLabel,
  timeAgo,
  truncate,
} from "../lib/format";
import type { Book, Briefing, Dashboard, Settings } from "../types/api";

export function HomePage() {
  const dashboard = useApi<Dashboard>("/api/dashboard", { pollMs: 45000 });
  const settings = useApi<Settings>("/api/settings");
  const toast = useToast();
  const [briefingBusy, setBriefingBusy] = useState(false);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [reordering, setReordering] = useState(false);

  async function reorderBooks(book: Book, direction: -1 | 1) {
    if (!dashboard.data) return;
    const ordered = [...dashboard.data.books].sort(
      (a, b) => (a.priority ?? 999) - (b.priority ?? 999),
    );
    const index = ordered.findIndex((item) => item.id === book.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setReordering(true);
    try {
      await api.post("/api/books/reorder", { ids: ordered.map((item) => item.id) });
      toast.push("success", "Priority order saved");
      dashboard.reload();
    } catch (caught) {
      toast.push("error", "Could not reorder books", errorMessage(caught));
    } finally {
      setReordering(false);
    }
  }

  async function generateBriefing(useAi: boolean) {
    setBriefingBusy(true);
    setBriefingError(null);
    try {
      const result = await api.post<Briefing>("/api/briefing/generate", { use_ai: useAi });
      toast.push(
        result.status === "complete" ? "success" : "info",
        result.mode === "ai" ? "AI-assisted briefing generated" : "Briefing generated",
        result.error ?? "Grounded in saved checkpoints, tasks and evidence.",
      );
      dashboard.reload();
    } catch (caught) {
      const message = errorMessage(caught);
      setBriefingError(message);
      toast.push("error", "Could not generate briefing", message);
    } finally {
      setBriefingBusy(false);
    }
  }

  if (dashboard.loading && !dashboard.data) {
    return (
      <div className="page">
        <LoadingBlock label="Assembling today's workspace" />
        <div className="card-grid three">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  if (dashboard.error) {
    return (
      <div className="page">
        <PageHeader eyebrow="Mission Control" title="Today" />
        <ErrorState message={dashboard.error.message} onRetry={dashboard.reload} />
      </div>
    );
  }

  if (!dashboard.data) return null;
  const data = dashboard.data;
  const books = [...data.books].sort((a, b) => (a.priority ?? 999) - (b.priority ?? 999));
  const pinnedApps = data.applications.filter((app) => app.pinned && app.enabled && !app.archived);
  const focus = data.focus;
  const checkpoint = data.checkpoint;
  const briefing = data.briefing;
  const aiReady = Boolean(settings.data?.ai_configured);

  return (
    <div className="page">
      <PageHeader
        eyebrow={`Mission Control · ${formatDate(data.date)}`}
        title="Today"
        description="One workspace for the books, projects and systems that matter now."
        actions={
          <>
            <Link className="button button-secondary" to="/activity">
              <Clock3 size={15} /> Activity
            </Link>
            <Link className="button button-primary" to={focus ? `/projects/${focus.id}` : "/projects"}>
              <Crosshair size={15} /> {focus ? "Open current focus" : "Choose a focus"}
            </Link>
          </>
        }
      />

      <div className="stat-strip">
        <Stat label="Priority books" value={data.stats.priority_books} />
        <Stat
          label="Running"
          value={`${data.stats.running_applications}/${data.stats.applications}`}
          detail="applications"
        />
        <Stat label="Open tasks" value={data.stats.open_tasks} />
        <Stat label="Pending reviews" value={data.stats.pending_reviews} />
        <Stat
          label="Adapters"
          value={`${data.stats.adapters_available}/${data.adapters.length}`}
          detail="available"
        />
      </div>

      <div className="today-grid">
        <section className="focus-panel">
          <span className="eyebrow">
            <Target size={13} /> Current focus
          </span>
          {focus ? (
            <>
              <div className="focus-title-row">
                <div>
                  <h2>{focus.name}</h2>
                  <span className="focus-kind">{projectLabel(focus.kind)}</span>
                </div>
                <SimpleStatusBadge state={focus.status} />
              </div>
              <p className="focus-milestone">{focus.current_milestone || "No milestone recorded."}</p>
              <div className="focus-next">
                <span>Next recorded action</span>
                <p>{focus.next_action || "No next action saved. Open the workspace to add one."}</p>
              </div>
              <div className="focus-actions">
                <Link className="button button-primary button-small" to={`/projects/${focus.id}`}>
                  Open workspace <ChevronRight size={14} />
                </Link>
                <span className="muted small">Last activity {timeAgo(focus.last_activity_at)}</span>
              </div>
            </>
          ) : (
            <EmptyState
              title="No current focus"
              description="Choose a priority book or project to anchor the day. The choice is persisted locally."
              icon={<Crosshair size={19} />}
              action={
                <Link className="button button-primary button-small" to="/projects">
                  Choose a project
                </Link>
              }
            />
          )}
        </section>

        <section className="resume-panel">
          <span className="eyebrow">
            <Clock3 size={13} /> Resume last work
          </span>
          {checkpoint ? (
            <>
              <div className="resume-project">{checkpoint.project_name ?? "Project"}</div>
              <h3>{truncate(checkpoint.summary, 180)}</h3>
              <div className="checkpoint-meta">
                <span>{formatDateTime(checkpoint.created_at)}</span>
                <ProvenanceBadge value="recorded_checkpoint" />
              </div>
              <div className="resume-next">
                <span>Next intended action</span>
                <p>{checkpoint.next_action || "No next action recorded."}</p>
              </div>
              {checkpoint.blockers ? (
                <p className="resume-blocker">Blocker: {checkpoint.blockers}</p>
              ) : null}
              <div className="focus-actions">
                <Link
                  className="button button-primary button-small"
                  to={`/projects/${checkpoint.project_id}`}
                >
                  Continue work <ChevronRight size={14} />
                </Link>
              </div>
            </>
          ) : (
            <EmptyState
              title="No checkpoint yet"
              description="Save a short checkpoint in a project workspace so tomorrow starts where today stopped."
              icon={<Clock3 size={19} />}
              action={
                focus ? (
                  <Link className="button button-secondary button-small" to={`/projects/${focus.id}`}>
                    Create checkpoint
                  </Link>
                ) : null
              }
            />
          )}
        </section>

        <section className="reviews-panel">
          <span className="eyebrow">
            <CircleDot size={13} /> Awaiting review
          </span>
          {data.recommendations.length ? (
            <ul className="review-list">
              {data.recommendations.slice(0, 3).map((rec) => (
                <li key={rec.id}>
                  <div>
                    <strong>{truncate(rec.title, 120)}</strong>
                    <span>
                      {rec.project_name ?? "Workspace"} · {rec.source_application ?? rec.provenance}
                    </span>
                  </div>
                  <ProvenanceBadge value={rec.provenance} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">No pending recommendations. Evidence adapters have not proposed work.</p>
          )}
          <div className="focus-actions">
            <Link className="text-link" to="/activity">
              View decisions and activity <ChevronRight size={13} />
            </Link>
          </div>
        </section>
      </div>

      <Section
        title="Priority books"
        description="Human priority controls the order. Recent file activity never promotes a book automatically."
        actions={
          <span className="section-hint">
            <ArrowUp size={13} /> <ArrowDown size={13} /> reorder
          </span>
        }
      >
        <div className="book-grid">
          {books.map((book, index) => (
            <article className="book-card" key={book.id}>
              <div className="book-card-top">
                <span className="book-rank">0{index + 1}</span>
                <SimpleStatusBadge state={book.status} />
              </div>
              <h3>{book.title}</h3>
              <span className="book-project">{book.project_name}</span>
              <div className="book-block">
                <span>Milestone</span>
                <p>{book.current_milestone || "No milestone recorded."}</p>
              </div>
              <div className="book-block">
                <span>Next action</span>
                <p>{book.next_action || "No next action recorded."}</p>
              </div>
              <div className="book-card-meta">
                <span>Checkpoint {book.latest_checkpoint ? timeAgo(book.latest_checkpoint.created_at) : "not saved"}</span>
              </div>
              <div className="book-card-actions">
                <Link className="button button-primary button-small" to={`/projects/${book.project_id}`}>
                  <BookOpen size={14} /> Open
                </Link>
                <div className="reorder-controls" aria-label={`Reorder ${book.title}`}>
                  <button
                    className="icon-button"
                    aria-label={`Move ${book.project_name} up`}
                    disabled={index === 0 || reordering}
                    onClick={() => void reorderBooks(book, -1)}
                  >
                    <ArrowUp size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`Move ${book.project_name} down`}
                    disabled={index === books.length - 1 || reordering}
                    onClick={() => void reorderBooks(book, 1)}
                  >
                    <ArrowDown size={15} />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Section>

      <Section
        title="Core applications"
        description="Launch, monitor and open the systems that already do the work."
        actions={
          <Link className="text-link" to="/applications">
            All applications <ChevronRight size={13} />
          </Link>
        }
      >
        {pinnedApps.length ? (
          <div className="card-grid two">
            {pinnedApps.map((app) => (
              <ApplicationCard key={app.id} app={app} onChanged={dashboard.reload} compact />
            ))}
          </div>
        ) : (
          <EmptyState title="No pinned applications" description="Pin an application to keep it on Today." />
        )}
      </Section>

      <div className="split-grid">
        <Section
          title="Daily briefing"
          description="Grounded in saved checkpoints, tasks and adapter evidence. AI is optional."
          actions={
            <div className="button-row">
              <button
                className="button button-secondary button-small"
                onClick={() => void generateBriefing(false)}
                disabled={briefingBusy}
              >
                <RefreshCw size={14} className={briefingBusy ? "spin" : ""} /> Generate
              </button>
              {aiReady ? (
                <button
                  className="button button-ghost button-small"
                  onClick={() => void generateBriefing(true)}
                  disabled={briefingBusy}
                  title="Send the grounded briefing evidence to the configured model provider"
                >
                  <Sparkles size={14} /> AI-assisted
                </button>
              ) : null}
            </div>
          }
        >
          <InlineError message={briefingError} />
          {briefing ? (
            <div className="briefing">
              <div className="briefing-meta">
                <span>{briefing.mode === "ai" ? "AI-assisted" : "Deterministic"}</span>
                <span>{timeAgo(briefing.created_at)}</span>
                {briefing.status !== "complete" ? <span className="warn-text">{briefing.status}</span> : null}
              </div>
              {briefing.error ? <p className="muted small">{briefing.error}</p> : null}
              <ol className="briefing-list">
                {briefing.items.slice(0, 6).map((item) => (
                  <li key={`${item.rank}-${item.title}`}>
                    <div className="briefing-item-head">
                      <strong>{item.title}</strong>
                      <ProvenanceBadge value={item.provenance} />
                    </div>
                    <p>{truncate(item.rationale, 260)}</p>
                    <span className="briefing-source">{item.source ?? item.provenance}</span>
                  </li>
                ))}
              </ol>
              <details className="raw-briefing">
                <summary>Show briefing text</summary>
                <pre>{briefing.content}</pre>
              </details>
            </div>
          ) : (
            <EmptyState
              title="No briefing yet"
              description="Generate a deterministic briefing from what is already recorded. It will never invent a task."
              action={
                <button
                  className="button button-primary button-small"
                  onClick={() => void generateBriefing(false)}
                  disabled={briefingBusy}
                >
                  Generate briefing
                </button>
              }
            />
          )}
        </Section>

        <Section
          title="Recent activity"
          description="Observed facts, user decisions and failed operations remain distinct."
          actions={
            <Link className="text-link" to="/activity">
              Full log <ChevronRight size={13} />
            </Link>
          }
        >
          {data.activity.length ? (
            <ul className="activity-feed compact">
              {data.activity.slice(0, 7).map((event) => (
                <li key={event.id}>
                  <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
                  <div>
                    <div className="activity-head">
                      <strong>{event.title}</strong>
                      <span className="activity-type">{activityLabel(event.type)}</span>
                    </div>
                    <span className="activity-meta">
                      {event.project_name ?? event.application_name ?? event.source} · {timeAgo(event.occurred_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No activity yet" description="Launch a tool, save a checkpoint or refresh an adapter." />
          )}
        </Section>
      </div>

      <Section title="Outcomes" description="Work is connected to destinations, not only repositories.">
        <div className="outcome-row">
          {data.outcomes.map((outcome) => (
            <div className="outcome" key={outcome.id}>
              <span className="outcome-name">{outcome.name}</span>
              <span className="outcome-status">{outcome.status}</span>
              <p>{outcome.description}</p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
