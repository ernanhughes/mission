import {
  ArrowLeft,
  BookOpen,
  ChevronRight,
  MessageCircle,
  NotebookPen,
  RefreshCw,
  Send,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  InlineError,
  LoadingBlock,
  PageHeader,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import { BookMarkdown, bookSlug } from "../features/living-book/BookMarkdown";
import { ImprovementPanel } from "../features/living-book/ImprovementPanel";
import type {
  LivingBookChapterContent,
  LivingBookConversation,
  LivingBookNote,
  LivingBookQuality,
  LivingBookStatus,
} from "../types/living-book";
import { formatDateTime } from "../lib/format";

type CompanionTab = "ask" | "notes" | "quality" | "improve";

const QUALITY_LABELS: Record<string, string> = {
  prose: "Prose evaluation",
  writer: "Writer readability",
  technical: "Technical evidence",
  publication: "Publication readiness",
  artifact_load: "Artifact Load",
};

function qualityTone(status: string): string {
  if (["CURRENT", "READY", "AVAILABLE"].includes(status)) return "accent";
  if (["STALE", "PARTIAL", "MODEL_UNAVAILABLE"].includes(status)) return "warning";
  return "default";
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function ConnectPanel({
  status,
  onConnected,
}: {
  status: LivingBookStatus;
  onConnected: () => void;
}) {
  const candidates = status.candidates ?? [];
  const recommended = candidates.find((item) => item.recommended) ?? candidates[0];
  const [root, setRoot] = useState(recommended?.path ?? "");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, any> | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const toast = useToast();
  const candidate = candidates.find((item) => item.path === root);

  useEffect(() => {
    if (!candidate?.available) {
      setPreview(null);
      return;
    }
    let live = true;
    setPreview(null);
    setPreviewError(null);
    setPreviewBusy(true);
    api
      .post<Record<string, any>>(
        `/api/living-book/projects/${status.project_id}/connect/preview`,
        { root: candidate.path },
      )
      .then((value) => {
        if (live) setPreview(value.preview);
      })
      .catch((caught) => {
        if (live) setPreviewError(errorMessage(caught));
      })
      .finally(() => {
        if (live) setPreviewBusy(false);
      });
    return () => {
      live = false;
    };
  }, [candidate?.path, candidate?.available, status.project_id]);

  async function connect() {
    if (!candidate || !consent) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/living-book/projects/${status.project_id}/connect`, {
        root: candidate.path,
        approve: true,
      });
      toast.push("success", "Book connected to ALIVE", "Read-only source access is now recorded.");
      onConnected();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (status.state === "unavailable") {
    return (
      <section className="living-book-connect">
        <EmptyState
          title="ALIVE is not running"
          description={
            status.detail ||
            "Start the ALIVE backend, then reopen this reading room. The book itself has not changed."
          }
          icon={<BookOpen size={20} />}
        />
        <div className="form-actions">
          <button
            className="button button-primary"
            disabled={starting}
            onClick={() => {
              setStarting(true);
              setError(null);
              void api
                .post("/api/applications/alive/launch", { confirm: true })
                .then(() => {
                  toast.push("success", "ALIVE launch requested", "Rechecking the reading room…");
                  window.setTimeout(onConnected, 1500);
                })
                .catch((caught) => setError(errorMessage(caught)))
                .finally(() => setStarting(false));
            }}
          >
            <BookOpen size={15} /> {starting ? "Starting…" : "Start ALIVE"}
          </button>
          <Link className="button button-secondary" to="/applications">
            Open Applications
          </Link>
        </div>
        <InlineError message={error} />
      </section>
    );
  }

  return (
    <section className="living-book-connect">
      <span className="eyebrow">Connect this book</span>
      <h2>{status.book_title}</h2>
      <p className="muted">
        ALIVE reads an approved, read-only source. Nothing is copied into Mission Control, and no
        manuscript file is changed. Choose what ALIVE may read:
      </p>
      <div className="living-book-candidates">
        {candidates.map((item) => (
          <label
            key={item.path}
            className={`living-book-candidate${!item.available ? " is-disabled" : ""}${
              root === item.path ? " is-selected" : ""
            }`}
          >
            <input
              type="radio"
              name="living-book-source"
              value={item.path}
              checked={root === item.path}
              disabled={!item.available}
              onChange={() => setRoot(item.path)}
            />
            <span>
              <strong>
                {item.kind === "repository" ? "Whole book repository" : "Manuscript folder"}
                {item.recommended ? " · recommended" : ""}
              </strong>
              <code>{item.path}</code>
              <small>{item.detail}</small>
              {root === item.path && preview ? (
                <small>
                  ALIVE preview: {preview.summary?.files ?? 0} eligible files ·{" "}
                  {Math.round((preview.summary?.bytes ?? 0) / 1000).toLocaleString("en-US")} KB ·{" "}
                  {preview.summary?.excluded ?? 0} excluded
                </small>
              ) : null}
              {root === item.path && previewBusy ? <small>Reading the source scope…</small> : null}
              {root === item.path && previewError ? <small>{previewError}</small> : null}
              {!item.available && item.reason ? <small>{item.reason}</small> : null}
            </span>
          </label>
        ))}
      </div>
      {candidate ? (
        <label className="living-book-consent">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />
          <span>
            I approve read-only access for ALIVE to this source for up to 30 days. I understand the
            approval can be revoked in ALIVE and that routine reading questions use a bounded,
            revocable model session.
          </span>
        </label>
      ) : null}
      <InlineError message={error} />
      <div className="form-actions">
        <button
          className="button button-primary"
          onClick={() => void connect()}
          disabled={!candidate || !consent || busy || !preview || Boolean(previewError)}
        >
          <BookOpen size={15} /> {busy ? "Connecting…" : "Connect and approve"}
        </button>
      </div>
    </section>
  );
}

function QualityRail({
  quality,
  onAsk,
}: {
  quality: LivingBookQuality | null;
  onAsk: (prompt: string) => void;
}) {
  if (!quality) return <LoadingBlock label="Loading quality evidence" compact />;
  const prose = quality.measures.find((item) => item.id.includes("prose"));
  const dims = prose?.value?.dimensions ?? {};
  return (
    <div className="living-quality">
      <div className="living-quality-coverage">
        {Object.entries(quality.coverage).map(([key, value]) => (
          <div className="living-quality-chip" key={key}>
            <span>{QUALITY_LABELS[key] ?? key}</span>
            <Tag tone={qualityTone(value.status)}>{statusLabel(value.status)}</Tag>
            {key === "prose" && value.current !== undefined ? (
              <small>
                {value.current} / {value.total} current
              </small>
            ) : null}
            {key === "technical" && value.claims_total !== undefined ? (
              <small>{value.claims_total} claims</small>
            ) : null}
          </div>
        ))}
      </div>
      {prose?.value?.overall !== undefined && prose.value.overall !== null ? (
        <div className="living-quality-prose">
          <div className="living-quality-overall">
            <span>Current prose observation</span>
            <strong>{prose.value.overall} / 5</strong>
            <small>{prose.rubric} · {prose.model ?? "model not recorded"}</small>
          </div>
          <div className="living-quality-dimensions">
            {Object.entries(dims).map(([name, row]: [string, any]) => (
              <div key={name}>
                <span>{name}</span>
                <strong>{row.score ?? "—"}</strong>
                {row.evidence ? <small>{row.evidence}</small> : null}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="muted small">
          {prose?.detail ?? "No current prose observation for this chapter."}
        </p>
      )}
      {quality.summary.weakest_chapters?.length ? (
        <div className="living-quality-weak">
          <span className="eyebrow">Lowest current chapter observations</span>
          {quality.summary.weakest_chapters.map((item) => (
            <div key={item.chapter_id}>
              <span>{item.chapter_id}</span>
              <strong>{item.overall}</strong>
            </div>
          ))}
        </div>
      ) : null}
      <div className="living-quality-limits">
        {quality.limitations.map((item) => (
          <p key={item} className="muted small">
            {item}
          </p>
        ))}
      </div>
      <button
        className="button button-secondary button-small"
        onClick={() =>
          onAsk(
            "Explain the quality evidence for this chapter. What do the scores cover, what do they not establish, and what should I do next?",
          )
        }
      >
        <Sparkles size={14} /> Ask ALIVE about quality
      </button>
    </div>
  );
}

export function LivingBookPage() {
  const { projectId = "" } = useParams();
  const status = useApi<LivingBookStatus>(`/api/living-book/projects/${projectId}`);
  const toast = useToast();
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [chapter, setChapter] = useState<LivingBookChapterContent | null>(null);
  const [quality, setQuality] = useState<LivingBookQuality | null>(null);
  const [note, setNote] = useState<LivingBookNote | null>(null);
  const [chapterError, setChapterError] = useState<string | null>(null);
  const [chapterLoading, setChapterLoading] = useState(false);
  const [tab, setTab] = useState<CompanionTab>("ask");
  const [conversation, setConversation] = useState<LivingBookConversation | null>(null);
  const [askText, setAskText] = useState("");
  const [askScope, setAskScope] = useState<"chapter" | "book">("chapter");
  const [askBusy, setAskBusy] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [selection, setSelection] = useState("");
  const [pendingQuote, setPendingQuote] = useState<string | null>(null);
  const [pendingNote, setPendingNote] = useState("");
  const [noteBusy, setNoteBusy] = useState(false);
  const [showChapters, setShowChapters] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const readerRef = useRef<HTMLDivElement | null>(null);
  const saveTimer = useRef<number | null>(null);
  const book = status.data?.book ?? null;

  useEffect(() => {
    if (!book || chapterId) return;
    const first =
      book.reading?.chapter_id ?? book.chapters[0]?.chapter_id ?? null;
    if (first) setChapterId(first);
  }, [book, chapterId]);

  useEffect(() => {
    if (!book || !chapterId) return;
    let live = true;
    setChapterLoading(true);
    setChapterError(null);
    Promise.all([
      api.get<LivingBookChapterContent>(
        `/api/living-book/projects/${projectId}/chapters/${encodeURIComponent(chapterId)}`,
      ),
      api.get<LivingBookQuality>(
        `/api/living-book/projects/${projectId}/quality?chapter_id=${encodeURIComponent(chapterId)}`,
      ),
      api
        .get<LivingBookNote | null>(
          `/api/living-book/projects/${projectId}/notes/${encodeURIComponent(chapterId)}`,
        )
        .catch(() => null),
    ])
      .then(([chapterData, qualityData, noteData]) => {
        if (!live) return;
        setChapter(chapterData);
        setQuality(qualityData);
        setNote(noteData);
        const reading = book.reading;
        if (reading?.chapter_id === chapterId) {
          window.setTimeout(() => {
            const target = readerRef.current;
            if (!target) return;
            if (reading.anchor) {
              const anchor = document.getElementById(bookSlug(reading.anchor));
              if (anchor) {
                anchor.scrollIntoView({ block: "start" });
                return;
              }
            }
            target.scrollTop = Math.max(0, reading.progress * (target.scrollHeight - target.clientHeight));
          }, 120);
        } else if (readerRef.current) {
          readerRef.current.scrollTop = 0;
        }
      })
      .catch((caught) => {
        if (live) setChapterError(errorMessage(caught));
      })
      .finally(() => {
        if (live) setChapterLoading(false);
      });
    return () => {
      live = false;
    };
  }, [book, chapterId, projectId, refreshToken]);

  useEffect(() => {
    const first = book?.conversations?.[0];
    if (!first?.id) return;
    let live = true;
    api
      .get<LivingBookConversation>(
        `/api/living-book/projects/${projectId}/conversations/${encodeURIComponent(first.id)}`,
      )
      .then((value) => {
        if (live) setConversation(value);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [book?.id, book?.conversations, projectId]);

  const currentChapter = useMemo(
    () => book?.chapters.find((item) => item.chapter_id === chapterId) ?? null,
    [book, chapterId],
  );
  const chapterAnnotations = useMemo(
    () => (book?.annotations ?? []).filter((item) => item.chapter_id === chapterId),
    [book, chapterId],
  );
  const messages = conversation?.messages ?? [];

  function persistReading() {
    if (!chapterId || !readerRef.current) return;
    const element = readerRef.current;
    const max = Math.max(1, element.scrollHeight - element.clientHeight);
    const progress = Math.min(1, Math.max(0, element.scrollTop / max));
    void api
      .put(`/api/living-book/projects/${projectId}/reading`, {
        chapter_id: chapterId,
        progress,
        anchor: "",
      })
      .catch(() => undefined);
  }

  function onReaderScroll() {
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(persistReading, 1200);
  }

  function onSelection() {
    const value = window.getSelection()?.toString().trim() ?? "";
    if (value.length >= 8 && value.length <= 4000) setSelection(value);
  }

  async function ask(message = askText) {
    if (!message.trim() || !chapterId || askBusy) return;
    setAskBusy(true);
    setAskError(null);
    try {
      const result = await api.post<LivingBookConversation>(
        `/api/living-book/projects/${projectId}/ask`,
        {
          message,
          chapter_id: askScope === "book" ? null : chapterId,
          scope: askScope,
          selection: selection || null,
          conversation_id: conversation?.id ?? null,
          idempotency_key:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `living-${Date.now()}`,
        },
      );
      setConversation(result);
      setAskText("");
      setSelection("");
      if (result.status === "failed") {
        toast.push("error", "ALIVE could not complete the answer", result.answer || "Inspect the receipt.");
      }
    } catch (caught) {
      setAskError(errorMessage(caught));
    } finally {
      setAskBusy(false);
    }
  }

  async function generateNote(regenerate = false) {
    if (!chapterId || noteBusy) return;
    setNoteBusy(true);
    try {
      const result = await api.post<LivingBookNote>(
        `/api/living-book/projects/${projectId}/notes/${encodeURIComponent(chapterId)}`,
        { regenerate },
      );
      setNote(result);
      toast.push("success", "Living note ready", "The note is retained against this chapter revision.");
    } catch (caught) {
      toast.push("error", "Could not generate the living note", errorMessage(caught));
    } finally {
      setNoteBusy(false);
    }
  }

  async function saveAnnotation() {
    if (!pendingQuote || !chapterId) return;
    try {
      await api.post(`/api/living-book/projects/${projectId}/annotations`, {
        chapter_id: chapterId,
        quote: pendingQuote,
        note: pendingNote,
      });
      setPendingQuote(null);
      setPendingNote("");
      toast.push("success", "Kept with the book", "Your note is retained in ALIVE.");
      status.reload();
    } catch (caught) {
      toast.push("error", "Could not keep this note", errorMessage(caught));
    }
  }

  async function revokeSession() {
    const session = conversation?.session;
    if (!session?.id) return;
    try {
      await api.post(
        `/api/living-book/projects/${projectId}/sessions/${encodeURIComponent(session.id)}/revoke`,
      );
      setConversation((current) =>
        current?.session ? { ...current, session: { ...current.session, state: "revoked" } } : current,
      );
      toast.push("success", "Model session revoked", "Later model requests are refused.");
    } catch (caught) {
      toast.push("error", "Could not revoke the session", errorMessage(caught));
    }
  }

  if (status.loading && !status.data) {
    return (
      <div className="page">
        <LoadingBlock label="Opening the book" />
      </div>
    );
  }
  if (status.error || !status.data) {
    return (
      <div className="page">
        <InlineError message={status.error?.message ?? "Reading room unavailable"} />
      </div>
    );
  }

  const state = status.data.state;
  const readable = Boolean(book) && ["ready", "model_unavailable", "needs_source"].includes(state);
  if (!readable) {
    return (
      <div className="page living-book-page">
        <Link className="back-link" to={`/projects/${projectId}`}>
          <ArrowLeft size={14} /> Project workspace
        </Link>
        <PageHeader
          eyebrow="Living Book"
          title={status.data.book_title}
          description={status.data.detail || "Connect an approved source to begin reading."}
        />
        <ConnectPanel status={status.data} onConnected={status.reload} />
      </div>
    );
  }

  const modelReady = book?.model.ready ?? false;
  return (
    <div className="living-reader-page">
      <header className="living-reader-head">
        <Link className="back-link" to={`/projects/${projectId}`}>
          <ArrowLeft size={14} /> Project workspace
        </Link>
        <div className="living-reader-title">
          <span className="eyebrow">Living Book</span>
          <h1>{status.data.book_title}</h1>
          <span className="muted small">
            {book?.chapter_count ?? 0} chapters · source {statusLabel(book?.source.status ?? "unknown")}
            {book?.source.current ? " · current" : ""}
          </span>
          {book?.source.mode === "pinned" ? <Tag tone="warning">pinned edition</Tag> : null}
        </div>
        <div className="living-reader-head-actions">
          <SimpleStatusBadge
            state={state === "ready" ? "running" : state === "model_unavailable" ? "pending" : "pending"}
            label={state === "ready" ? "ALIVE ready" : state === "model_unavailable" ? "Reading only" : statusLabel(state)}
          />
          <button className="button button-secondary button-small" onClick={() => setShowChapters((value) => !value)}>
            <BookOpen size={14} /> Chapters
          </button>
        </div>
      </header>

      {state === "needs_source" ? (
        <div className="living-reader-notice">
          <InlineError message={book?.error ?? "The book source changed or is not usable."} />
          <button
            className="button button-secondary button-small"
            onClick={() => {
              void api
                .post(`/api/living-book/projects/${projectId}/refresh`)
                .then(() => status.reload())
                .catch((caught) => toast.push("error", "Refresh failed", errorMessage(caught)));
            }}
          >
            <RefreshCw size={14} /> Refresh source
          </button>
        </div>
      ) : null}

      <div className="living-reader-grid">
        <aside className={`living-reader-index${showChapters ? " is-open" : ""}`}>
          <div className="living-reader-index-head">
            <span className="eyebrow">Contents</span>
            <span className="muted small">{(book?.chapters ?? []).length} chapters</span>
          </div>
          <ol>
            {(book?.chapters ?? []).map((item) => (
              <li key={item.chapter_id}>
                <button
                  className={item.chapter_id === chapterId ? "is-current" : ""}
                  onClick={() => {
                    persistReading();
                    setChapterId(item.chapter_id);
                    setShowChapters(false);
                  }}
                >
                  <span>{item.order}</span>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.word_count.toLocaleString("en-US")} words</small>
                  </span>
                  {item.status !== "current" ? <Tag tone="warning">changed</Tag> : null}
                </button>
              </li>
            ))}
          </ol>
        </aside>

        <main className="living-reader-main">
          <div className="living-reader-scroll" ref={readerRef} onScroll={onReaderScroll} onMouseUp={onSelection}>
            {chapterLoading ? <LoadingBlock label="Opening chapter" /> : null}
            <InlineError message={chapterError} />
            {chapter ? (
              <>
                <div className="living-chapter-head">
                  <span className="eyebrow">Chapter {chapter.order}</span>
                  <h2>{chapter.title}</h2>
                  <div className="inline-meta">
                    <span>{chapter.word_count.toLocaleString("en-US")} words</span>
                    <span>{chapter.sections.length} sections</span>
                    {currentChapter?.sha256 ? <code>{currentChapter.sha256.slice(0, 12)}</code> : null}
                  </div>
                </div>
                <BookMarkdown content={chapter.markdown} projectId={projectId} />
                <div className="living-chapter-carry">
                  <span className="eyebrow">Carry forward</span>
                  {note ? (
                    <p>
                      A living note for this chapter is ready in the companion. Ask one of its
                      questions or keep a passage before you move on.
                    </p>
                  ) : (
                    <p>
                      Ask ALIVE to read this chapter with you, or keep a passage that matters. The
                      book will remember where you stopped.
                    </p>
                  )}
                  <div className="living-chapter-carry-actions">
                    <button
                      className="button button-secondary button-small"
                      onClick={() => {
                        setTab("notes");
                        void generateNote(false);
                      }}
                      disabled={noteBusy}
                    >
                      <Sparkles size={14} /> {note ? "Open living note" : "Read with ALIVE"}
                    </button>
                    <button
                      className="button button-primary button-small"
                      onClick={() => {
                        setTab("ask");
                        const first = book?.chapters.find((item) => item.chapter_id === chapterId);
                        setAskText(
                          `What is this chapter doing, and what should I carry into the next chapter?`,
                        );
                        void first;
                      }}
                    >
                      <MessageCircle size={14} /> Ask about this chapter
                    </button>
                    <button
                      className="button button-secondary button-small"
                      onClick={() => setTab("improve")}
                      disabled={!currentChapter || currentChapter.status !== "current"}
                    >
                      <Wrench size={14} /> Improve this chapter
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </main>

        <aside className="living-companion">
          {selection ? (
            <div className="living-selection">
              <span className="eyebrow">Selection</span>
              <blockquote>{selection.slice(0, 260)}</blockquote>
              <div className="living-selection-actions">
                <button
                  className="button button-secondary button-small"
                  onClick={() => {
                    setAskText(`What does this passage mean in the chapter's argument?\n\n"${selection}"`);
                    setTab("ask");
                  }}
                >
                  <MessageCircle size={13} /> Ask
                </button>
                <button
                  className="button button-secondary button-small"
                  onClick={() => {
                    setPendingQuote(selection);
                    setTab("notes");
                  }}
                >
                  <NotebookPen size={13} /> Keep
                </button>
              </div>
            </div>
          ) : null}

          <div className="living-companion-tabs">
            <button className={tab === "ask" ? "is-current" : ""} onClick={() => setTab("ask")}>
              <MessageCircle size={14} /> Ask
            </button>
            <button className={tab === "notes" ? "is-current" : ""} onClick={() => setTab("notes")}>
              <NotebookPen size={14} /> Notes
            </button>
            <button className={tab === "quality" ? "is-current" : ""} onClick={() => setTab("quality")}>
              <Sparkles size={14} /> Quality
            </button>
            <button className={tab === "improve" ? "is-current" : ""} onClick={() => setTab("improve")}>
              <Wrench size={14} /> Improve
            </button>
          </div>

          {tab === "ask" ? (
            <div className="living-companion-body">
              <div className="living-companion-session">
                <span className="muted small">
                  {book?.model.name} · {modelReady ? "ready" : "model unavailable"}
                </span>
                {conversation?.session ? (
                  <span className="muted small">
                    {conversation.session.usage?.calls ?? 0} / {conversation.session.max_calls ?? "—"} calls
                  </span>
                ) : null}
                {conversation?.session && conversation.session.state !== "revoked" ? (
                  <button className="text-link" onClick={() => void revokeSession()}>
                    Revoke
                  </button>
                ) : null}
              </div>
              <div className="living-conversation">
                {!messages.length ? (
                  <div className="living-conversation-empty">
                    <p>
                      ALIVE has the open chapter, its evidence files where available, and the
                      current quality measures. It does not have authority to change the book.
                    </p>
                    <div className="living-suggestions">
                      {[
                        "What is this chapter trying to establish?",
                        "Where is the argument weakest, and why?",
                        "How should I read the quality scores for this chapter?",
                      ].map((prompt) => (
                        <button
                          key={prompt}
                          className="living-suggestion"
                          onClick={() => void ask(prompt)}
                          disabled={!modelReady || askBusy}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`living-message ${message.role === "user" ? "is-user" : "is-alive"}`}
                  >
                    <span className="eyebrow">{message.role === "user" ? "You" : "ALIVE"}</span>
                    <p>{message.content}</p>
                    {message.citations?.length ? (
                      <details>
                        <summary>{message.citations.length} citation(s)</summary>
                        {message.citations.map((citation, index) => (
                          <blockquote key={`${message.id}-cite-${index}`}>
                            {citation.quote || citation.document_id || citation.source_ref}
                            {citation.line_start ? (
                              <small>
                                {" "}
                                · line {citation.line_start}
                                {citation.line_end && citation.line_end !== citation.line_start
                                  ? `–${citation.line_end}`
                                  : ""}
                              </small>
                            ) : null}
                          </blockquote>
                        ))}
                      </details>
                    ) : null}
                    {message.status === "failed" ? (
                      <p className="warn-text small">No completed reply was retained.</p>
                    ) : null}
                  </article>
                ))}
                {askBusy ? <p className="muted small">ALIVE is reading and answering…</p> : null}
                <InlineError message={askError} />
              </div>
              <form
                className="living-composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  void ask();
                }}
              >
                <div className="living-composer-scope">
                  <button
                    type="button"
                    className={askScope === "chapter" ? "is-current" : ""}
                    onClick={() => setAskScope("chapter")}
                  >
                    This chapter
                  </button>
                  <button
                    type="button"
                    className={askScope === "book" ? "is-current" : ""}
                    onClick={() => setAskScope("book")}
                  >
                    Whole book
                  </button>
                </div>
                <textarea
                  value={askText}
                  onChange={(event) => setAskText(event.target.value)}
                  placeholder={
                    askScope === "chapter"
                      ? "Ask about this chapter, a passage, or the quality evidence…"
                      : "Ask the book across chapters…"
                  }
                  rows={3}
                />
                <div className="living-composer-actions">
                  <span className="muted small">
                    {book?.model.name} · bounded session
                  </span>
                  <button
                    className="button button-primary button-small"
                    type="submit"
                    disabled={!askText.trim() || askBusy || !modelReady}
                  >
                    <Send size={14} /> Send
                  </button>
                </div>
              </form>
            </div>
          ) : null}

          {tab === "notes" ? (
            <div className="living-companion-body living-notes">
              <div className="living-note-card">
                <div className="living-note-head">
                  <span className="eyebrow">Living note</span>
                  {note ? (
                    <Tag tone={note.status === "current" ? "accent" : "warning"}>
                      {note.status === "current" ? "retained · current" : "retained · stale"}
                    </Tag>
                  ) : null}
                </div>
                {note ? (
                  <>
                    <BookMarkdown content={note.markdown} projectId={projectId} />
                    <span className="muted small">
                      {note.model ?? "model not recorded"} · {formatDateTime(note.generated_at)}
                    </span>
                    <button
                      className="button button-secondary button-small"
                      onClick={() => void generateNote(true)}
                      disabled={noteBusy}
                    >
                      <RefreshCw size={13} /> {noteBusy ? "Regenerating…" : "Regenerate"}
                    </button>
                  </>
                ) : (
                  <p className="muted small">
                    No living note for this chapter yet. Generate one to get an orientation, key
                    moves, questions and a quality read grounded in this revision.
                  </p>
                )}
                {!note ? (
                  <button
                    className="button button-primary button-small"
                    onClick={() => void generateNote(false)}
                    disabled={noteBusy || !modelReady}
                  >
                    <Sparkles size={14} /> {noteBusy ? "Reading…" : "Generate living note"}
                  </button>
                ) : null}
              </div>

              {pendingQuote ? (
                <div className="living-annotation-form">
                  <span className="eyebrow">Keep this passage</span>
                  <blockquote>{pendingQuote.slice(0, 300)}</blockquote>
                  <textarea
                    rows={3}
                    value={pendingNote}
                    onChange={(event) => setPendingNote(event.target.value)}
                    placeholder="Why does this matter? (optional)"
                  />
                  <div className="form-actions">
                    <button className="button button-primary button-small" onClick={() => void saveAnnotation()}>
                      Keep with the book
                    </button>
                    <button
                      className="button button-secondary button-small"
                      onClick={() => {
                        setPendingQuote(null);
                        setPendingNote("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="living-annotations">
                <span className="eyebrow">Kept in this chapter ({chapterAnnotations.length})</span>
                {chapterAnnotations.length ? (
                  chapterAnnotations.map((item) => (
                    <article key={item.id}>
                      <blockquote>{item.quote}</blockquote>
                      {item.stale ? <Tag tone="warning">chapter changed</Tag> : null}
                      {item.note ? <p>{item.note}</p> : null}
                      <button
                        className="text-link"
                        onClick={() => {
                          void api
                            .delete(
                              `/api/living-book/projects/${projectId}/annotations/${encodeURIComponent(item.id)}`,
                            )
                            .then(() => status.reload())
                            .catch((caught) => toast.push("error", "Could not remove note", errorMessage(caught)));
                        }}
                      >
                        Remove
                      </button>
                    </article>
                  ))
                ) : (
                  <p className="muted small">
                    Select a passage in the chapter and press “Keep” to leave a note here.
                  </p>
                )}
              </div>
            </div>
          ) : null}

          {tab === "quality" ? (
            <div className="living-companion-body">
              <QualityRail
                quality={quality}
                onAsk={(prompt) => {
                  setAskText(prompt);
                  setAskScope("chapter");
                  setTab("ask");
                }}
              />
            </div>
          ) : null}

          {tab === "improve" && chapterId ? (
            <div className="living-companion-body living-improve-body">
              <ImprovementPanel
                projectId={projectId}
                chapterId={chapterId}
                onSourceRefreshed={() => {
                  status.reload();
                  setRefreshToken((value) => value + 1);
                }}
              />
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
