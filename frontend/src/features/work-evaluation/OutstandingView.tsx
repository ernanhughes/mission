import { useMemo, useState } from "react";
import { useApi } from "../../api/useApi";
import { api, apiPath } from "../../api/client";
import { useToast } from "../../components/Toast";
import type { WorkFinding, WorkFindingGroup, WorkOverview } from "../../types/api";
import { EmptyState, ErrorState, LoadingBlock, Tag } from "../../components/ui";
import { actionAdvice, actionForGap, gapClassLabel, gapClosureCriteria, verdictTone } from "./labels";

type StatusFilter = "" | "suspected" | "confirmed" | "authorized" | "closed";
type KindFilter = "" | "missing_requirement" | "defect" | "verification_gap" | "unsupported_claim";
type Mode = "groups" | "findings";

export function OutstandingView({ projectKey, onOpenProposals }: { projectKey: string; onOpenProposals?: () => void }) {
  const [mode, setMode] = useState<Mode>("groups");
  const [status, setStatus] = useState<StatusFilter>("");
  const [kind, setKind] = useState<KindFilter>("");
  const [limit, setLimit] = useState(100);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const episodes = useApi<WorkOverview>(
    projectKey ? null : apiPath("/api/work-evaluation/overview", { limit: 100 }),
  );
  const projectOf = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of episodes.data?.episodes ?? []) map.set(row.id, row.project_key ?? "");
    return map;
  }, [episodes.data]);
  const findings = useApi<{ findings: WorkFinding[] }>(
    apiPath("/api/work-evaluation/findings", {
      status: status || undefined,
      limit,
    }),
  );
  // W6B groups: computed read-only layer; members stay individually listed.
  const groups = useApi<{ groups: WorkFindingGroup[] }>(
    mode === "groups" ? "/api/work-evaluation/findings/groups" : null,
  );

  // Findings list loads lazily; groups mode must not block on it.
  const needle = projectKey.trim().toLowerCase();
  const items = (findings.data?.findings ?? []).filter(
    (f) =>
      (!kind || f.kind === kind) &&
      (!needle || (projectOf.get(f.episode_id) ?? "").toLowerCase().includes(needle)),
  );
  const kinds: Record<string, number> = {};
  for (const f of findings.data?.findings ?? []) kinds[f.kind] = (kinds[f.kind] ?? 0) + 1;

  return (
    <div>
      <div className="toolbar" role="tablist" aria-label="Outstanding work mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "groups"}
          className={`button button-small ${mode === "groups" ? "button-primary" : "button-ghost"}`}
          onClick={() => setMode("groups")}
        >
          Groups
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "findings"}
          className={`button button-small ${mode === "findings" ? "button-primary" : "button-ghost"}`}
          onClick={() => setMode("findings")}
        >
          Individual findings
        </button>
      </div>
      {mode === "groups" ? (
        <GroupsList groups={groups} projectKey={projectKey} openGroup={openGroup} setOpenGroup={setOpenGroup} onOpenProposals={onOpenProposals} />
      ) : (
        <FindingsList
          findings={findings}
          items={items}
          kinds={kinds}
          kind={kind}
          setKind={setKind}
          status={status}
          setStatus={setStatus}
          limit={limit}
          setLimit={setLimit}
        />
      )}
    </div>
  );
}

