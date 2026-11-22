import { apiPath } from "../../api/client";
import { useApi } from "../../api/useApi";
import type {
  InspectCapabilityList,
  InspectCompositionList,
  InspectCoverage,
  InspectManifest,
  InspectOpportunityList,
  InspectProjectList,
  InspectUsageList,
} from "../../types/api";

export function useInspectManifest() {
  return useApi<InspectManifest>("/api/inspect/manifest", { pollMs: 60000 });
}

export function useInspectProjects() {
  return useApi<InspectProjectList>("/api/inspect/projects", { pollMs: 60000 });
}

export type CapabilityQuery = {
  project?: string;
  subsystem?: string;
  access?: string;
  verification?: string;
  risk?: string;
  q?: string;
};

export function capabilitiesPath(query: CapabilityQuery = {}) {
  return apiPath("/api/inspect/capabilities", {
    project: query.project || undefined,
    subsystem: query.subsystem && query.subsystem !== "ALL" ? query.subsystem : undefined,
    access: query.access && query.access !== "ALL" ? query.access : undefined,
    verification:
      query.verification && query.verification !== "ALL" ? query.verification : undefined,
    risk: query.risk && query.risk !== "ALL" ? query.risk : undefined,
    q: query.q?.trim() ? query.q.trim() : undefined,
  });
}

export function useInspectCapabilities(query: CapabilityQuery = {}) {
  return useApi<InspectCapabilityList>(capabilitiesPath(query), { pollMs: 60000 });
}

export function useInspectUsage(capabilityId: string | null) {
  return useApi<InspectUsageList>(
    capabilityId ? `/api/inspect/usage/${capabilityId}` : null,
  );
}

export type OpportunityQuery = {
  project?: string;
  category?: string;
  status?: string;
};

export function opportunitiesPath(query: OpportunityQuery = {}) {
  return apiPath("/api/inspect/opportunities", {
    project: query.project || undefined,
    category:
      query.category && query.category !== "ALL" ? query.category : undefined,
    status: query.status && query.status !== "ALL" ? query.status : undefined,
  });
}

export function useInspectOpportunities(query: OpportunityQuery = {}) {
  return useApi<InspectOpportunityList>(opportunitiesPath(query), { pollMs: 60000 });
}

export function useInspectCoverage(projectId: string | null) {
  return useApi<InspectCoverage>(
    projectId ? `/api/inspect/coverage/${projectId}` : null,
  );
}

export function useInspectCompositions(project?: string) {
  return useApi<InspectCompositionList>(
    apiPath("/api/inspect/compositions", { project: project || undefined }),
    { pollMs: 60000 },
  );
}

export function shortSha(value: unknown, length = 12): string {
  const text = String(value ?? "");
  return text ? text.slice(0, length) : "—";
}

/** Capabilities whose invocation writes outside a sandbox or spawns effects. */
export function isSideEffectful(capability: Record<string, any>): boolean {
  const risk = String(capability.risk ?? "").toLowerCase();
  if (risk && risk !== "read-only" && risk !== "none" && risk !== "unknown") return true;
  const haystack = JSON.stringify([
    capability.risk,
    capability.functionality?.invocation,
    capability.functionality?.outputs,
  ]).toLowerCase();
  return /write|delete|mutat|side.effect|execut|spawn|network|publish|send/.test(haystack);
}

/** Capabilities with no test evidence and no demonstrated run. */
export function isUntested(capability: Record<string, any>): boolean {
  const status = String(capability.operational_status ?? "").toLowerCase();
  if (status.includes("demonstrat")) return false;
  if (status.includes("test")) return false;
  const evidence = Array.isArray(capability.evidence) ? capability.evidence : [];
  return !evidence.some(
    (item: Record<string, any>) =>
      String(item?.kind ?? "").toLowerCase() === "test",
  );
}

export function needsAttention(capability: Record<string, any>): string[] {
  const notes: string[] = [];
  if (!capability.verified_reason && capability.unverified_reason) {
    notes.push(`Unverified: ${String(capability.unverified_reason).slice(0, 200)}`);
  } else if (isUntested(capability)) {
    notes.push("No test evidence and no demonstrated run — treat as untested.");
  }
  if (isSideEffectful(capability)) {
    notes.push(
      `Side-effectful (risk: ${String(capability.risk ?? "unknown")}) — read the invocation before running anything.`,
    );
  }
  return notes;
}

/** Distinct facet values across a capability list, for filter dropdowns. */
export function facetValues(
  capabilities: Array<Record<string, any>>,
  pick: (capability: Record<string, any>) => string | string[] | undefined,
): string[] {
  const seen = new Set<string>();
  for (const capability of capabilities) {
    const value = pick(capability);
    if (Array.isArray(value)) {
      for (const item of value) if (item) seen.add(String(item));
    } else if (value) {
      seen.add(String(value));
    }
  }
  return [...seen].sort((a, b) => a.localeCompare(b));
}

export function uniqueStrings(values: Array<unknown>): string[] {
  return [...new Set(values.map((v) => String(v ?? "")).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
}
