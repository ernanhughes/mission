import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Copy, Search } from "lucide-react";
import { errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  KeyValue,
  LoadingBlock,
  PathText,
  Section,
  SimpleStatusBadge,
  Stat,
  Tag,
} from "../../components/ui";
import { copyText } from "../../lib/clipboard";
import { timeAgo, titleCase } from "../../lib/format";
import type { ApiError } from "../../api/client";
import { OpportunityProposalBridge } from "../praxis/ProposalBridge";
import {
  facetValues,
  isSideEffectful,
  isUntested,
  needsAttention,
  shortSha,
  uniqueStrings,
  useInspectCapabilities,
  useInspectCompositions,
  useInspectCoverage,
  useInspectOpportunities,
  useInspectProjects,
  useInspectUsage,
} from "./inspect";

function toneForStatus(status: unknown): "accent" | "danger" | "warn" | "default" {
  const text = String(status ?? "").toLowerCase();
  if (text.includes("complete") || text === "current" || text === "verified") return "accent";
  if (text === "partial" || text.includes("stale") || text === "proposed") return "warn";
  if (text.includes("fail") || text.includes("error") || text.includes("unknown")) return "danger";
  return "default";
}

/**
 * Render one composition step. Snapshot steps are objects
 * ({order, capability_id, description, inputs, outputs}); older or hand-made
 * snapshots may carry plain strings. Never interpolate the object itself:
 * String({...}) renders as "[object Object]".
 */
function formatCompositionStep(step: unknown): string {
  if (typeof step === "string") return step.slice(0, 240);
  if (step && typeof step === "object") {
    const s = step as Record<string, unknown>;
    const parts: string[] = [];
    if (s.order !== undefined && s.order !== null) parts.push(`${String(s.order)}.`);
    if (typeof s.capability_id === "string" && s.capability_id) parts.push(s.capability_id);
    if (typeof s.description === "string" && s.description) parts.push(`— ${s.description}`);
    const text = parts.join(" ").trim();
    if (text) return text.slice(0, 240);
  }
  return String(step ?? "").slice(0, 240);
}

export function InspectStaleNote({
  stale,
  staleReason,
  revision,
  generatedAt,
}: {
  stale?: boolean;
  staleReason?: string | null;
  revision?: string | null;
  generatedAt?: string | null;
}) {
  if (!stale && !staleReason && !revision) return null;
  return (
    <p className="warn-text small" role="note">
      {stale ? "Stale snapshot" : "Snapshot note"}
      {revision ? ` · revision ${shortSha(revision)}` : ""}
      {generatedAt ? ` · inspected ${timeAgo(generatedAt)}` : ""}
      {staleReason ? ` — ${staleReason}` : ""}
    </p>
  );
}

