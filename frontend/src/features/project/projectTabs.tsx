import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export type ProjectTabId =
  | "overview"
  | "book"
  | "quality"
  | "technical"
  | "calibration"
  | "publishing"
  | "work"
  | "activity"
  | "tests";

export const PROJECT_TABS: Array<{ id: ProjectTabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "book", label: "Book" },
  { id: "quality", label: "Quality" },
  { id: "technical", label: "Technical" },
  { id: "calibration", label: "Calibration" },
  { id: "publishing", label: "Publishing" },
  { id: "work", label: "Work" },
  { id: "activity", label: "Activity" },
  { id: "tests", label: "Tests" },
];

const VALID = new Set<string>(PROJECT_TABS.map((t) => t.id));

export function normalizeProjectTab(raw: string | null): ProjectTabId {
  if (raw && VALID.has(raw)) return raw as ProjectTabId;
  return "overview";
}

export function useProjectTab(projectId: string) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = normalizeProjectTab(searchParams.get("tab"));

  const setTab = useCallback(
    (next: ProjectTabId) => {
      setSearchParams(
        (prev) => {
          const updated = new URLSearchParams(prev);
          if (next === "overview") {
            updated.delete("tab");
          } else {
            updated.set("tab", next);
          }
          return updated;
        },
      );
      void projectId;
    },
    [setSearchParams],
  );

  const setParam = useCallback(
    (key: string, value: string | null) => {
      setSearchParams(
        (prev) => {
          const updated = new URLSearchParams(prev);
          if (value === null || value === "") updated.delete(key);
          else updated.set(key, value);
          return updated;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  return { tab, setTab, searchParams, setParam };
}

export function tabHref(projectId: string, tab: ProjectTabId): string {
  if (tab === "overview") return `/projects/${projectId}`;
  return `/projects/${projectId}?tab=${tab}`;
}
