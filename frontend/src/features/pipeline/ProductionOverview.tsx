import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useApi } from "../../api/useApi";
import type { PipelineOverview, PipelineStage } from "../../types/api";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Section,
  SimpleStatusBadge,
} from "../../components/ui";
import { MaintenanceStrip } from "./MaintenanceStrip";
import {
  PIPELINE_VISIBILITY_KEY,
  bookMatchesFilters,
  summaryStatus,
  visibleStages,
  type AttentionFilter,
} from "./pipelineStatus";

const FILTERS: Array<{ id: AttentionFilter; label: string }> = [
  { id: "stale", label: "Stale" },
  { id: "missing", label: "Missing" },
  { id: "failed", label: "Failed" },
  { id: "unknown", label: "Unknown" },
];

function stageLabel(stage: PipelineStage): string {
  return stage.name;
}

export function ProductionOverview({
  hidden,
  onToggleStage,
  onSelectBook,
}: {
  hidden: string[];
  onToggleStage: (stageId: string) => void;
  onSelectBook: (projectId: string, title: string) => void;
}) {
  const stagesQuery = useApi<{ registry_version: string; stages: PipelineStage[] }>(
    "/api/pipeline/stages",
  );
  const overviewQuery = useApi<PipelineOverview>("/api/pipeline/overview");
  const [filters, setFilters] = useState<AttentionFilter[]>([]);
  const [columnsOpen, setColumnsOpen] = useState(false);

  const stages = useMemo(
    () => (stagesQuery.data ? visibleStages(stagesQuery.data.stages, []) : []),
    [stagesQuery.data],
  );
  const shown = useMemo(() => visibleStages(stages, hidden), [stages, hidden]);
  const visibleIds = useMemo(() => shown.map((stage) => stage.stage_id), [shown]);

  function toggleFilter(filter: AttentionFilter) {
    setFilters((current) =>
      current.includes(filter) ? current.filter((item) => item !== filter) : [...current, filter],
    );
  }

  function reload() {
    stagesQuery.reload();
    overviewQuery.reload();
  }

  const books = useMemo(() => {
    const rows = overviewQuery.data?.books ?? [];
    return [...rows]
      .sort((a, b) => a.project_id.localeCompare(b.project_id))
      .filter((book) => bookMatchesFilters(book.summaries, visibleIds, filters));
  }, [overviewQuery.data, visibleIds, filters]);

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Books and publishing"
        title="Production & Quality"
        description="Read-only projection of stored Writer evidence. Every status traces to a real artifact plus an exact digest comparison — or to an explicit absence of evidence. Nothing here runs analysis or edits manuscripts."
        actions={
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={reload}
            disabled={overviewQuery.loading}
          >
            <RefreshCw size={14} /> {overviewQuery.loading ? "Reading…" : "Refresh overview"}
          </button>
        }
      />

      <MaintenanceStrip />

      <Section title="Catalogue status">
        {stagesQuery.loading || overviewQuery.loading ? <LoadingBlock label="Reading stored production evidence…" /> : null}
        {stagesQuery.error ? (
          <ErrorState message={stagesQuery.error.message} onRetry={stagesQuery.reload} />
        ) : null}
        {!stagesQuery.loading && !stagesQuery.error && overviewQuery.error ? (
          <ErrorState message={overviewQuery.error.message} onRetry={overviewQuery.reload} />
        ) : null}
        {!stagesQuery.loading && !overviewQuery.loading && !overviewQuery.error && books.length === 0 ? (
          <EmptyState
            title="No production evidence"
            description={
              filters.length
                ? "No books match the active attention filters."
                : "No registered books report pipeline evidence yet."
            }
          />
        ) : null}

        {!overviewQuery.loading && !overviewQuery.error && overviewQuery.data ? (
          <>
            <div className="pipe-filters" role="group" aria-label="Attention filters">
              <span className="pipe-filters-label">Show books with:</span>
              {FILTERS.map((filter) => (
                <label key={filter.id} className="pipe-check">
                  <input
                    type="checkbox"
                    checked={filters.includes(filter.id)}
                    onChange={() => toggleFilter(filter.id)}
                  />
                  {filter.label}
                </label>
              ))}
              <span className="pipe-filters-label">Columns:</span>
              <details
                className="pipe-cols"
                open={columnsOpen}
                onToggle={(event) => setColumnsOpen((event.target as HTMLDetailsElement).open)}
              >
                <summary aria-label="Configure visible stages">
                  {shown.length}/{stages.length} stages
                </summary>
                <div className="pipe-cols-list">
                  {stages.map((stage) => (
                    <label key={stage.stage_id} className="pipe-check">
                      <input
                        type="checkbox"
                        checked={!hidden.includes(stage.stage_id)}
                        onChange={() => onToggleStage(stage.stage_id)}
                      />
                      {stageLabel(stage)}
                    </label>
                  ))}
                </div>
              </details>
            </div>

            <div className="pipe-scroll" role="region" aria-label="Books production overview" tabIndex={0}>
              <table className="data-table pipe-table">
                <thead>
                  <tr>
                    <th scope="col">Book</th>
                    <th scope="col">Chapters</th>
                    {shown.map((stage) => (
                      <th key={stage.stage_id} scope="col" title={stage.description}>
                        {stageLabel(stage)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {books.map((book) => (
                    <tr key={book.project_id}>
                      <th scope="row" className="pipe-book-cell">
                        <button
                          type="button"
                          className="pipe-book-button"
                          onClick={() => onSelectBook(book.project_id, book.book_title)}
                          aria-label={`Open production matrix for ${book.book_title}`}
                        >
                          <strong>{book.book_title}</strong>
                          <span className="table-note">{book.project_id}</span>
                        </button>
                        {book.discovery_error ? (
                          <span className="table-note pipe-warn">{book.discovery_error}</span>
                        ) : null}
                      </th>
                      <td>{book.applicable_chapters}</td>
                      {shown.map((stage) => {
                        const summary = book.summaries[stage.stage_id];
                        const status = summaryStatus(summary, stage.availability);
                        return (
                          <td key={stage.stage_id}>
                            <span className={`pipe-badge pipe-tone-${status.tone}`} title={status.label}>
                              <span className="pipe-dot" aria-hidden="true" />
                              {status.short}
                            </span>
                            {stage.availability === "implemented" && summary ? (
                              <span className="table-note">{summary.coverage}</span>
                            ) : null}
                            {stage.availability !== "implemented" ? (
                              <span className="table-note">{stage.availability}</span>
                            ) : null}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pipe-legend" aria-label="Status legend">
              <span className="pipe-badge pipe-tone-current"><span className="pipe-dot" aria-hidden="true" />current</span>
              <span className="pipe-badge pipe-tone-stale"><span className="pipe-dot" aria-hidden="true" />stale</span>
              <span className="pipe-badge pipe-tone-missing"><span className="pipe-dot" aria-hidden="true" />missing</span>
              <span className="pipe-badge pipe-tone-unknown"><span className="pipe-dot" aria-hidden="true" />unknown</span>
              <span className="pipe-badge pipe-tone-failed"><span className="pipe-dot" aria-hidden="true" />failed</span>
              <span className="pipe-badge pipe-tone-planned"><span className="pipe-dot" aria-hidden="true" />planned</span>
              <span className="pipe-badge pipe-tone-na"><span className="pipe-dot" aria-hidden="true" />n/a</span>
            </div>
            <p className="muted small">
              A current editing audit does not mean the chapter was edited or improved — it means
              the audit evidence matches the live manuscript. Failed and stale are separate
              dimensions: a cell can report a real failure and also be stale.
            </p>
            <p className="muted small">
              Overview computed in {(overviewQuery.data.elapsed_ms / 1000).toFixed(1)}s · registry{" "}
              {overviewQuery.data.registry_version} · {overviewQuery.data.book_count} books ·
              column visibility is stored locally ({PIPELINE_VISIBILITY_KEY}) and never alters
              backend evidence or coverage.
            </p>
          </>
        ) : null}
      </Section>

      <Section title="How production status works" className="note-section">
        <p className="muted">
          Status is derived from stored Writer artifacts plus exact digest comparisons, using the
          registry at <code>/api/pipeline/stages</code>. Planned stages have no provider yet and
          are never shown as 0% complete. Missing validation runs do not imply failed validation;
          unknown metadata freshness does not imply a metadata problem.
        </p>
        <div className="inline-meta">
          <SimpleStatusBadge state="complete" label="current evidence" />
          <SimpleStatusBadge state="stale" label="stale evidence" />
          <SimpleStatusBadge state="pending" label="attention filters" />
        </div>
      </Section>
    </div>
  );
}