export function InspectQueryState({
  loading,
  error,
  available,
  empty,
  loadingLabel,
  emptyTitle,
  emptyDescription,
  onRetry,
  children,
}: {
  loading: boolean;
  error: ApiError | null;
  available: boolean | undefined;
  empty: boolean;
  loadingLabel: string;
  emptyTitle: string;
  emptyDescription: string;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  if (loading) return <LoadingBlock label={loadingLabel} compact />;
  if (error) return <ErrorState message={error.message} onRetry={onRetry} />;
  if (available === false) {
    return (
      <EmptyState
        title={emptyTitle}
        description="No Inspect snapshot is published yet. The reader publishes one under output/consumers/mission/; until then this view has nothing to show."
      />
    );
  }
  if (empty) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return <>{children}</>;
}

function CopyCommand({ command, label }: { command: string; label: string }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await copyText(command);
      setCopied(true);
      toast.push("success", "Command copied", "Paste it into a terminal yourself — this panel never runs commands.");
      window.setTimeout(() => setCopied(false), 2000);
    } catch (caught) {
      toast.push("error", "Could not copy", errorMessage(caught));
    }
  }
  return (
    <span className="row">
      <code className="mono">{command}</code>
      <button
        className="button button-secondary button-small"
        onClick={() => void copy()}
        aria-label={label}
        title="Copy to clipboard. This panel never executes commands."
      >
        <Copy size={13} /> {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

export function CapabilityWarnings({ capability }: { capability: Record<string, any> }) {
  const notes = needsAttention(capability);
  if (!notes.length) return null;
  return (
    <div className="inline-meta">
      {notes.map((note) => (
        <span className="warn-text small" key={note}>
          <AlertTriangle size={13} aria-hidden="true" /> {note}
        </span>
      ))}
    </div>
  );
}

function EvidenceList({ evidence }: { evidence: unknown }) {
  const items = Array.isArray(evidence) ? evidence : [];
  if (!items.length) {
    return <p className="muted small">No evidence recorded. Unverified — not a pass.</p>;
  }
  return (
    <ul className="plain-list">
      {items.map((item: Record<string, any>, index: number) => (
        <li key={`${String(item?.kind ?? "evidence")}-${index}`} className="muted small">
          <Tag tone={String(item?.kind ?? "") === "test" ? "accent" : "info"}>
            {String(item?.kind ?? "evidence")}
          </Tag>{" "}
          {item?.path ? <PathText>{String(item.path)}</PathText> : null}{" "}
          {item?.detail ? <span>{String(item.detail).slice(0, 400)}</span> : null}
          {Array.isArray(item?.symbols) && item.symbols.length ? (
            <span className="mono small"> · {item.symbols.map(String).join(", ")}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function InvocationBlock({ capability }: { capability: Record<string, any> }) {
  const fn = (capability.functionality ?? {}) as Record<string, any>;
  const rows: Array<[string, unknown]> = [
    ["Accomplishes", fn.accomplishes],
    ["Inputs", fn.inputs],
    ["Outputs", fn.outputs],
    ["Dependencies", fn.dependencies],
  ];
  return (
    <div className="writer-dimension-detail">
      {capability.description ? <p>{String(capability.description)}</p> : null}
      {fn.invocation ? (
        <p className="muted small">
          Invocation: <CopyCommand command={String(fn.invocation)} label={`Copy invocation for ${String(capability.id ?? "capability")}`} />
        </p>
      ) : null}
      {fn.usage_example && fn.usage_example !== fn.invocation ? (
        <p className="muted small">
          Example: <CopyCommand command={String(fn.usage_example)} label={`Copy usage example for ${String(capability.id ?? "capability")}`} />
        </p>
      ) : null}
      <dl className="kv-list">
        {rows.map(([label, value]) => {
          if (value == null || (Array.isArray(value) && value.length === 0) || value === "") return null;
          return (
            <KeyValue key={label} label={label}>
              {Array.isArray(value) ? value.map(String).join(" · ") : String(value)}
            </KeyValue>
          );
        })}
      </dl>
      <CapabilityWarnings capability={capability} />
    </div>
  );
}

function UsageBlock({ capabilityId }: { capabilityId: string }) {
  const usage = useInspectUsage(capabilityId);
  if (usage.loading) return <LoadingBlock label="Loading usage observations" compact />;
  if (usage.error) return <InlineError message={usage.error.message} />;
  if (usage.data && !usage.data.available) {
    return <p className="muted small">No Inspect snapshot is published, so no usage observations exist.</p>;
  }
  const usages = usage.data?.usages ?? [];
  if (!usages.length) {
    return (
      <p className="muted small">
        No usage observations recorded for this capability. How to invoke it is
        plausible but unverified — the invocation above is proposed, not demonstrated.
      </p>
    );
  }
  return (
    <ul className="plain-list">
      {usages.map((item: Record<string, any>, index: number) => (
        <li key={String(item.outcome ?? item.id ?? index)} className="writer-finding">
          <div className="writer-finding-head">
            <strong>{String(item.outcome ?? "Usage")}</strong>
            {item.invocation_status ? <Tag>{String(item.invocation_status)}</Tag> : null}
            {item.verification_status ? (
              <Tag tone={String(item.verification_status).includes("unverified") ? "warn" : "info"}>
                {String(item.verification_status)}
              </Tag>
            ) : null}
            {item.documentation_status ? <Tag>{String(item.documentation_status)}</Tag> : null}
          </div>
          {item.description ? <p className="muted small">{String(item.description).slice(0, 500)}</p> : null}
          {Array.isArray(item.invocations) && item.invocations.length ? (
            <ul className="plain-list">
              {item.invocations.map((inv: Record<string, any>, invIndex: number) => (
                <li key={invIndex} className="muted small">
                  <code className="mono">{String(inv.mechanism ?? "")}</code>{" "}
                  <PathText>{String(inv.target ?? "")}</PathText>
                  {inv.arguments ? <span> · {String(inv.arguments).slice(0, 200)}</span> : null}
                  {inv.side_effects ? <span className="warn-text"> · side effects: {String(inv.side_effects).slice(0, 200)}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
          {Array.isArray(item.examples) && item.examples.length ? (
            <div className="table-wrap">
              {item.examples.map((example: Record<string, any>, exIndex: number) => (
                <p key={exIndex} className="muted small">
                  <strong>{String(example.title ?? "Example")}</strong>
                  {example.command ? (
                    <>
                      {" — "}
                      <CopyCommand command={String(example.command)} label={`Copy example command: ${String(example.title ?? "")}`} />
                    </>
                  ) : null}
                  {example.expected ? <span> · expected: {String(example.expected).slice(0, 200)}</span> : null}
                  {example.validated === false ? <span className="warn-text"> · unvalidated</span> : null}
                </p>
              ))}
            </div>
          ) : null}
          {item.limitations ? <p className="warn-text small">Limitations: {String(item.limitations).slice(0, 300)}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function CapabilityDetail({ capability }: { capability: Record<string, any> }) {
  const [showUsage, setShowUsage] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const evidence = Array.isArray(capability.evidence) ? capability.evidence : [];
  return (
    <article className="writer-chapter-detail" aria-label={`Capability ${String(capability.id ?? "")}`}>
      <div className="writer-chapter-detail-head">
        <div>
          <span className="eyebrow">Capability evidence</span>
          <h3>{String(capability.name ?? capability.id)}</h3>
          <div className="inline-meta">
            <code className="mono small">{String(capability.id ?? "")}</code>
            {capability.subsystem ? <Tag>{String(capability.subsystem)}</Tag> : null}
            {capability.maturity ? (
              <Tag tone={capability.maturity === "implemented" ? "accent" : "default"}>
                {String(capability.maturity)}
              </Tag>
            ) : null}
            {capability.operational_status ? (
              <Tag tone={String(capability.operational_status).includes("demonstrat") ? "accent" : "warn"}>
                {String(capability.operational_status)}
              </Tag>
            ) : null}
            {capability.risk ? (
              <Tag tone={isSideEffectful(capability) ? "danger" : "default"}>
                {String(capability.risk)}
              </Tag>
            ) : null}
            {(capability.accessibility ?? []).map((access: unknown) => (
              <Tag key={String(access)}>{String(access)}</Tag>
            ))}
          </div>
        </div>
        {capability.repository ? <PathText>{String(capability.repository)}</PathText> : null}
      </div>
      <InvocationBlock capability={capability} />
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={() => setShowEvidence((v) => !v)} aria-expanded={showEvidence}>
          {showEvidence ? "Hide evidence" : `Evidence (${evidence.length})`}
        </button>
        <button className="button button-secondary button-small" onClick={() => setShowUsage((v) => !v)} aria-expanded={showUsage}>
          {showUsage ? "Hide usage" : "How to use it"}
        </button>
      </div>
      {showEvidence ? <EvidenceList evidence={evidence} /> : null}
      {showUsage && capability.id ? <UsageBlock capabilityId={String(capability.id)} /> : null}
    </article>
  );
}

export function CapabilityCatalogue({
  capabilities,
  loading,
  error,
  available,
  onRetry,
  projectOptions,
  fixedProject,
  idPrefix = "inspect",
}: {
  capabilities: Array<Record<string, any>> | undefined;
  loading: boolean;
  error: ApiError | null;
  available: boolean | undefined;
  onRetry: () => void;
  projectOptions?: string[];
  fixedProject?: string | null;
  idPrefix?: string;
}) {
  const [query, setQuery] = useState("");
  const [project, setProject] = useState("ALL");
  const [subsystem, setSubsystem] = useState("ALL");
  const [access, setAccess] = useState("ALL");
  const [verification, setVerification] = useState("ALL");
  const [risk, setRisk] = useState("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [visible, setVisible] = useState(25);

  const all = useMemo(() => capabilities ?? [], [capabilities]);
  const subsystems = useMemo(() => facetValues(all, (c) => c.subsystem), [all]);
  const accesses = useMemo(() => facetValues(all, (c) => c.accessibility), [all]);
  const verifications = useMemo(() => facetValues(all, (c) => c.operational_status), [all]);
  const risks = useMemo(() => facetValues(all, (c) => c.risk), [all]);
  const projects = useMemo(
    () => projectOptions ?? uniqueStrings(all.map((c) => c.repository)),
    [projectOptions, all],
  );

  const needle = query.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      all.filter((capability) => {
        if (fixedProject && capability.repository !== fixedProject) return false;
        if (!fixedProject && project !== "ALL" && capability.repository !== project) return false;
        if (subsystem !== "ALL" && capability.subsystem !== subsystem) return false;
        if (access !== "ALL" && !(capability.accessibility ?? []).includes(access)) return false;
        if (verification !== "ALL" && capability.operational_status !== verification) return false;
        if (risk !== "ALL" && capability.risk !== risk) return false;
        if (needle) {
          const haystack = `${capability.id ?? ""} ${capability.name ?? ""} ${capability.description ?? ""}`.toLowerCase();
          if (!haystack.includes(needle)) return false;
        }
        return true;
      }),
    [all, fixedProject, project, subsystem, access, verification, risk, needle],
  );

  const grouped = useMemo(() => {
    const map = new Map<string, Array<Record<string, any>>>();
    for (const capability of filtered.slice(0, visible)) {
      const key = String(capability.subsystem ?? "ungrouped");
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(capability);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered, visible]);

  const selected = selectedId ? all.find((c) => String(c.id) === selectedId) ?? null : null;

  return (
    <InspectQueryState
      loading={loading}
      error={error}
      available={available}
      empty={(capabilities ?? []).length === 0}
      loadingLabel="Loading capability catalogue"
      emptyTitle="No capabilities published"
      emptyDescription="The Inspect snapshot contains no capabilities yet. Enrichment may still be running — nothing here is a verdict about the inspected apps."
      onRetry={onRetry}
    >
      <div className="inline-form" role="search">
        <label className="muted small">
          <Search size={13} aria-hidden="true" /> Search{" "}
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setVisible(25);
            }}
            placeholder="name, id or description"
            aria-label="Search capabilities"
            size={28}
          />
        </label>
        {!fixedProject ? (
          <label className="muted small">
            Project{" "}
            <select value={project} onChange={(e) => { setProject(e.target.value); setVisible(25); }} aria-label="Filter by project">
              <option value="ALL">All</option>
              {projects.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="muted small">
          Subsystem{" "}
          <select value={subsystem} onChange={(e) => { setSubsystem(e.target.value); setVisible(25); }} aria-label="Filter by subsystem">
            <option value="ALL">All</option>
            {subsystems.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Access{" "}
          <select value={access} onChange={(e) => { setAccess(e.target.value); setVisible(25); }} aria-label="Filter by access">
            <option value="ALL">All</option>
            {accesses.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Verification{" "}
          <select value={verification} onChange={(e) => { setVerification(e.target.value); setVisible(25); }} aria-label="Filter by verification">
            <option value="ALL">All</option>
            {verifications.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Risk{" "}
          <select value={risk} onChange={(e) => { setRisk(e.target.value); setVisible(25); }} aria-label="Filter by risk">
            <option value="ALL">All</option>
            {risks.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">
        {filtered.length} of {all.length} capabilities
        {needle ? ` matching “${query.trim()}”` : ""} · grouped by subsystem.
      </p>
      {grouped.map(([subsystemName, items]) => (
        <details key={subsystemName} open={grouped.length <= 4} id={`${idPrefix}-subsystem-${subsystemName}`}>
          <summary className="muted">
            {subsystemName} ({items.length})
          </summary>
          <div className="writer-decision-queue">
            {items.map((capability) => {
              const id = String(capability.id ?? "");
              const active = selectedId === id;
              return (
                <button
                  key={id}
                  className={`writer-queue-row ${active ? "active" : ""}`}
                  onClick={() => setSelectedId(active ? null : id)}
                  aria-expanded={active}
                >
                  <span className="writer-queue-main">
                    <strong>{String(capability.name ?? id)}</strong>
                    <small>{String(capability.description ?? "").slice(0, 160)}</small>
                    <span className="inline-meta">
                      <code className="mono small">{id}</code>
                      {!fixedProject && capability.repository ? <span>{String(capability.repository)}</span> : null}
                      {capability.operational_status ? <span>{String(capability.operational_status)}</span> : null}
                      {isUntested(capability) ? <span className="warn-text">untested</span> : null}
                      {isSideEffectful(capability) ? <span className="warn-text">side-effectful</span> : null}
                    </span>
                  </span>
                  <SimpleStatusBadge
                    state={String(capability.maturity ?? "unknown") === "implemented" ? "running" : "pending"}
                    label={titleCase(String(capability.maturity ?? "unknown"))}
                  />
                </button>
              );
            })}
          </div>
        </details>
      ))}
      {filtered.length > visible ? (
        <button className="button button-secondary button-small" onClick={() => setVisible((v) => v + 25)}>
          Show more ({filtered.length - visible} remaining)
        </button>
      ) : null}
      {filtered.length === 0 ? (
        <p className="muted small">No capabilities match these filters. Broaden the search — an empty result is not evidence of absence.</p>
      ) : null}
      {selected ? <CapabilityDetail capability={selected} /> : null}
    </InspectQueryState>
  );
}

export function OpportunityList({
  opportunities,
  loading,
  error,
  available,
  onRetry,
  fixedProject,
}: {
  opportunities: Array<Record<string, any>> | undefined;
  loading: boolean;
  error: ApiError | null;
  available: boolean | undefined;
  onRetry: () => void;
  fixedProject?: string | null;
}) {
  const [category, setCategory] = useState("ALL");
  const [status, setStatus] = useState("attention");
  const all = useMemo(() => {
    const list = opportunities ?? [];
    if (!fixedProject) return list;
    return list.filter(
      (o) => o.repository === fixedProject || (o.project_ids ?? []).includes(fixedProject),
    );
  }, [opportunities, fixedProject]);
  const categories = useMemo(() => uniqueStrings(all.map((o) => o.category)), [all]);
  const filtered = useMemo(
    () =>
      all.filter((o) => {
        if (category !== "ALL" && o.category !== category) return false;
        if (status === "attention") {
          return o.status !== "resolved" && o.status !== "rejected" && o.human_decision !== "dismissed";
        }
        if (status !== "ALL" && o.status !== status) return false;
        return true;
      }),
    [all, category, status],
  );
  const grouped = useMemo(() => {
    const map = new Map<string, Array<Record<string, any>>>();
    for (const item of filtered) {
      const key = String(item.category ?? "uncategorized");
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(item);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  return (
    <InspectQueryState
      loading={loading}
      error={error}
      available={available}
      empty={all.length === 0}
      loadingLabel="Loading opportunities"
      emptyTitle="No opportunities published"
      emptyDescription="The Inspect snapshot contains no opportunities yet. Enrichment may still be running — this is not a claim that no improvements exist."
      onRetry={onRetry}
    >
      <div className="inline-form">
        <label className="muted small">
          Category{" "}
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filter opportunities by category">
            <option value="ALL">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Status{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter opportunities by status">
            <option value="attention">Needs attention</option>
            <option value="ALL">All</option>
            <option value="proposed">Proposed</option>
            <option value="verified">Verified</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
      </div>
      <p className="muted small">
        {filtered.length} of {all.length} opportunities · proposed Inspect suggestions are
        not verified findings until a person decides.
      </p>
      {grouped.map(([group, items]) => (
        <div key={group}>
          <h4 className="writer-section-heading">{group} ({items.length})</h4>
          {items.map((item) => (
            <article className="writer-decision-card" key={String(item.opportunity_id ?? item.title)}>
              <div className="writer-decision-head">
                <strong>{String(item.title ?? item.opportunity_id)}</strong>
                {item.status ? (
                  <Tag tone={item.status === "verified" ? "accent" : item.status === "proposed" ? "warn" : "default"}>
                    {String(item.status)}
                  </Tag>
                ) : null}
                {item.confidence ? <Tag>confidence: {String(item.confidence)}</Tag> : null}
                {item.human_decision ? (
                  <Tag tone={item.human_decision === "dismissed" ? "default" : "accent"}>
                    human: {String(item.human_decision)}
                  </Tag>
                ) : (
                  <Tag tone="warn">awaiting human decision</Tag>
                )}
              </div>
              {item.desired_outcome ? <p><strong>Desired outcome:</strong> {String(item.desired_outcome).slice(0, 400)}</p> : null}
              {item.gap ? <p className="muted small"><strong>Gap:</strong> {String(item.gap).slice(0, 400)}</p> : null}
              {item.suggested_action ? (
                <p className="muted small"><strong>Suggested action:</strong> {String(item.suggested_action).slice(0, 400)}</p>
              ) : null}
              {item.unknowns ? <p className="warn-text small"><strong>Unknowns:</strong> {String(item.unknowns).slice(0, 300)}</p> : null}
              {Array.isArray(item.evidence_refs) && item.evidence_refs.length ? (
                <details>
                  <summary className="muted small">Evidence ({item.evidence_refs.length})</summary>
                  <ul className="plain-list">
                    {item.evidence_refs.map((ref: unknown, index: number) => (
                      <li key={index} className="muted small"><code className="mono">{String(ref).slice(0, 200)}</code></li>
                    ))}
                  </ul>
                </details>
              ) : (
                <p className="muted small">No evidence references — proposed, not verified.</p>
              )}
              {item.opportunity_id ? (
                <details>
                  <summary className="muted small">Propose governed improvement</summary>
                  <OpportunityProposalBridge opportunityId={String(item.opportunity_id)} />
                  <p className="muted small">
                    Import only. Approval is human and explicit on the Praxis route; execution never
                    follows automatically. Advisory when no compatible action exists.
                  </p>
                </details>
              ) : null}
            </article>
          ))}
        </div>
      ))}
      {filtered.length === 0 ? (
        <p className="muted small">No opportunities match these filters.</p>
      ) : null}
    </InspectQueryState>
  );
}

export function CoverageCard({ projectId }: { projectId: string }) {
  const coverage = useInspectCoverage(projectId);
  if (coverage.loading) return <LoadingBlock label={`Loading coverage for ${projectId}`} compact />;
  if (coverage.error) {
    return (
      <p className="muted small">
        No coverage record published for <code className="mono">{projectId}</code>
        {coverage.error.message.includes("404") ? "" : ` (${coverage.error.message})`} — coverage is unknown, not zero.
      </p>
    );
  }
  if (coverage.data && !coverage.data.available) {
    return <p className="muted small">No Inspect snapshot is published, so coverage is unknown.</p>;
  }
  const record = coverage.data?.record ?? {};
  const inspected = Array.isArray(record.inspected_subsystems) ? record.inspected_subsystems : [];
  const deferred = Array.isArray(record.deferred_subsystems) ? record.deferred_subsystems : [];
  const discovered = Array.isArray(record.discovered_subsystems) ? record.discovered_subsystems : [];
  const entrypoints = Array.isArray(record.discovered_entrypoints) ? record.discovered_entrypoints : [];
  const inspectedEntrypoints = Array.isArray(record.inspected_entrypoints) ? record.inspected_entrypoints : [];
  const unresolved = Array.isArray(record.unresolved_areas) ? record.unresolved_areas : [];
  return (
    <article className="writer-decision-card">
      <div className="writer-decision-head">
        <strong>{projectId}</strong>
        {record.inspection_status ? (
          <Tag tone={toneForStatus(record.inspection_status)}>{String(record.inspection_status)}</Tag>
        ) : null}
        {record.stale ? <Tag tone="danger">Stale</Tag> : <Tag tone="accent">Fresh</Tag>}
      </div>
      <InspectStaleNote
        stale={Boolean(record.stale)}
        staleReason={typeof record.stale_reason === "string" ? record.stale_reason : null}
        revision={typeof record.head_sha === "string" ? record.head_sha : null}
        generatedAt={typeof record.generated_at === "string" ? record.generated_at : null}
      />
      <div className="writer-mini-scores">
        <span title="Subsystems discovered">discovered: {(discovered.length || record.discovered_subsystems_count) ?? "—"}</span>
        <span title="Subsystems inspected">inspected: {inspected.length}</span>
        <span title="Subsystems deferred">deferred: {deferred.length}</span>
        <span title="Entrypoints discovered">entrypoints: {entrypoints.length || inspectedEntrypoints.length}</span>
        <span title="Unresolved areas">unresolved: {unresolved.length}</span>
      </div>
      {inspected.length ? (
        <p className="muted small"><strong>Inspected:</strong> {inspected.map(String).join(" · ").slice(0, 400)}</p>
      ) : null}
      {deferred.length ? (
        <p className="muted small"><strong>Deferred (unknown, not covered):</strong> {deferred.map(String).join(" · ").slice(0, 400)}</p>
      ) : null}
      {unresolved.length ? (
        <ul className="plain-list">
          {unresolved.map((area: unknown, index: number) => (
            <li key={index} className="warn-text small">{String(area).slice(0, 240)}</li>
          ))}
        </ul>
      ) : null}
      {record.denominator_notes ? (
        <p className="muted small"><strong>Denominator notes:</strong> {String(record.denominator_notes).slice(0, 400)}</p>
      ) : null}
      {record.coverage_limits ? (
        <p className="muted small"><strong>Limits:</strong> {String(record.coverage_limits).slice(0, 400)}</p>
      ) : null}
    </article>
  );
}

export function CompositionList({
  projectId,
  showProject,
}: {
  projectId?: string | null;
  showProject?: boolean;
}) {
  const compositions = useInspectCompositions(projectId ?? undefined);
  const items = compositions.data?.compositions ?? [];
  return (
    <InspectQueryState
      loading={compositions.loading}
      error={compositions.error}
      available={compositions.data?.available}
      empty={items.length === 0}
      loadingLabel="Loading compositions"
      emptyTitle="No compositions published"
      emptyDescription="The Inspect snapshot contains no multi-capability compositions yet. Enrichment may still be running."
      onRetry={compositions.reload}
    >
      <div className="writer-decision-queue">
        {items.map((composition: Record<string, any>) => (
          <article className="writer-decision-card" key={String(composition.composition_id ?? composition.desired_outcome)}>
            <div className="writer-decision-head">
              <strong>{String(composition.desired_outcome ?? composition.composition_id)}</strong>
              {composition.status ? <Tag tone={toneForStatus(composition.status)}>{String(composition.status)}</Tag> : null}
              {showProject && composition.repository ? <Tag>{String(composition.repository)}</Tag> : null}
            </div>
            {composition.description ? <p className="muted small">{String(composition.description).slice(0, 400)}</p> : null}
            {Array.isArray(composition.steps) && composition.steps.length ? (
              <ol className="plain-list">
                {composition.steps.map((step: unknown, index: number) => (
                  <li key={index} className="muted small">{formatCompositionStep(step)}</li>
                ))}
              </ol>
            ) : null}
            {Array.isArray(composition.required_capabilities) && composition.required_capabilities.length ? (
              <p className="muted small">
                <strong>Requires:</strong> {composition.required_capabilities.map(String).join(" · ").slice(0, 400)}
              </p>
            ) : null}
            {Array.isArray(composition.gaps) && composition.gaps.length ? (
              <p className="warn-text small">
                <strong>Gaps:</strong> {composition.gaps.map(String).join(" · ").slice(0, 400)}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </InspectQueryState>
  );
}

/**
 * Per-project Inspect content, reused by the global Inspect page (scoped to one
 * repository) and by the per-project Inspect <Section> on ProjectPage.
 * No duplicated state: each hook call owns its fetch, filtered by inspect id.
 */
export function InspectProjectBlock({
  inspectId,
  showHeader = true,
}: {
  inspectId: string;
  showHeader?: boolean;
}) {
  const capabilities = useInspectCapabilities();
  const opportunities = useInspectOpportunities();
  const projects = useInspectProjects();
  const match = (projects.data?.projects ?? []).find((p) => p.id === inspectId) ?? null;
  const record = match?.record ?? {};
  const scoped = useMemo(
    () => (capabilities.data?.capabilities ?? []).filter((c) => c.repository === inspectId),
    [capabilities.data, inspectId],
  );
  const tested = scoped.filter((c) => !isUntested(c)).length;
  const effectful = scoped.filter((c) => isSideEffectful(c)).length;

  return (
    <>
      {showHeader ? (
        <div className="writer-stats">
          <Stat label="Capabilities" value={record.capabilities_count ?? scoped.length} detail={`in ${inspectId}`} />
          <Stat label="With test evidence" value={tested} detail="tested or demonstrated" />
          <Stat label="Side-effectful" value={effectful} detail="read before running" />
          <Stat
            label="Inspection"
            value={String(record.inspection_status ?? "unknown")}
            detail={record.branch ? `${String(record.branch)} · ${shortSha(record.head_sha)}` : shortSha(record.head_sha)}
          />
        </div>
      ) : null}
      <InspectStaleNote
        stale={Boolean(record.stale)}
        staleReason={typeof record.stale_reason === "string" ? record.stale_reason : null}
        revision={typeof record.head_sha === "string" ? record.head_sha : null}
        generatedAt={typeof record.generated_at === "string" ? record.generated_at : null}
      />
      <Section
        title="Capabilities"
        description={`What ${inspectId} can do, with invocation evidence. Proposed invocations are not verified runs.`}
      >
        <CapabilityCatalogue
          capabilities={capabilities.data?.capabilities}
          loading={capabilities.loading}
          error={capabilities.error}
          available={capabilities.data?.available}
          onRetry={capabilities.reload}
          fixedProject={inspectId}
          idPrefix={`inspect-${inspectId}`}
        />
      </Section>
      <Section
        title="Opportunities"
        description="Suggested improvements for this project. Proposed is not verified — a person decides."
      >
        <OpportunityList
          opportunities={opportunities.data?.opportunities}
          loading={opportunities.loading}
          error={opportunities.error}
          available={opportunities.data?.available}
          onRetry={opportunities.reload}
          fixedProject={inspectId}
        />
      </Section>
      <Section
        title="Coverage"
        description="What was inspected, what was deferred, and what remains unknown."
      >
        <CoverageCard projectId={inspectId} />
      </Section>
      <Section
        title="Compositions"
        description="Multi-capability workflows toward a desired outcome."
      >
        <CompositionList projectId={inspectId} />
      </Section>
    </>
  );
}

/**
 * Per-project Inspect panel for ProjectPage: one <Section> reusing the same
 * hooks and components as the global Inspect view, scoped to the inspect
 * project mapped to this Mission project (via its application ids).
 */
export function InspectPanel({ applicationIds }: { applicationIds: string[] }) {
  const projects = useInspectProjects();
  const ids = useMemo(() => new Set(applicationIds), [applicationIds]);
  const match = useMemo(
    () => (projects.data?.projects ?? []).find((p) => p.mapped && ids.has(p.mission_application_id)) ?? null,
    [projects.data, ids],
  );
  return (
    <Section
      title="Inspect"
      description="Read-only capability evidence for this project, published by the Inspect reader. Proposed invocations are not verified runs — this panel never executes anything."
      actions={
        match ? (
          <div className="button-row">
            <Tag tone="accent">{match.record.capabilities_count ?? 0} capabilities</Tag>
            <Link className="button button-secondary button-small" to="/inspect">
              Open full Inspect view
            </Link>
          </div>
        ) : null
      }
    >
      {projects.loading ? <LoadingBlock label="Loading Inspect snapshot" compact /> : null}
      {projects.error ? <InlineError message={projects.error.message} /> : null}
      {projects.data && !projects.data.available ? (
        <EmptyState
          title="No Inspect snapshot published"
          description="The Inspect reader has not published a consumer snapshot yet. Until then, capability evidence for this project is unknown — not zero."
        />
      ) : null}
      {projects.data?.available && !projects.loading && !match ? (
        <EmptyState
          title="Project not mapped to an inspected repository"
          description="No inspected repository maps to this project's applications. The full Inspect view still shows every inspected app."
          action={
            <Link className="button button-secondary button-small" to="/inspect">
              Open Inspect
            </Link>
          }
        />
      ) : null}
      {match ? <InspectProjectBlock inspectId={match.id} showHeader={false} /> : null}
    </Section>
  );
}
