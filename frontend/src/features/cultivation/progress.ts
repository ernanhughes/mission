import type { CultivationProgress } from "../../types/api";

/** Progress-bar state: empty, in progress, achieved, over target, or unknown. */
export function barState(progress: CultivationProgress): string {
  if (progress.current == null) return "unknown";
  if (progress.current <= 0) return "empty";
  if (progress.achieved) return progress.current > progress.target ? "over" : "achieved";
  return "active";
}

export function barPercent(progress: CultivationProgress): number {
  if (progress.current == null || progress.current <= 0) return 0;
  if (progress.percent == null) return 0;
  return Math.min(100, Math.max(0, progress.percent));
}

export function currentLabel(detail: CultivationProgress): string {
  if (detail.estimate_label) return detail.estimate_label;
  if (detail.current == null) return detail.unknown_reason ?? "Unknown";
  const formatted = Number.isInteger(detail.current) ? `${detail.current}` : detail.current.toFixed(1);
  return `${formatted} / ${detail.target} ${detail.unit}`;
}
