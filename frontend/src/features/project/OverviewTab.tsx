import { Link } from "react-router-dom";
import { BookOpen, Crosshair } from "lucide-react";
import { LivingBookCard } from "../living-book/LivingBookCard";
import { EmptyState, LoadingBlock, Section, SimpleStatusBadge, Tag } from "../../components/ui";
import { useApi } from "../../api/useApi";
import { formatDateTime, timeAgo, truncate } from "../../lib/format";
import type {
  ProjectDetail,
  QualityCampaign,
  QualityDiscovery,
} from "../../types/api";
import type { ProjectTabId } from "./projectTabs";

type CalRun = {
  run_id: string;
  awaiting?: number;
  reviewed?: number;
  disagreements?: number;
  arm_A_target?: number;
  arm_B_target?: number;
  kind?: string;
};

export function OverviewTab({
  projectId,
  data,
  discovery,
  techOverview,
  campaigns,
  calRuns,
  onNavigate,
}: {
  projectId: string;
  data: ProjectDetail;
  discovery: QualityDiscovery[] | null;
  techOverview: Record<string, unknown> | null;
  campaigns: QualityCampaign[] | null;
  calRuns: CalRun[] | null;
  onNavigate: (tab: ProjectTabId) => void;
}) {
  const publishing = useApi<Record<string, unknown>>(
    `/api/publication/publishing?project_id=${encodeURIComponent(projectId)}`,
  );
  const living = useApi<Record<string, unknown>>(`/api/living-book/projects/${projectId}`);
  const checkpoint = data.latest_checkpoint;
  const openTasks = data.tasks.filter((t) => t.status !== "done" && t.status !== "cancelled");
  const pendingRecs = data.recommendations.filter((r) => r.review_state === "pending");
  const failedCampaigns = (campaigns ?? []).filter((c) =>
    ["failed", "interrupted", "partial"].includes(c.status),
  );
  const activeCampaign = (campaigns ?? []).find((c) =>
    ["pending", "running", "cancelling"].includes(c.status),
  );
  const missingEvals = (discovery ?? []).filter((d) => !d.has_current).length;
  const staleEvals = (discovery ?? []).filter((d) => d.eligibility === "stale").length;
  const unresolvedTech = typeof techOverview?.claims_unresolved === "number" ? (techOverview.claims_unresolved as number) : null;
  const awaitingCal = (calRuns ?? []).reduce((sum, r) => sum + (r.awaiting ?? 0), 0);
  const recent = [...(data.activity ?? [])]
    .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1))
    .slice(0, 5);

  const bookChapters = discovery?.length ?? null;
  const currentEvals = (discovery ?? []).filter((d) => d.has_current).length;
  const techClaims = typeof techOverview?.claims_total === "number" ? (techOverview.claims_total as number) : null;

  return (
    <div className="overview-workspace">
      <div className="overview-grid">
        <Section title="Project summary" description="What this project is and where it stands.">
          <p>{data.description || "No description recorded."}</p>
          <div className="inline-meta">
            <SimpleStatusBadge state={data.status} />
            <span className="muted small">{data.kind}</span>
            {data.book ? <span className="muted small">{data.book.title}</span> : null}
          </div>
          <dl className="kv-list">
            <div className="key-value"><dt>Milestone</dt><dd>{data.current_milestone || "No milestone recorded."}</dd></div>
            <div className="key-value"><dt>Next action</dt><dd>{data.next_action || "No next action saved."}</dd></div>
            <div className="key-value"><dt>Last activity</dt><dd>{timeAgo(data.last_activity_at)}</dd></div>
          </dl>
        </Section>

        <Section
          title="Continue working"
          description="Resume where the work stopped. Checkpoints persist locally."
          actions={checkpoint ? <Tag tone="accent">Checkpoint saved</Tag> : undefined}
        >
          {checkpoint ? (
            <div>
              <strong>{checkpoint.summary}</strong>
              <p className="muted small">
                Last: {checkpoint.last_completed || "not recorded"} · Next:{" "}
                {checkpoint.next_action || data.next_action || "not recorded"}
              </p>
              {checkpoint.blockers ? <p className="warn-text small">Blocker: {checkpoint.blockers}</p> : null}
              <p className="muted small">{formatDateTime(checkpoint.created_at)}</p>
            </div>
          ) : (
            <EmptyState
              title="No checkpoint recorded"
              description="Save a checkpoint in Work to capture where the work stopped."
              icon={<Crosshair size={19} />}
            />
          )}
          <div className="button-row">
            <button className="button button-secondary button-small" onClick={() => onNavigate("work")}>
              Open Work to save a checkpoint
            </button>
            {data.book ? (
              <Link className="button button-primary button-small" to={`/projects/${projectId}/read`}>
                <BookOpen size={14} /> Continue reading
              </Link>
            ) : null}
          </div>
        </Section>
      </div>

      {data.book || (discovery && discovery.length) ? (
        <Section title="Book progress" description="Chapter inventory and evidence coverage. Unknown stays unknown.">
          <div className="writer-mini-scores">
            <span title="Chapters discovered">Chapters: {bookChapters ?? "—"}</span>
            <span title="Chapters with current prose evaluation">
              Current prose: {currentEvals} / {bookChapters ?? "—"}
            </span>
            <span title="Missing evaluations">Missing: {missingEvals}</span>
            {staleEvals > 0 ? <span title="Stale evaluations">Stale: {staleEvals}</span> : null}
            <span title="Technical claims">Technical claims: {techClaims ?? "—"}</span>
            {unresolvedTech !== null ? <span title="Unresolved technical claims">Unresolved: {unresolvedTech}</span> : null}
          </div>
          {living.data ? (
            <p className="muted small">
              Reading room: {String((living.data as { state?: string }).state ?? "unknown")} ·{" "}
              {(() => {
                const d = living.data as { book?: { chapter_count?: number } | null };
                return d.book ? `${d.book.chapter_count} chapters` : "no book linked";
              })()}
            </p>
          ) : living.loading ? (
            <LoadingBlock label="Loading reading progress" compact />
          ) : null}
          {data.book ? <LivingBookCard projectId={projectId} /> : null}
          <div className="button-row">
            <button className="button button-secondary button-small" onClick={() => onNavigate("book")}>Review book</button>
            <button className="button button-secondary button-small" onClick={() => onNavigate("quality")}>Evaluate quality</button>
            <button className="button button-secondary button-small" onClick={() => onNavigate("technical")}>Inspect technical evidence</button>
          </div>
        </Section>
      ) : null}

      <Section title="Attention required" description="What needs a person next. Advisory stays advisory.">
        {pendingRecs.length === 0 &&
        failedCampaigns.length === 0 &&
        missingEvals === 0 &&
        (unresolvedTech ?? 0) === 0 &&
        awaitingCal === 0 ? (
          <p className="muted small">Nothing outstanding. Missing evidence is reported, never zero-filled.</p>
        ) : (
          <ul className="plain-list">
            {pendingRecs.length ? (
              <li>
                <strong>{pendingRecs.length} pending recommendation{pendingRecs.length === 1 ? "" : "s"}</strong>{" "}
                <button className="text-link" onClick={() => onNavigate("work")}>Review in Work</button>
              </li>
            ) : null}
            {failedCampaigns.length ? (
              <li>
                <strong>{failedCampaigns.length} interrupted campaign{failedCampaigns.length === 1 ? "" : "s"}</strong>{" "}
                <span className="muted small">{failedCampaigns.map((c) => c.id.slice(0, 8)).join(", ")}</span>{" "}
                <button className="text-link" onClick={() => onNavigate("quality")}>Resume in Quality</button>
              </li>
            ) : null}
            {activeCampaign ? (
              <li>
                <strong>Active campaign:</strong>{" "}
                <span className="muted small">
                  {activeCampaign.id.slice(0, 14)} · {activeCampaign.status} · {activeCampaign.completed} done ·{" "}
                  {activeCampaign.remaining} remaining
                </span>
              </li>
            ) : null}
            {missingEvals > 0 ? (
              <li>
                <strong>{missingEvals} chapters missing evaluation</strong>{" "}
                <button className="text-link" onClick={() => onNavigate("quality")}>Evaluate quality</button>
              </li>
            ) : null}
            {staleEvals > 0 ? (
              <li>
                <strong>{staleEvals} stale evaluations</strong>{" "}
                <span className="muted small">Source changed since evaluation.</span>
              </li>
            ) : null}
            {unresolvedTech !== null && unresolvedTech > 0 ? (
              <li>
                <strong>{unresolvedTech} unresolved technical claims</strong>{" "}
                <button className="text-link" onClick={() => onNavigate("technical")}>Inspect evidence</button>
              </li>
            ) : null}
            {awaitingCal > 0 ? (
              <li>
                <strong>{awaitingCal} calibration reviews awaiting</strong>{" "}
                <button className="text-link" onClick={() => onNavigate("calibration")}>Continue calibration</button>
              </li>
            ) : null}
            {publishing.data ? (
              <li>
                <span className="muted small">
                  Publishing gate: {String((publishing.data as { publication_gate?: string }).publication_gate ?? "unknown")} ·{" "}
                  {(() => {
                    const d = publishing.data as { chapter_count?: number | null };
                    return d.chapter_count != null ? `${d.chapter_count} chapters observed` : "chapter count unknown";
                  })()}
                </span>{" "}
                <button className="text-link" onClick={() => onNavigate("publishing")}>Review readiness</button>
              </li>
            ) : null}
            {openTasks.length > 0 ? (
              <li>
                <strong>{openTasks.length} open tasks</strong>{" "}
                <button className="text-link" onClick={() => onNavigate("work")}>View tasks</button>
              </li>
            ) : null}
          </ul>
        )}
      </Section>

      <Section
        title="Recent activity"
        description="Latest project events. Full history lives in Activity."
        actions={<button className="text-link" onClick={() => onNavigate("activity")}>View all activity</button>}
      >
        {recent.length ? (
          <ul className="activity-feed">
            {recent.map((event) => (
              <li key={event.id}>
                <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
                <div>
                  <div className="activity-head">
                    <strong>{event.title}</strong>
                  </div>
                  <span className="activity-meta">
                    {timeAgo(event.occurred_at)}
                  </span>
                  {event.detail ? <p className="activity-detail">{truncate(event.detail, 180)}</p> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">No activity recorded yet.</p>
        )}
      </Section>

      <Section title="Quick navigation" description="Jump directly to the relevant workspace.">
        <div className="button-row">
          <button className="button button-secondary button-small" onClick={() => onNavigate("book")}>Review book</button>
          <button className="button button-secondary button-small" onClick={() => onNavigate("quality")}>Evaluate quality</button>
          <button className="button button-secondary button-small" onClick={() => onNavigate("technical")}>Inspect technical evidence</button>
          <button className="button button-secondary button-small" onClick={() => onNavigate("calibration")}>Continue calibration review</button>
          <button className="button button-secondary button-small" onClick={() => onNavigate("publishing")}>Review publication readiness</button>
          <button className="button button-secondary button-small" onClick={() => onNavigate("activity")}>View activity</button>
        </div>
      </Section>
    </div>
  );
}