function GroupsList({
  groups, projectKey, openGroup, setOpenGroup, onOpenProposals,
}: {
  groups: ReturnType<typeof useApi<{ groups: WorkFindingGroup[] }>>;
  projectKey: string;
  openGroup: string | null;
  setOpenGroup: (id: string | null) => void;
  onOpenProposals?: () => void;
}) {
  if (groups.loading) return <LoadingBlock label="Loading finding groups" />;
  if (groups.error)
    return <ErrorState message={`Finding groups unavailable: ${groups.error.message}`} onRetry={groups.reload} />;
  const needle = projectKey.trim().toLowerCase();
  const items = (groups.data?.groups ?? []).filter(
    (g) => !needle || (g.project_key ?? "").toLowerCase().includes(needle),
  );
  const totalMembers = items.reduce((n, g) => n + g.member_count, 0);
  if (items.length === 0)
    return (
      <EmptyState
        title="No open finding groups"
        description="Nothing requires attention in scope. Groups aggregate identical assertions; members are never deleted."
      />
    );
  return (
    <div>
      <div className="toolbar">
        <span className="toolbar-count">
          {items.length} group(s) · {totalMembers} underlying finding(s) · nothing hidden
        </span>
      </div>
      <ul className="activity-feed">
        {items.map((g) => {
          const open = openGroup === g.id;
          return (
            <li key={g.id}>
              <span className="activity-marker type-user" aria-hidden="true" />
              <div className="activity-entry">
                <div className="activity-head">
                  <strong>{gapClassLabel(g.gap_class)} × {g.member_count}</strong>
                  <Tag tone={g.severity === "major" ? "danger" : "default"}>{g.severity}</Tag>
                  <Tag>{g.status}</Tag>
                </div>
                <div className="activity-meta">
                  <span>{g.episode_ids.length} episode(s) affected</span>
                  {g.project_key ? <span>{g.project_key}</span> : null}
                </div>
                {g.sample_title ? <p className="muted">e.g. {g.sample_title}</p> : null}
                <p className="muted">Recommended: {actionForGap(g.gap_class, "")} — {actionAdvice(actionForGap(g.gap_class, ""))}</p>
                <p className="muted">Closes when: {gapClosureCriteria(g.gap_class)}</p>
                <div className="activity-actions">
                  <button
                    type="button"
                    className="button button-ghost button-small"
                    onClick={() => setOpenGroup(open ? null : g.id)}
                  >
                    {open ? "Hide members" : `Show ${g.member_count} underlying finding(s)`}
                  </button>
                  <GenerateCommission group={g} onOpenProposals={onOpenProposals} />
                </div>
                {open ? (
                  <div className="activity-meta">
                    <span>Episodes: {g.episode_ids.slice(0, 12).join(", ")}{g.episode_ids.length > 12 ? ` +${g.episode_ids.length - 12} more` : ""}</span>
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function GenerateCommission({ group, onOpenProposals }: { group: WorkFindingGroup; onOpenProposals?: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<string[]>([]);

  async function generate() {
    setBusy(true);
    setCreated([]);
    try {
      // One proposal per episode (proposals bind a single episode).
      const byEp = new Map<string, string[]>();
      for (const m of group.members ?? []) {
        if (!byEp.has(m.episode_id)) byEp.set(m.episode_id, []);
        byEp.get(m.episode_id)?.push(m.id);
      }
      const ids: string[] = [];
      const action = actionForGap(group.gap_class, "");
      for (const [ep, fids] of byEp) {
        const out = await api.post<{ status: string; proposal_id?: string; error?: string }>(
          "/api/work-corrective/proposals",
          { episode_id: ep, finding_ids: fids, group_id: group.id, action_category: action },
        );
        if (out.status === "duplicate" && out.proposal_id) {
          ids.push(out.proposal_id);
        } else if (out.status !== "completed" || !out.proposal_id) {
          throw new Error(out.error ?? "proposal rejected");
        } else {
          ids.push(out.proposal_id);
        }
      }
      setCreated(ids);
      toast.push("success", `Commission draft ready (${ids.length} proposal${ids.length === 1 ? "" : "s"}) — review in Proposals`);
    } catch (caught) {
      toast.push("error", `Commission failed: ${caught instanceof Error ? caught.message : "request failed"}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="button button-ghost button-small"
        disabled={busy}
        onClick={() => void generate()}
      >
        {busy ? "Generating…" : "Generate corrective commission"}
      </button>
      {created.length > 0 ? (
        <button type="button" className="button button-ghost button-small" onClick={() => onOpenProposals?.()}>
          Open proposals ({created.length})
        </button>
      ) : null}
    </>
  );
}

function FindingsList({
  findings, items, kinds, kind, setKind, status, setStatus, limit, setLimit,
}: {
  findings: ReturnType<typeof useApi<{ findings: WorkFinding[] }>>;
  items: WorkFinding[];
  kinds: Record<string, number>;
  kind: KindFilter;
  setKind: (v: KindFilter) => void;
  status: StatusFilter;
  setStatus: (v: StatusFilter) => void;
  limit: number;
  setLimit: (v: (n: number) => number) => void;
}) {
  if (findings.loading) return <LoadingBlock label="Loading outstanding work" />;
  if (findings.error)
    return <ErrorState message={`Outstanding work unavailable: ${findings.error.message}`} onRetry={findings.reload} />;

  return (
    <div>
      <div className="toolbar">
        <select aria-label="Filter by finding type" value={kind} onChange={(e) => setKind(e.target.value as KindFilter)}>
          <option value="">All types</option>
          <option value="missing_requirement">Missing requirement</option>
          <option value="defect">Confirmed defect</option>
          <option value="verification_gap">Verification gap</option>
          <option value="unsupported_claim">Unsupported claim</option>
        </select>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)}>
          <option value="">All statuses</option>
          <option value="suspected">Suspected</option>
          <option value="confirmed">Confirmed</option>
          <option value="authorized">Authorized deferral</option>
          <option value="closed">Closed</option>
        </select>
        <span className="toolbar-count">{items.length} finding(s) shown</span>
        {items.length >= limit ? (
          <button
            className="button button-ghost button-small"
            onClick={() => setLimit((v) => Math.min(v + 100, 1000))}
          >
            Show more
          </button>
        ) : null}
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No outstanding findings"
          description="Nothing requires attention in scope. An empty list means no recorded findings, not proof of completeness."
        />
      ) : (
        <ul className="activity-feed">
          {items.map((f) => {
            const tone = verdictTone(f.kind === "unsupported_claim" ? "unsupported_claim" : f.status === "suspected" ? "unknown" : f.kind);
            return (
              <li key={f.id}>
                <span className="activity-marker type-user" aria-hidden="true" />
                <div className="activity-entry">
                  <div className="activity-head">
                    <strong>{f.title}</strong>
                    <Tag tone={f.severity === "major" ? "danger" : "default"}>{f.severity}</Tag>
                    <Tag tone={tone.tone}>{tone.label}</Tag>
                  </div>
                  <div className="activity-meta">
                    <span>{f.kind}</span>
                    <span>{f.status}</span>
                    <span>{f.episode_id}</span>
                  </div>
                  {f.rationale ? <p className="muted">{f.rationale.slice(0, 400)}</p> : null}
                  {f.next_action ? (
                    <div className="activity-actions">
                      <span className="muted">Next: {f.next_action}</span>
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
