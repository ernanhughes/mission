export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return "Not recorded";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return "Not recorded";
  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return "Never";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  if (seconds < 2592000) return `${Math.round(seconds / 86400)}d ago`;
  return formatDate(value);
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function provenanceLabel(value: string | null | undefined): string {
  switch (value) {
    case "user":
      return "User entered";
    case "user_priority":
      return "User priority";
    case "user_task":
      return "User task";
    case "recorded_checkpoint":
      return "Saved checkpoint";
    case "verified_observation":
      return "Verified observation";
    case "external_claim":
      return "External claim";
    case "derived_observation":
      return "Derived from evidence";
    case "ai_recommendation":
      return "AI recommendation";
    default:
      return titleCase(value ?? "unknown");
  }
}

export function activityLabel(value: string): string {
  const labels: Record<string, string> = {
    user_note: "Note",
    user_decision: "Decision",
    workspace_focus: "Focus",
    checkpoint: "Checkpoint",
    task_created: "Task",
    task_updated: "Task",
    recommendation_created: "Recommendation",
    recommendation_reviewed: "Review",
    application_launch: "Launch",
    application_stopped: "Stopped",
    application_launch_failed: "Launch failed",
    application_health: "Health",
    repository_opened: "Repository",
    git_observation: "Git",
    adapter_refresh: "Adapter",
    adapter_available: "Adapter",
    adapter_unavailable: "Adapter",
    adapter_observation: "Evidence",
    discovery_scan: "Discovery",
    briefing_generated: "Briefing",
    system: "System",
  };
  return labels[value] ?? titleCase(value);
}

export function shortCommit(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "unknown";
}

export function truncate(value: string, length = 220): string {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

export function classificationLabel(value: string): string {
  return titleCase(value.replace(/_/g, " "));
}

export function projectLabel(kind: string): string {
  if (kind === "book") return "Book";
  if (kind === "research") return "Research";
  if (kind === "application") return "Application";
  return titleCase(kind);
}
