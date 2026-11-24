import { useMemo, useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import type { PipelineMaintenanceStatus, PipelineStage } from "../../types/api";
import { EmptyState } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { ProductionOverview } from "./ProductionOverview";
import { ChapterMatrix } from "./ChapterMatrix";
import { StageEvidencePanel } from "./StageEvidencePanel";
import { usePipelineVisibility } from "./usePipelineVisibility";

export function BooksProduction() {
  const stagesQuery = useApi<{ registry_version: string; stages: PipelineStage[] }>(
    "/api/pipeline/stages",
  );
  const maintenanceQuery = useApi<PipelineMaintenanceStatus>("/api/pipeline/maintenance");
  const toast = useToast();
  const { hidden, toggleStage } = usePipelineVisibility();
  const [productionBook, setProductionBook] = useState<{ id: string; title: string } | null>(null);
  const [inspect, setInspect] = useState<{ stageId: string; chapterId: string } | null>(null);
  const [pausing, setPausing] = useState(false);

  const stages = useMemo(() => stagesQuery.data?.stages ?? [], [stagesQuery.data]);
  const inspectStage = useMemo(
    () => (inspect ? stages.find((stage) => stage.stage_id === inspect.stageId) ?? null : null),
    [inspect, stages],
  );
  const bookPaused = useMemo(
    () => maintenanceQuery.data?.paused_books.includes(productionBook?.id ?? "") ?? false,
    [maintenanceQuery.data, productionBook],
  );

  async function setBookPaused(paused: boolean) {
    if (!productionBook) return;
    setPausing(true);
    try {
      await api.post("/api/pipeline/maintenance/pause", {
        project_id: productionBook.id,
        paused,
      });
      toast.push(
        "success",
        paused
          ? `Automatic maintenance paused for ${productionBook.title}`
          : `Automatic maintenance resumed for ${productionBook.title}`,
      );
      maintenanceQuery.reload();
    } catch (caught) {
      toast.push("error", "Could not change pause setting", errorMessage(caught));
    } finally {
      setPausing(false);
    }
  }

  return (
    <div className="stack">
      <ProductionOverview
        hidden={hidden}
        onToggleStage={toggleStage}
        onSelectBook={(projectId, title) => {
          setProductionBook({ id: projectId, title });
          setInspect(null);
        }}
      />

      {productionBook ? (
        <>
          <section className="panel pipe-book-maintenance" aria-label="Book maintenance controls">
            <span className="eyebrow">Automatic maintenance · {productionBook.title}</span>
            <div className="button-row">
              <button
                className="button button-secondary button-small"
                type="button"
                disabled={pausing}
                onClick={() => void setBookPaused(!bookPaused)}
              >
                {bookPaused ? "Resume automatic maintenance" : "Pause automatic maintenance"}
              </button>
              {bookPaused ? (
                <span className="muted small">
                  Automatic runs are paused for this book. Existing evidence is unaffected.
                </span>
              ) : (
                <span className="muted small">
                  Eligible deterministic stages refresh on their own; Refresh and Retry below
                  are recovery controls, not the normal path.
                </span>
              )}
            </div>
          </section>
          <ChapterMatrix
            projectId={productionBook.id}
            bookTitle={productionBook.title}
            stages={stages}
            hiddenStages={hidden}
            onInspect={(stageId, chapterId) => setInspect({ stageId, chapterId })}
          />
        </>
      ) : (
        <EmptyState
          title="No book selected"
          description="Select a book in the overview above to open its chapter-level production matrix."
        />
      )}

      {inspect && inspectStage && productionBook ? (
        <StageEvidencePanel
          projectId={productionBook.id}
          bookTitle={productionBook.title}
          chapterId={inspect.chapterId}
          stage={inspectStage}
          onClose={() => setInspect(null)}
        />
      ) : null}
    </div>
  );
}
