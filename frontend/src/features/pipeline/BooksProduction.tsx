import { useMemo, useState } from "react";
import { useApi } from "../../api/useApi";
import type { PipelineStage } from "../../types/api";
import { EmptyState } from "../../components/ui";
import { ProductionOverview } from "./ProductionOverview";
import { ChapterMatrix } from "./ChapterMatrix";
import { StageEvidencePanel } from "./StageEvidencePanel";
import { usePipelineVisibility } from "./usePipelineVisibility";

export function BooksProduction() {
  const stagesQuery = useApi<{ registry_version: string; stages: PipelineStage[] }>(
    "/api/pipeline/stages",
  );
  const { hidden, toggleStage } = usePipelineVisibility();
  const [productionBook, setProductionBook] = useState<{ id: string; title: string } | null>(null);
  const [inspect, setInspect] = useState<{ stageId: string; chapterId: string } | null>(null);

  const stages = useMemo(() => stagesQuery.data?.stages ?? [], [stagesQuery.data]);
  const inspectStage = useMemo(
    () => (inspect ? stages.find((stage) => stage.stage_id === inspect.stageId) ?? null : null),
    [inspect, stages],
  );

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
        <ChapterMatrix
          projectId={productionBook.id}
          bookTitle={productionBook.title}
          stages={stages}
          hiddenStages={hidden}
          onInspect={(stageId, chapterId) => setInspect({ stageId, chapterId })}
        />
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
