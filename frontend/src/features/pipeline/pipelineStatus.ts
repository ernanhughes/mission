import type { PipelineSummary } from "../../types/api";

// Production pipeline presentation states (M2). These describe how to render
// backend result/freshness pairs; they never replace the underlying values.
// Result and freshness stay separate: a failed, stale cell communicates both.

export type PipeTone =
  | "current"
  | "stale"
  | "missing"
  | "unknown"
  | "failed"
  | "planned"
  | "na";

export type PipeStatus = { tone: PipeTone; label: string; short: string };

export function summaryStatus(
  summary: PipelineSummary | undefined,
  availability: string,
): PipeStatus {
  if (!summary || availability === "unavailable") return { tone: "na", label: "n/a", short: "n/a" };
  if (availability === "planned") return { tone: "planned", label: "planned", short: "planned" };
  const { applicable, current, stale, missing, unknown, failed } = summary;
  if (applicable === 0) return { tone: "na", label: "no chapters", short: "—" };
  if (failed > 0 && stale > 0)
    return { tone: "failed", label: `${summary.coverage} · failed · stale`, short: "failed·stale" };
  if (failed > 0)
    return { tone: "failed", label: `${summary.coverage} · failed`, short: "failed" };
  if (stale > 0)
    return { tone: "stale", label: `${summary.coverage} · stale`, short: "stale" };
  if (missing > 0)
    return { tone: "missing", label: `${summary.coverage} · missing`, short: "missing" };
  if (unknown > 0)
    return { tone: "unknown", label: `${summary.coverage} · unknown freshness`, short: "unknown" };
  if (current === applicable)
    return { tone: "current", label: `${summary.coverage} · current`, short: "current" };
  return { tone: "unknown", label: summary.coverage, short: summary.coverage };
}

export function cellStatus(cell: {
  result: string;
  freshness: string;
  has_evidence: boolean;
  applicable: boolean;
}): PipeStatus {
  if (!cell.applicable) return { tone: "na", label: "not applicable", short: "n/a" };
  if (cell.result === "unavailable") return { tone: "na", label: "unavailable", short: "n/a" };
  if (cell.result === "failed" && cell.freshness === "stale")
    return { tone: "failed", label: "failed · stale evidence", short: "failed·stale" };
  if (cell.result === "failed") return { tone: "failed", label: "failed", short: "failed" };
  if (cell.result === "pending")
    return { tone: "unknown", label: "pending", short: cell.freshness === "stale" ? "pend·stale" : "pending" };
  if (cell.freshness === "stale") return { tone: "stale", label: "stale", short: "stale" };
  if (!cell.has_evidence) return { tone: "missing", label: "missing — no qualifying evidence", short: "missing" };
  if (cell.freshness === "current") return { tone: "current", label: "current", short: "current" };
  return { tone: "unknown", label: "unknown freshness", short: "unknown" };
}

export type AttentionFilter = "stale" | "missing" | "failed" | "unknown";

export function bookMatchesFilters(
  summaries: Record<string, PipelineSummary>,
  visibleStageIds: string[],
  filters: AttentionFilter[],
): boolean {
  if (!filters.length) return true;
  const active = visibleStageIds.filter((id) => {
    const summary = summaries[id];
    return summary && summary.availability !== "planned" && summary.availability !== "unavailable";
  });
  return filters.some((filter) =>
    active.some((id) => (summaries[id]?.[filter] ?? 0) > 0),
  );
}

export function visibleStages<T extends { stage_id: string }>(
  stages: T[],
  hidden: string[],
): T[] {
  const hiddenSet = new Set(hidden);
  return stages.filter((stage) => !hiddenSet.has(stage.stage_id));
}

// Stage visibility is view configuration stored beside the Theme localStorage
// preference. Hiding a column never alters backend evidence or coverage.
export const PIPELINE_VISIBILITY_KEY = "mc.pipeline.hiddenStages";

export function loadHiddenStages(): string[] {
  try {
    const raw = window.localStorage.getItem(PIPELINE_VISIBILITY_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function saveHiddenStages(hidden: string[]): void {
  try {
    window.localStorage.setItem(PIPELINE_VISIBILITY_KEY, JSON.stringify(hidden));
  } catch {
    // View configuration is best-effort; the matrix works without it.
  }
}
