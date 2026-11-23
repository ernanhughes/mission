import { useApi } from "../../api/useApi";
import { ErrorState, LoadingBlock, Section, Tag } from "../../components/ui";

type Runtime = {
  available: boolean;
  base_url: string;
  checked_at: string;
  connection: { reachable: boolean; status: string; version: string; listener: string; error?: string | null };
  availability: {
    available: boolean;
    error?: string | null;
    schema_version?: string;
    discovered_at?: string | null;
    probing?: boolean;
    models: Array<{ id: string; provider: string; status: string; tested_at?: string | null; age_seconds?: number | null; failure_type?: string | null; blocked?: boolean | null }>;
    warnings: string[];
    freshness_note: string;
  };
  usage: {
    available: boolean;
    error?: string | null;
    schema_version?: string;
    scope?: string;
    outcomes?: Record<string, number>;
    billed?: Record<string, unknown>;
    estimated?: Record<string, unknown>;
    billed_unknown_calls?: number | null;
    models_count?: number;
    warnings: string[];
    unknown_note: string;
  };
  preflight: { available: boolean; error?: string | null; document?: Record<string, unknown> };
  notes: string[];
};

export function WorkerRuntimePanel() {
  const runtime = useApi<Runtime>("/api/worker/runtime", { pollMs: 60000 });

  if (runtime.loading && !runtime.data) {
    return (
      <Section title="AI runtime" description="Worker model readiness and usage. Read-only; cached availability never triggers a probe.">
        <LoadingBlock label="Loading Worker runtime" compact />
      </Section>
    );
  }
  if (runtime.error) {
    return (
      <Section title="AI runtime" description="Worker model readiness and usage. Read-only; cached availability never triggers a probe.">
        <ErrorState message={runtime.error.message} onRetry={runtime.reload} />
      </Section>
    );
  }
  const data = runtime.data;
  if (!data) return null;

  return (
    <Section
      title="AI runtime"
      description="Worker model readiness and usage. Read-only; cached availability never triggers a probe."
      actions={
        data.available ? <Tag tone="accent">Worker reachable</Tag> : <Tag tone="danger">Worker unavailable</Tag>
      }
    >
      {!data.available ? (
        <p className="warn-text small">
          Worker is unavailable at {data.base_url} ({data.connection.error ?? "no detail"}). Projects and Inspect
          remain available; readiness is unknown, not zero.
        </p>
      ) : null}
      <div className="writer-mini-scores">
        <span>Connection: {data.connection.reachable ? `${data.connection.status} · ${data.connection.version}` : "unreachable"}</span>
        <span title={data.availability.freshness_note}>
          Cached availability: {data.availability.available ? `${data.availability.models.length} models` : `unknown (${data.availability.error ?? "no payload"})`}
        </span>
        <span title={data.usage.unknown_note}>
          Usage: {data.usage.available ? `${data.usage.models_count ?? 0} models observed` : `unknown (${data.usage.error ?? "no payload"})`}
        </span>
      </div>
      {data.availability.available ? (
        <p className="muted small">
          {data.availability.freshness_note} Discovered {data.availability.discovered_at ?? "unknown"}
          {data.availability.probing ? " · probing in progress" : ""}.
          {data.availability.warnings.length ? ` Warnings: ${data.availability.warnings.join("; ")}` : ""}
        </p>
      ) : null}
      {data.usage.available ? (
        <p className="muted small">
          Outcomes: {JSON.stringify(data.usage.outcomes)} · Billed unknown calls:{" "}
          {data.usage.billed_unknown_calls ?? "unknown"} ({data.usage.unknown_note})
        </p>
      ) : null}
      <p className="muted small">
        Passive dashboard only. No live probe is triggered from this view. Billed costs shown when known;
        unknown remains unknown and is never collapsed to zero.
      </p>
      <ul className="plain-list muted small">
        {data.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </Section>
  );
}
