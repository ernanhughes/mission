import { BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { useApi } from "../../api/useApi";
import { SimpleStatusBadge } from "../../components/ui";
import { timeAgo } from "../../lib/format";
import type { LivingBookStatus } from "../../types/living-book";

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

export function LivingBookCard({ projectId }: { projectId: string }) {
  const status = useApi<LivingBookStatus>(`/api/living-book/projects/${projectId}`);
  if (status.loading && !status.data) return null;
  if (status.error) {
    return (
      <section className="panel living-book-card">
        <span className="eyebrow">Living Book</span>
        <h3>Reading room unavailable</h3>
        <p className="muted small">{status.error.message}</p>
      </section>
    );
  }
  if (!status.data) return null;
  const data = status.data;
  const book = data.book;
  const reading = book?.reading;
  const currentChapter = book?.chapters.find((item) => item.chapter_id === reading?.chapter_id);
  return (
    <section className="panel living-book-card">
      <div className="living-book-card-head">
        <div>
          <span className="eyebrow">Living Book</span>
          <h3>{data.book_title}</h3>
        </div>
        <SimpleStatusBadge
          state={
            data.state === "ready"
              ? "running"
              : data.state === "unavailable"
                ? "unavailable"
                : "pending"
          }
          label={statusLabel(data.state)}
        />
      </div>
      <p className="muted small">
        {book
          ? `${book.chapter_count} chapters · ${data.quality.coverage.prose.current ?? 0} of ${
              data.quality.coverage.prose.total ?? book.chapter_count
            } current prose evaluations`
          : data.detail || "Connect this book to ALIVE to open the reading room."}
      </p>
      {reading ? (
        <div className="living-book-continue">
          <span className="eyebrow">Continue</span>
          <strong>{currentChapter?.title ?? reading.chapter_id}</strong>
          <span className="muted small">
            {Math.round(reading.progress * 100)}% through this chapter
            {reading.updated_at ? ` · ${timeAgo(reading.updated_at)}` : ""}
          </span>
        </div>
      ) : null}
      <div className="living-book-card-actions">
        <Link className="button button-primary" to={`/projects/${projectId}/read`}>
          <BookOpen size={15} /> Open reading room
        </Link>
        {book ? (
          <Link className="text-link" to={`/projects/${projectId}`}>
            Project evidence
          </Link>
        ) : null}
      </div>
    </section>
  );
}
