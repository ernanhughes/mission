import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Crosshair, FlaskConical, Search } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  SimpleStatusBadge,
  Tag,
} from "../../components/ui";
import { shortCommit, timeAgo } from "../../lib/format";
import type { SoftwareInventory as Inventory } from "../../types/api";

const PAGE_SIZE = 25;

function qualityTag(state: string) {
  if (state === "unassessed") return <Tag tone="default">Unassessed</Tag>;
  return <Tag tone="accent">{state}</Tag>;
}

export function SoftwareInventory({ onReconcile }: { onReconcile: () => void }) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [classification, setClassification] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [missingOnly, setMissingOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (debounced.trim()) params.set("search", debounced.trim());
    if (classification) params.set("classification", classification);
    if (attentionOnly) params.set("attention_only", "true");
    if (missingOnly) params.set("missing_only", "true");
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    return `/api/projects/software?${params.toString()}`;
  }, [debounced, classification, attentionOnly, missingOnly, offset]);

  const inventory = useApi<Inventory>(query);

  function onSearch(value: string) {
    setSearch(value);
    setOffset(0);
    window.clearTimeout((onSearch as { timer?: number }).timer);
    (onSearch as { timer?: number }).timer = window.setTimeout(() => setDebounced(value), 250);
  }

  async function setFocus(id: string, name: string) {
    setBusyId(id);
    try {
      await api.post(`/api/projects/${id}/focus`);
      toast.push("success", `Focus set to ${name}`);
    } catch (caught) {
      toast.push("error", "Could not set focus", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  const items = inventory.data?.items ?? [];
  const total = inventory.data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Software systems under quality control. Book manuscripts live under Books; this inventory excludes them."
        actions={
          <button className="button button-secondary" onClick={onReconcile}>
            <FlaskConical size={15} /> Discovery & reconciliation
          </button>
        }
      />

      <div className="toolbar">
        <label className="search-field">
          <Search size={15} aria-hidden="true" />
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search name, description or path"
            aria-label="Search software projects"
          />
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by classification</span>
          <select
            value={classification}
            onChange={(event) => {
              setClassification(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All classifications</option>
            <option value="executable_application">Application</option>
            <option value="background_service">Background service</option>
            <option value="research_project">Research</option>
            <option value="experiment">Experiment</option>
            <option value="library">Library</option>
            <option value="supporting_repository">Supporting</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label className="checkbox inline-checkbox">
          <input
            type="checkbox"
            checked={attentionOnly}
            onChange={(event) => {
              setAttentionOnly(event.target.checked);
              setOffset(0);
            }}
          />
          Needs attention
        </label>
        <label className="checkbox inline-checkbox">
          <input
            type="checkbox"
            checked={missingOnly}
            onChange={(event) => {
              setMissingOnly(event.target.checked);
              setOffset(0);
            }}
          />
          Missing only
        </label>
        <span className="toolbar-count">
          {total} software {total === 1 ? "project" : "projects"}
        </span>
      </div>

      {inventory.loading && !inventory.data ? <LoadingBlock label="Loading software inventory" /> : null}
      {inventory.error ? <ErrorState message={inventory.error.message} onRetry={inventory.reload} /> : null}

      {inventory.data && items.length === 0 ? (
        <EmptyState
          title="No software projects yet"
          description="Run discovery and approve the reconciled inventory to register the repositories under C:\Projects."
          action={
            <button className="button button-secondary button-small" onClick={onReconcile}>
              Open reconciliation
            </button>
          }
        />
      ) : null}

      <div className="project-list">
        {items.map((project) => (
          <article className="project-row" key={project.id}>
            <div className="project-main">
              <div className="project-head">
                <div>
                  <div className="project-title-row">
                    <Link to={`/projects/${project.id}`} className="project-title">
                      {project.name}
                    </Link>
                    <Tag>{project.classification.replace(/_/g, " ")}</Tag>
                    <SimpleStatusBadge state={project.status} />
                    {qualityTag(project.quality_state)}
                    {project.missing ? <Tag tone="danger">Missing</Tag> : null}
                    {!project.missing && project.stale ? <Tag tone="warn">Stale</Tag> : null}
                  </div>
                  <p className="project-description">
                    {project.path ?? "No repository linked"}
                    {project.repository_count > 1 ? ` · ${project.repository_count} repositories` : ""}
                  </p>
                </div>
                <div className="project-row-actions">
                  <button
                    className="button button-ghost button-small"
                    onClick={() => void setFocus(project.id, project.name)}
                    disabled={busyId === project.id}
                  >
                    <Crosshair size={14} /> Set focus
                  </button>
                  <Link className="button button-secondary button-small" to={`/projects/${project.id}`}>
                    Open
                  </Link>
                </div>
              </div>
              <div className="project-facts">
                <span>
                  {project.branch ?? "no branch"} · {shortCommit(project.commit_hash) ?? "no commit indexed"}
                </span>
                <span>Observed {project.last_observed_at ? timeAgo(project.last_observed_at) : "never"}</span>
                <span>
                  {project.needs_attention
                    ? `${project.open_task_count} open tasks · ${project.pending_recommendation_count} pending reviews`
                    : "No open findings"}
                </span>
                <span>
                  {project.applications.length
                    ? `Apps: ${project.applications.map((app) => app.name).join(", ")}`
                    : "No linked application"}
                </span>
                <span>{project.inspect_project_id ? "Inspect: mapped" : "Inspect: unmapped"}</span>
              </div>
            </div>
          </article>
        ))}
      </div>

      {pages > 1 ? (
        <div className="button-row" role="navigation" aria-label="Inventory pages">
          <button
            className="button button-secondary button-small"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            <ArrowLeft size={14} /> Previous
          </button>
          <span className="muted small">
            Page {page} of {pages}
          </span>
          <button
            className="button button-secondary button-small"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next <ArrowRight size={14} />
          </button>
        </div>
      ) : null}
    </div>
  );
}
