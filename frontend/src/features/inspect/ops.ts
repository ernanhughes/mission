import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import type { InspectInventory, InspectJobList, InspectRun } from "../../types/api";

export function useInspectOpsInventory() {
  return useApi<InspectInventory>("/api/inspect/ops/inventory", { pollMs: 10000 });
}

export function useInspectOpsJobs(repositoryId?: string | null) {
  const path = repositoryId
    ? `/api/inspect/ops/runs?repository_id=${encodeURIComponent(repositoryId)}`
    : "/api/inspect/ops/runs?limit=25";
  return useApi<InspectJobList>(path, { pollMs: 3000 });
}

export async function startInspectOp(
  repositoryId: string,
  operation: string,
): Promise<{ run: InspectRun; duplicate: boolean }> {
  return api.post("/api/inspect/ops/runs", { repository_id: repositoryId, operation });
}

export async function cancelInspectRun(runId: string): Promise<{ run: InspectRun }> {
  return api.post(`/api/inspect/ops/runs/${runId}/cancel`, {});
}

/** Primary action label for the inventory table. */
export function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    inspect: "Inspect",
    full: "Full inspection",
    enrich: "Enrich",
    stamp: "Stamp",
    view: "View results",
  };
  return labels[action] ?? action;
}
