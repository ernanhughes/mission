import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  CircleSlash,
  Inbox,
  Search,
  Sparkles,
} from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  ProvenanceBadge,
  SimpleStatusBadge,
} from "../components/ui";
import { timeAgo, titleCase, truncate } from "../lib/format";
import type { InboxItem } from "../types/api";

const sourceLabels: Record<string, string> = {
  next: "Next",
  work: "Work",
  cocoder: "CoCoder",
  "mission-control": "Mission Control",
};

export function InboxPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [application, setApplication] = useState("");
  const [priority, setPriority] = useState("");
  const path = apiPath("/api/inbox", {
    application_id: application || undefined,
    priority: priority || undefined,
    limit: 150,
  });
  const inbox = useApi<InboxItem[]>(path, { pollMs: 45000 });
  const [busyId, setBusyId] = useState<string | null>(null);
  const items = inbox.data ?? [];
  const sources = useMemo(
    () => Array.from(new Set(items.map((item) => item.source_application))),
    [items],
  );

  async function decide(item: InboxItem, decision: string) {
    if (!item.resource_id) return;
    const reason = window.prompt(`Reason for "${decision}" (optional)`, "");
    if (reason === null) return;
    setBusyId(item.id);
    try {
      await api.post(
        `/api/integrations/${item.source_application}/resources/${item.resource_id}/decision`,
        { decision, reason },
      );
      toast.push("success", `Recorded locally: ${decision}`, "The source application was not modified.");
      inbox.reload();
    } catch (caught) {
      toast.push("error", "Could not record decision", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Unified inbox"
        title="Awaiting your attention"
        description="Research decisions, commercial opportunities, code findings and Mission Control tasks in one place. Source identity is never merged."
        actions={
          <Link className="button button-secondary" to="/search">
            <Search size={15} /> Search everything
          </Link>
        }
      />

      <div className="inbox-summary">
        <div>
          <span className="eyebrow">Across engines</span>
          <strong>{items.length}</strong>
          <span className="muted"> items awaiting review</span>
        </div>
        <div className="inbox-sources">
          {sources.length
            ? sources.map((source) => (
                <span className={`source-pill source-${source}`} key={source}>
                  {sourceLabels[source] ?? source}
                </span>
              ))
            : null}
        </div>
      </div>

      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Filter by source</span>
          <select value={application} onChange={(event) => setApplication(event.target.value)}>
            <option value="">All sources</option>
            <option value="next">Next</option>
            <option value="work">Work</option>
            <option value="cocoder">CoCoder</option>
            <option value="mission-control">Mission Control</option>
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by priority</span>
          <select value={priority} onChange={(event) => setPriority(event.target.value)}>
            <option value="">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="normal">Normal</option>
          </select>
        </label>
        <span className="toolbar-count">{items.length} items</span>
      </div>

      {inbox.loading && !inbox.data ? <LoadingBlock label="Loading the unified inbox" /> : null}
      {inbox.error ? <ErrorState message={inbox.error.message} onRetry={inbox.reload} /> : null}
      {inbox.data && items.length === 0 ? (
        <EmptyState
          title="Nothing awaiting attention"
          description="Unresolved Next candidates, qualified Work opportunities, CoCoder findings and tasks will appear here."
          icon={<CheckCircle2 size={20} />}
        />
      ) : null}

      <div className="inbox-list">
        {items.map((item) => (
          <article className={`inbox-card priority-${item.priority_label.toLowerCase()}`} key={item.id}>
            <div className="inbox-source-column">
              <span className={`source-pill source-${item.source_application}`}>
                {sourceLabels[item.source_application] ?? item.source_name}
              </span>
              <span className="inbox-priority">{item.priority_label}</span>
            </div>
            <div className="inbox-card-main">
              <div className="inbox-card-head">
                <div>
                  <span className="eyebrow">{titleCase(item.item_type.replace(/_/g, " "))}</span>
                  <h3>{item.title}</h3>
                </div>
                <SimpleStatusBadge state={item.state.toLowerCase()} label={item.state} />
              </div>
              <p>{truncate(item.summary, 500)}</p>
              <div className="inbox-meta">
                {item.project_name ? <span>{item.project_name}</span> : <span>No project</span>}
                <span>{timeAgo(item.observed_at)}</span>
                <ProvenanceBadge value="external_claim" />
                {item.decision_state === "pending" ? <span>Decision pending</span> : null}
              </div>
            </div>
            <div className="inbox-actions">
              <button
                className="button button-primary button-small"
                onClick={() => navigate(item.target_path)}
              >
                Open <ArrowRight size={13} />
              </button>
              {item.resource_id
                ? item.actions
                    .filter((action) => action !== "open")
                    .slice(0, 3)
                    .map((action) => (
                      <button
                        className="button button-ghost button-small"
                        key={action}
                        disabled={busyId === item.id}
                        onClick={() => void decide(item, action)}
                      >
                        {titleCase(action)}
                      </button>
                    ))
                : null}
            </div>
          </article>
        ))}
      </div>

      {items.length > 0 ? (
        <p className="muted small inbox-footnote">
          Decisions made here are stored locally with a <code>local_only</code> sync state. They do not
          modify Next, Work, CoCoder or their databases.
        </p>
      ) : null}
    </div>
  );
}
