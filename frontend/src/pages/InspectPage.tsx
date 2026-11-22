import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ScanSearch } from "lucide-react";
import { useApi } from "../api/useApi";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import { timeAgo } from "../lib/format";
import type {
  InspectCapabilityList,
  InspectManifest,
  InspectOpportunityList,
  InspectProjectList,
} from "../types/api";
import {
  CapabilityCatalogue,
  CompositionList,
  CoverageCard,
  InspectStaleNote,
  OpportunityList,
} from "../features/inspect/InspectPanels";
import { isSideEffectful, isUntested } from "../features/inspect/inspect";

function attentionCount(opportunities: Array<Record<string, any>>): number {
  return opportunities.filter(
    (o) => o.status !== "resolved" && o.status !== "rejected" && o.human_decision !== "dismissed",
  ).length;
}

export function InspectPage() {
  const manifest = useApi<InspectManifest>("/api/inspect/manifest", { pollMs: 60000 });
  const projects = useApi<InspectProjectList>("/api/inspect/projects", { pollMs: 60000 });
  const capabilities = useApi<InspectCapabilityList>("/api/inspect/capabilities", {
    pollMs: 60000,
  });
  const opportunities = useApi<InspectOpportunityList>("/api/inspect/opportunities", {
    pollMs: 60000,
  });

  const sources = manifest.data?.sources ?? [];
  const counts = manifest.data?.counts ?? {};
  const allCapabilities = capabilities.data?.capabilities ?? [];
  const allOpportunities = opportunities.data?.opportunities ?? [];
  const projectList = projects.data?.projects ?? [];

  const evidence = useMemo(() => {
    const tested = allCapabilities.filter((c) => !isUntested(c)).length;
    const effectful = allCapabilities.filter((c) => isSideEffectful(c)).length;
    const unverified = allCapabilities.filter(
      (c) => typeof c.unverified_reason === "string" && c.unverified_reason.length > 0,
    ).length;
    return { tested, untested: allCapabilities.length - tested, effectful, unverified };
  }, [allCapabilities]);

  const sourceByRepo = useMemo(
    () => new Map(sources.map((s) => [s.repository, s])),
    [sources],
  );
  const staleProjects = projectList.filter((p) => p.record.stale || sourceByRepo.get(p.id)?.stale);

  if (manifest.loading && !manifest.data) {
    return (
      <div className="page">
        <PageHeader
          eyebrow="Inspect · Capability evidence"
          title="Inspect"
          description="Read-only capability evidence published by the Inspect reader."
        />
        <LoadingBlock label="Loading Inspect snapshot" />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Inspect · Capability evidence"
        title="Inspect"
        description="What the inspected apps can do, how to invoke it, whether it actually works, what is missing, and what to improve next. Read-only: this view never runs anything."
        actions={
          manifest.data?.available ? (
            <div className="tag-row">
              <Tag tone="accent">{counts.capabilities ?? 0} capabilities</Tag>
              <Tag>{counts.projects ?? 0} projects</Tag>
              {manifest.data.stale_refresh ? <Tag tone="danger">Stale refresh</Tag> : null}
            </div>
          ) : null
        }
      />

      {manifest.error ? <ErrorState message={manifest.error.message} onRetry={manifest.reload} /> : null}

      <Section
        title="Overview"
        description="One snapshot across the inspected repositories: what exists, how trustworthy it is, and what needs attention."
      >
        {manifest.data && !manifest.data.available ? (
          <EmptyState
            title="No Inspect snapshot published"
            description="The Inspect reader has not published a consumer snapshot yet (output/consumers/mission/). Enrichment may still be running — an empty view is unknown, not zero."
            icon={<ScanSearch size={20} />}
          />
        ) : null}
        {manifest.data?.available ? (
          <>
            <div className="writer-stats">
              <Stat label="Projects" value={counts.projects ?? projectList.length} detail="inspected repositories" />
              <Stat label="Capabilities" value={counts.capabilities ?? allCapabilities.length} detail="published operations" />
              <Stat label="Usages" value={counts.usages ?? 0} detail="invocation observations" />
              <Stat label="Opportunities" value={counts.opportunities ?? allOpportunities.length} detail={`${attentionCount(allOpportunities)} need attention`} />
              <Stat label="Compositions" value={counts.compositions ?? 0} detail="multi-capability workflows" />
            </div>
            <div className="writer-stats">
              <Stat label="Tested" value={evidence.tested} detail="test evidence or demonstrated" />
              <Stat label="Untested" value={evidence.untested} detail="no test, no demonstration" />
              <Stat label="Side-effectful" value={evidence.effectful} detail="writes or external effects" />
              <Stat label="Explicitly unverified" value={evidence.unverified} detail="unverified_reason recorded" />
            </div>
            {manifest.data.stale_refresh ? (
              <p className="warn-text small">
                The last refresh failed validation, so this is the last valid snapshot — not the
                latest inspection. Treat revision pins as possibly behind the inspected apps.
              </p>
            ) : null}
            <p className="muted small">
              Contract {manifest.data.contract_version ?? "unknown"} · snapshot{" "}
              {manifest.data.generated_at ? timeAgo(manifest.data.generated_at) : "unknown"} · validation{" "}
              {String((manifest.data.validation as Record<string, unknown>)?.status ?? "unknown")}
              {manifest.data.snapshot_dir ? ` · ${manifest.data.snapshot_dir}` : ""}
            </p>
            {staleProjects.length ? (
              <p className="warn-text small">
                Stale: {staleProjects.map((p) => p.id).join(", ")} — source changed since inspection.
                See per-project stale reasons below.
              </p>
            ) : null}
            {attentionCount(allOpportunities) > 0 ? (
              <p className="warn-text small">
                {attentionCount(allOpportunities)} opportunit{attentionCount(allOpportunities) === 1 ? "y needs" : "ies need"} a
                human decision — proposed Inspect suggestions are not verified findings.
              </p>
            ) : null}
          </>
        ) : null}
      </Section>

      <Section
        title="Projects"
        description="Inspected repositories, their mapping to Mission applications, evidence counts, and staleness."
      >
        {projects.loading ? <LoadingBlock label="Loading inspected projects" compact /> : null}
        {projects.error ? <InlineError message={projects.error.message} /> : null}
        {projects.data && !projects.data.available ? (
          <EmptyState
            title="No projects published"
            description="No Inspect snapshot is published yet."
          />
        ) : null}
        {(projects.data?.projects ?? []).map((project) => {
          const source = sourceByRepo.get(project.id);
          const stale = Boolean(project.record.stale || source?.stale);
          return (
            <article className="writer-decision-card" key={project.id}>
              <div className="writer-decision-head">
                <strong>{String(project.record.name ?? project.id)}</strong>
                <code className="mono small">{project.id}</code>
                {project.mapped ? (
                  <Tag tone="accent">→ {project.mission_application_id}</Tag>
                ) : (
                  <Tag>unmapped</Tag>
                )}
                {project.record.inspection_status ? (
                  <Tag tone={String(project.record.inspection_status) === "complete" ? "accent" : "warn"}>
                    {String(project.record.inspection_status)}
                  </Tag>
                ) : null}
                {stale ? <Tag tone="danger">Stale</Tag> : <Tag tone="accent">Fresh</Tag>}
              </div>
              <InspectStaleNote
                stale={stale}
                staleReason={typeof source?.stale_reason === "string" ? source.stale_reason : null}
                revision={typeof project.record.head_sha === "string" ? project.record.head_sha : typeof source?.head_sha === "string" ? source.head_sha : null}
                generatedAt={typeof project.record.generated_at === "string" ? project.record.generated_at : null}
              />
              <div className="writer-mini-scores">
                <span title="Published capabilities">capabilities: {String(project.record.capabilities_count ?? "—")}</span>
                {project.record.branch ? <span>branch: {String(project.record.branch)}</span> : null}
                {source?.head_sha || project.record.head_sha ? (
                  <span title="Inspected revision">
                    revision: {String(source?.head_sha ?? project.record.head_sha).slice(0, 12)}
                  </span>
                ) : null}
              </div>
            </article>
          );
        })}
      </Section>

      <Section
        title="Capabilities"
        description="Searchable catalogue of everything the inspected apps can do. Select a row for purpose, inputs, outputs, invocation, and evidence. Copy any command — this panel never runs it."
      >
        <CapabilityCatalogue
          capabilities={capabilities.data?.capabilities}
          loading={capabilities.loading}
          error={capabilities.error}
          available={capabilities.data?.available}
          onRetry={capabilities.reload}
        />
      </Section>

      <Section
        title="Opportunities"
        description="What improvement next: suggested, grouped, with gaps and evidence. Proposed is not verified — a person decides."
      >
        <OpportunityList
          opportunities={opportunities.data?.opportunities}
          loading={opportunities.loading}
          error={opportunities.error}
          available={opportunities.data?.available}
          onRetry={opportunities.reload}
        />
      </Section>

      <Section
        title="Coverage"
        description="Per repository: inspected, deferred, and unknown. Deferred means not covered — never a pass."
      >
        {projectList.length === 0 && !projects.loading ? (
          <EmptyState
            title="No coverage published"
            description="No inspected projects means no coverage records. Enrichment may still be running."
          />
        ) : (
          projectList.map((project) => <CoverageCard key={project.id} projectId={project.id} />)
        )}
      </Section>

      <Section
        title="Compositions"
        description="Multi-capability workflows toward a desired outcome, with required capabilities and gaps."
      >
        <CompositionList showProject />
      </Section>

      <Section title="Boundaries" description="What this view does not claim.">
        <ul className="plain-list writer-boundaries">
          <li>
            Proposed invocations are read from a static snapshot, not observed runs. An
            invocation without usage observations is plausible, not demonstrated.
          </li>
          <li>
            A missing capability, usage, or coverage record is unknown — never evidence
            that the app cannot do it.
          </li>
          <li>
            Opportunities are Inspect suggestions. Nothing here is verified, scheduled, or
            applied; human review happens outside this view.
          </li>
          <li>
            <Link className="text-link" to="/integrations">Inspect integration diagnostics</Link>
          </li>
        </ul>
      </Section>
    </div>
  );
}
