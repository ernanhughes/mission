import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  ExternalLink,
  FolderOpen,
  Save,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  ActionButton,
  EmptyState,
  ErrorState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PathText,
  ProvenanceBadge,
  Section,
  SimpleStatusBadge,
} from "../components/ui";
import { formatDateTime, timeAgo } from "../lib/format";
import type { Book } from "../types/api";

const bookStatuses = [
  "planned",
  "drafting",
  "editorial_review",
  "verification",
  "production",
  "published",
];

function BookEditor({ book, onSaved }: { book: Book; onSaved: () => void }) {
  const toast = useToast();
  const [status, setStatus] = useState(book.status);
  const [milestone, setMilestone] = useState(book.current_milestone);
  const [nextAction, setNextAction] = useState(book.next_action);
  const [quality, setQuality] = useState(book.quality_review_state);
  const [publishedUrl, setPublishedUrl] = useState(book.published_url ?? "");
  const [localUrl, setLocalUrl] = useState(book.local_url ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setStatus(book.status);
    setMilestone(book.current_milestone);
    setNextAction(book.next_action);
    setQuality(book.quality_review_state);
    setPublishedUrl(book.published_url ?? "");
    setLocalUrl(book.local_url ?? "");
  }, [book]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/api/books/${book.id}`, {
        status,
        current_milestone: milestone,
        next_action: nextAction,
        quality_review_state: quality,
        published_url: publishedUrl.trim() || null,
        local_url: localUrl.trim() || null,
      });
      toast.push("success", "Book workspace saved");
      onSaved();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function openRepository() {
    try {
      await api.post(`/api/projects/${book.project_id}/open-repository`);
      toast.push("success", "Repository opened");
    } catch (caught) {
      toast.push("error", "Could not open repository", errorMessage(caught));
    }
  }

  return (
    <div className="book-workspace">
      <header className="book-workspace-head">
        <div>
          <span className="eyebrow">Book workspace</span>
          <h2>{book.title}</h2>
          <div className="inline-meta">
            <SimpleStatusBadge state={book.status} />
            <span>{book.project_name}</span>
            <span>Priority {book.priority ?? "—"}</span>
          </div>
        </div>
        <div className="button-row">
          <ActionButton
            action={book.repository_action ?? undefined}
            onClick={() => void openRepository()}
            variant="secondary"
            small
            icon={<FolderOpen size={14} />}
          >
            Repository
          </ActionButton>
          <Link className="button button-primary button-small" to={`/projects/${book.project_id}`}>
            <BookOpen size={14} /> Full workspace
          </Link>
        </div>
      </header>

      <div className="book-workspace-grid">
        <section className="panel">
          <span className="eyebrow">Direction</span>
          <h3>Book state</h3>
          <p className="muted small">
            Status and next actions are user-maintained until an authoritative Writer or BookBuilder
            integration is configured. Git timestamps never imply completion.
          </p>
          <form className="form-stack" onSubmit={(event) => void save(event)}>
            <InlineError message={error} />
            <div className="form-grid two">
              <label className="field">
                <span>Status</span>
                <select value={status} onChange={(event) => setStatus(event.target.value)}>
                  {bookStatuses.map((item) => (
                    <option value={item} key={item}>
                      {item.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Quality review state</span>
                <input value={quality} onChange={(event) => setQuality(event.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Current milestone</span>
              <textarea rows={2} value={milestone} onChange={(event) => setMilestone(event.target.value)} />
            </label>
            <label className="field">
              <span>Next action</span>
              <textarea rows={3} value={nextAction} onChange={(event) => setNextAction(event.target.value)} />
            </label>
            <div className="form-grid two">
              <label className="field">
                <span>Published URL</span>
                <input value={publishedUrl} onChange={(event) => setPublishedUrl(event.target.value)} />
              </label>
              <label className="field">
                <span>Local URL</span>
                <input value={localUrl} onChange={(event) => setLocalUrl(event.target.value)} />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-primary button-small" type="submit" disabled={saving}>
                <Save size={14} /> {saving ? "Saving…" : "Save book state"}
              </button>
              {publishedUrl ? (
                <a className="text-link" href={publishedUrl} target="_blank" rel="noreferrer">
                  Published version <ExternalLink size={13} />
                </a>
              ) : null}
              {localUrl ? (
                <a className="text-link" href={localUrl} target="_blank" rel="noreferrer">
                  Local version <ExternalLink size={13} />
                </a>
              ) : null}
            </div>
          </form>
        </section>

        <div className="stack">
          <section className="panel">
            <span className="eyebrow">Continuity</span>
            <h3>Last checkpoint</h3>
            {book.latest_checkpoint ? (
              <>
                <p>{book.latest_checkpoint.summary}</p>
                <div className="inline-meta">
                  <ProvenanceBadge value="recorded_checkpoint" />
                  <span>{formatDateTime(book.latest_checkpoint.created_at)}</span>
                </div>
                <div className="mini-block">
                  <span>Next intended action</span>
                  <p>{book.latest_checkpoint.next_action || "Not recorded"}</p>
                </div>
                {book.latest_checkpoint.blockers ? (
                  <p className="resume-blocker">Blocker: {book.latest_checkpoint.blockers}</p>
                ) : null}
              </>
            ) : (
              <p className="muted">
                No checkpoint yet. Save one in the project workspace to anchor the resume workflow.
              </p>
            )}
            <Link className="text-link" to={`/projects/${book.project_id}`}>
              Save or review checkpoints
            </Link>
          </section>

          <section className="panel">
            <span className="eyebrow">Paths</span>
            <h3>Manuscript and implementation</h3>
            <dl className="kv-list">
              <KeyValue label="Manuscript">
                {book.manuscript_paths.length ? (
                  book.manuscript_paths.map((path) => <PathText key={path}>{path}</PathText>)
                ) : (
                  <span className="muted">Not configured</span>
                )}
              </KeyValue>
              <KeyValue label="Implementation">
                {book.implementation_paths.length ? (
                  book.implementation_paths.map((path) => <PathText key={path}>{path}</PathText>)
                ) : (
                  <span className="muted">Not configured</span>
                )}
              </KeyValue>
              <KeyValue label="Last activity">
                {book.last_activity_at ? timeAgo(book.last_activity_at) : "Not recorded"}
              </KeyValue>
            </dl>
          </section>

          <section className="panel publishing-panel">
            <span className="eyebrow">Publishing</span>
            <h3>Build actions</h3>
            <p className="muted">
              No verified BookBuilder action is configured for this book, so no build button is
              shown. Publishing artifacts are never overwritten automatically.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function BooksPage() {
  const books = useApi<Book[]>("/api/books");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const toast = useToast();
  const [reordering, setReordering] = useState(false);

  useEffect(() => {
    if (books.data?.length && !books.data.some((book) => book.id === selectedId)) {
      setSelectedId(books.data[0].id);
    }
  }, [books.data, selectedId]);

  const ordered = [...(books.data ?? [])].sort(
    (a, b) => (a.priority ?? 999) - (b.priority ?? 999),
  );
  const selected = ordered.find((book) => book.id === selectedId) ?? ordered[0] ?? null;

  async function move(book: Book, direction: -1 | 1) {
    const index = ordered.findIndex((item) => item.id === book.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    const next = [...ordered];
    [next[index], next[target]] = [next[target], next[index]];
    setReordering(true);
    try {
      await api.post("/api/books/reorder", { ids: next.map((item) => item.id) });
      toast.push("success", "Book priority saved");
      books.reload();
    } catch (caught) {
      toast.push("error", "Could not reorder books", errorMessage(caught));
    } finally {
      setReordering(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Books and publishing"
        title="Books"
        description="The three priority books are first-class workspaces, not repository shortcuts."
      />

      {books.loading && !books.data ? <LoadingBlock label="Loading books" /> : null}
      {books.error ? <ErrorState message={books.error.message} onRetry={books.reload} /> : null}
      {books.data && books.data.length === 0 ? (
        <EmptyState
          title="No book workspaces"
          description="Create a project with kind Book to add a manuscript workspace."
          icon={<BookOpen size={20} />}
          action={
            <Link className="button button-primary button-small" to="/projects">
              Create a book project
            </Link>
          }
        />
      ) : null}

      {ordered.length ? (
        <div className="books-layout">
          <aside className="book-selector" aria-label="Books">
            {ordered.map((book, index) => (
              <div
                className={`book-selector-item ${selected?.id === book.id ? "active" : ""}`}
                key={book.id}
              >
                <button
                  className="book-selector-main"
                  onClick={() => setSelectedId(book.id)}
                  aria-pressed={selected?.id === book.id}
                  aria-label={`${book.project_name} — ${book.status.replace(/_/g, " ")}`}
                >
                  <span className="book-rank">0{index + 1}</span>
                  <span className="book-selector-copy">
                    <strong>{book.project_name}</strong>
                    <span>{book.status.replace(/_/g, " ")}</span>
                  </span>
                </button>
                <span className="book-selector-arrows">
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Move ${book.project_name} up`}
                    disabled={index === 0 || reordering}
                    onClick={() => void move(book, -1)}
                  >
                    <ArrowUp size={13} />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Move ${book.project_name} down`}
                    disabled={index === ordered.length - 1 || reordering}
                    onClick={() => void move(book, 1)}
                  >
                    <ArrowDown size={13} />
                  </button>
                </span>
              </div>
            ))}
          </aside>
          <div>
            {selected ? <BookEditor key={selected.id} book={selected} onSaved={books.reload} /> : null}
          </div>
        </div>
      ) : null}

      <Section title="How book status works" className="note-section">
        <p className="muted">
          Status is an explicit human judgement. Mission Control does not infer completion from Git
          activity or from a model summary. Where a verified adapter supplies evidence, it appears
          as an observation with a source, not as a silent status change.
        </p>
      </Section>
    </div>
  );
}
