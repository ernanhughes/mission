import { useMemo } from "react";
import { useApi } from "../../api/useApi";
import type { PipelineBookMatrix, PipelineStage } from "../../types/api";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PathText,
  Section,
} from "../../components/ui";
import { cellStatus, type PipeStatus } from "./pipelineStatus";

export function ChapterMatrix({
  projectId,
  bookTitle,
  stages,
  hiddenStages,
  onInspect,
}: {
  projectId: string;
  bookTitle: string;
  stages: PipelineStage[];
  hiddenStages: string[];
  onInspect: (stageId: string, chapterId: string) => void;
}) {
  const matrixQuery = useApi<PipelineBookMatrix>(
    projectId ? `/api/pipeline/books/${projectId}` : null,
  );
  const hiddenSet = useMemo(() => new Set(hiddenStages), [hiddenStages]);
  const shown = useMemo(
    () => stages.filter((stage) => !hiddenSet.has(stage.stage_id)),
    [stages, hiddenSet],
  );

  const data = matrixQuery.data;
  const rows = useMemo(() => {
    if (!data) return [];
    return data.chapters.map((chapter) => ({
      ...chapter,
      cells: shown.map((stage) => ({
        stage,
        cell: (data.matrix[stage.stage_id] ?? []).find(
          (item) => item.chapter_id === chapter.chapter_id,
        ),
      })),
    }));
  }, [data, shown]);

  return (
    <Section
      title={`${bookTitle} — Production Pipeline`}
      description="One row per chapter, one column per configured stage. Select a cell to inspect the evidence behind its status."
      actions={
        matrixQuery.loading ? <span className="muted small">Reading…</span> : null
      }
    >
      {matrixQuery.loading && !data ? <LoadingBlock label="Reading chapter evidence…" /> : null}
      {matrixQuery.error ? (
        <ErrorState message={matrixQuery.error.message} onRetry={matrixQuery.reload} />
      ) : null}
      {!matrixQuery.loading && !matrixQuery.error && data && data.chapters.length === 0 ? (
        <EmptyState
          title="No applicable chapters"
          description={
            typeof data.discovery?.error === "string" && data.discovery.error
              ? data.discovery.error
              : "The chapter directory reports no files matching the registry pattern."
          }
        />
      ) : null}
      {data && data.chapters.length > 0 ? (
        <>
          {typeof data.discovery?.error === "string" && data.discovery.error ? (
            <InlineError message={String(data.discovery.error)} />
          ) : null}
          <div className="pipe-scroll" role="region" aria-label="Chapter production matrix" tabIndex={0}>
            <table className="data-table pipe-table pipe-matrix">
              <thead>
                <tr>
                  <th scope="col" className="pipe-sticky">Chapter</th>
                  {shown.map((stage) => {
                    const summary = data.summaries[stage.stage_id];
                    return (
                      <th key={stage.stage_id} scope="col" title={stage.description}>
                        {stage.name}
                        {summary && stage.availability === "implemented" ? (
                          <span className="table-note">{summary.coverage}</span>
                        ) : (
                          <span className="table-note">{stage.availability}</span>
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.chapter_id}>
                    <th scope="row" className="pipe-sticky pipe-chapter-cell">
                      <strong>{row.chapter_id}</strong>
                      <span className="table-note">{row.filename}</span>
                    </th>
                    {row.cells.map(({ stage, cell }) => {
                      if (!cell) {
                        return (
                          <td key={stage.stage_id}>
                            <span className="pipe-badge pipe-tone-na">
                              <span className="pipe-dot" aria-hidden="true" />n/a
                            </span>
                          </td>
                        );
                      }
                      const status: PipeStatus = stage.availability !== "implemented"
                        ? {
                            tone: stage.availability === "planned" ? "planned" : "na",
                            label: stage.availability,
                            short: stage.availability,
                          }
                        : cellStatus(cell);
                      return (
                        <td key={stage.stage_id}>
                          <button
                            type="button"
                            className={`pipe-cell pipe-tone-${status.tone}`}
                            onClick={() => onInspect(stage.stage_id, row.chapter_id)}
                            aria-label={`${stage.name} — ${row.chapter_id}: ${status.label}`}
                            title={`${status.label}. Select to inspect evidence.`}
                          >
                            <span className="pipe-dot" aria-hidden="true" />
                            {status.short}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Manuscript source: <PathText>{data.chapter_dir}</PathText> · pattern{" "}
            {data.chapter_pattern} · profile {data.profile}
          </p>
        </>
      ) : null}
    </Section>
  );
}
