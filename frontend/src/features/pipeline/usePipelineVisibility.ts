import { useCallback, useState } from "react";
import { loadHiddenStages, saveHiddenStages } from "./pipelineStatus";

// Stage visibility is view configuration (localStorage, beside the Theme
// preference). Shared by the overview and matrix so hiding a column applies
// to both. Hiding never alters backend evidence or coverage.
export function usePipelineVisibility() {
  const [hidden, setHidden] = useState<string[]>(() => loadHiddenStages());
  const toggleStage = useCallback((stageId: string) => {
    setHidden((current) => {
      const next = current.includes(stageId)
        ? current.filter((item) => item !== stageId)
        : [...current, stageId];
      saveHiddenStages(next);
      return next;
    });
  }, []);
  return { hidden, toggleStage };
}
