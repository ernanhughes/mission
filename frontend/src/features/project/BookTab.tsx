import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { LivingBookCard } from "../living-book/LivingBookCard";
import { EmptyState, Section, SimpleStatusBadge, Tag } from "../../components/ui";
import { useApi } from "../../api/useApi";
import { timeAgo } from "../../lib/format";
import type { ProjectDetail, QualityDiscovery } from "../../types/api";

export function BookTab({
  projectId,
  data,
  discovery,
}: {
  projectId: string;
  data: ProjectDetail;
  discovery: QualityDiscovery[] | null;
}) {
  const living = useApi<{ book_title?: string; detail?: string; state?: string; book?: { chapters?: Array<{ chapter_id: string; title?: string | null }> } | null }>(
    `/api/living-book/projects/${projectId}`,
  );

  if (!data.book && data.kind !== "book") {
    return (
      <Section title="Book" description="Manuscript workspace for book projects.">
        <EmptyState
          title="Not a book project"
          description="This project has no manuscript attached. Book tools are hidden rather than shown empty."
        />
      </Section>
    );
  }

  const chapters = discovery ?? [];
  const book = data.book;

  return (
    <div>
      <LivingBookCard projectId={projectId} />
      <Section
        title="Reading"
        description="Continue where the reading stopped. The Reading Room remains the canonical reading experience."
        actions={
          <Link className="button button-primary button-small" to={`/projects/${projectId}/read`}>
            <BookOpen size={14} /> Open reading room
          </Link>
        }
      >
        {living.loading ? <p className="muted small">Loading reading progress…</p> : null}
        {living.data?.book ? (
          <p className="muted small">
            {living.data.book.chapters?.length ?? chapters.length} chapters inventoried · state{" "}
            {living.data.state ?? "unknown"}
          </p>
        ) : (
          <p className="muted small">{living.data?.detail ?? "Reading progress loads with the Living Book."}</p>
        )}
        {book ? (
          <div className="inline-meta">
            <SimpleStatusBadge state={book.status} />
            <span className="muted small">{book.quality_review_state.replace(/_/g, " ")}</span>
            {book.next_action ? <span className="muted small">Next: {book.next_action}</span> : null}
          </div>
        ) : (
          <p className="muted small">
            No book record linked yet. Chapter inventory below reflects discovered manuscript sources, not a
            reconciled book count.
          </p>
        )}
      </Section>

      <Section
        title="Manuscript and chapter inventory"
        description="Discovered chapters. Counts are reported as observed, never reconciled across pillars."
        actions={chapters.length ? <Tag>{chapters.length} chapters</Tag> : undefined}
      >
        {chapters.length === 0 ? (
          <EmptyState
            title="No chapters discovered"
            description="Run quality discovery or link the manuscript root. An empty inventory is unknown, not zero evidence."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Chapter</th>
                  <th>Title</th>
                  <th>Evaluation</th>
                </tr>
              </thead>
              <tbody>
                {chapters.map((row) => (
                  <tr key={row.chapter_id}>
                    <td>{row.chapter_id}</td>
                    <td className="muted small">{row.title ?? "untitled"}</td>
                    <td>
                      {row.has_current ? (
                        <Tag tone="accent">current</Tag>
                      ) : (
                        <Tag>{row.eligibility}</Tag>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Book outcomes" description="Outcome relationships for this manuscript.">
        {data.outcomes.length ? (
          <ul className="plain-list">
            {data.outcomes.map((outcome) => (
              <li key={outcome.id}>
                <strong>{outcome.name}</strong> · <span className="muted small">{outcome.status}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">No outcome relationship configured.</p>
        )}
      </Section>

      {data.notes ? (
        <Section title="Manuscript notes" description="Author notes and manuscript context.">
          <p className="small">{data.notes}</p>
          <p className="muted small">Last activity {timeAgo(data.last_activity_at)}</p>
        </Section>
      ) : null}
    </div>
  );
}
