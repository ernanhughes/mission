import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  Crosshair,
  FolderKanban,
  Pin,
  PinOff,
  Plus,
  Search,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import { projectLabel, timeAgo } from "../lib/format";
import type { Project } from "../types/api";

function AddProjectForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState("project");
  const [repositoryPath, setRepositoryPath] = useState("");
  const [milestone, setMilestone] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [bookTitle, setBookTitle] = useState("");
  const [pinned, setPinned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/projects", {
        name,
        description,
        kind,
        repository_path: repositoryPath.trim() || null,
        current_milestone: milestone,
        next_action: nextAction,
        pinned,
        book_title: kind === "book" ? bookTitle || name : null,
      });
      toast.push("success", "Project created");
      onSaved();
      onClose();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title="Add project"
      eyebrow="Workspace"
      onClose={onClose}
      footer={
        <>
          <button className="button button-ghost" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button button-primary" type="submit" form="project-form" disabled={saving}>
            {saving ? "Creating…" : "Create project"}
          </button>
        </>
      }
    >
      <form className="form-stack" id="project-form" onSubmit={(event) => void save(event)}>
        <InlineError message={error} />
        <div className="form-grid two">
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label className="field">
            <span>Kind</span>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="project">Project</option>
              <option value="book">Book</option>
              <option value="research">Research</option>
              <option value="application">Application work</option>
              <option value="supporting">Supporting</option>
            </select>
          </label>
        </div>
        <label className="field">
          <span>Description</span>
          <textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="field">
          <span>Primary repository path (optional)</span>
          <input
            value={repositoryPath}
            onChange={(event) => setRepositoryPath(event.target.value)}
            placeholder="C:\Projects\example"
          />
          <small>The directory must already exist. Adding it does not modify the repository.</small>
        </label>
        {kind === "book" ? (
          <label className="field">
            <span>Book title (optional)</span>
            <input
              value={bookTitle}
              onChange={(event) => setBookTitle(event.target.value)}
              placeholder="Defaults to the project name"
            />
          </label>
        ) : null}
        <div className="form-grid two">
          <label className="field">
            <span>Current milestone</span>
            <input value={milestone} onChange={(event) => setMilestone(event.target.value)} />
          </label>
          <label className="field">
            <span>Next action</span>
            <input value={nextAction} onChange={(event) => setNextAction(event.target.value)} />
          </label>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={pinned} onChange={(event) => setPinned(event.target.checked)} />
          Pin this project
        </label>
      </form>
    </Modal>
  );
}

export function ProjectsPage() {
  const projects = useApi<Project[]>("/api/projects");
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("all");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const list = useMemo(() => {
    const source = projects.data ?? [];
    return source
      .filter((project) => (pinnedOnly ? project.pinned : true))
      .filter((project) => (kind === "all" ? true : project.kind === kind))
      .filter((project) => {
        if (!search.trim()) return true;
        const needle = search.toLocaleLowerCase();
        return (
          project.name.toLocaleLowerCase().includes(needle) ||
          project.description.toLocaleLowerCase().includes(needle) ||
          project.repositories.some((repository) => repository.name.toLocaleLowerCase().includes(needle))
        );
      })
      .sort((a, b) => a.priority - b.priority || a.display_order - b.display_order);
  }, [projects.data, pinnedOnly, kind, search]);

  async function togglePin(project: Project) {
    setBusyId(project.id);
    try {
      await api.patch(`/api/projects/${project.id}`, { pinned: !project.pinned });
      toast.push("success", project.pinned ? "Project unpinned" : "Project pinned");
      projects.reload();
    } catch (caught) {
      toast.push("error", "Could not update project", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  async function setFocus(project: Project) {
    setBusyId(project.id);
    try {
      await api.post(`/api/projects/${project.id}/focus`);
      toast.push("success", `Focus set to ${project.name}`);
      projects.reload();
    } catch (caught) {
      toast.push("error", "Could not set focus", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  async function move(project: Project, direction: -1 | 1) {
    const ordered = [...(projects.data ?? [])].sort((a, b) => a.priority - b.priority);
    const index = ordered.findIndex((item) => item.id === project.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setBusyId(project.id);
    try {
      await api.post("/api/projects/reorder", { ids: ordered.map((item) => item.id) });
      toast.push("success", "Priority order saved");
      projects.reload();
    } catch (caught) {
      toast.push("error", "Could not reorder projects", errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Bodies of work, not executables. Applications support projects; they do not replace them."
        actions={
          <button className="button button-primary" onClick={() => setAddOpen(true)}>
            <Plus size={15} /> Add project
          </button>
        }
      />

      <div className="toolbar">
        <label className="search-field">
          <Search size={15} aria-hidden="true" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search projects or repositories"
            aria-label="Search projects"
          />
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by kind</span>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="all">All kinds</option>
            <option value="book">Books</option>
            <option value="project">Projects</option>
            <option value="research">Research</option>
            <option value="application">Application work</option>
            <option value="supporting">Supporting</option>
          </select>
        </label>
        <label className="checkbox inline-checkbox">
          <input
            type="checkbox"
            checked={pinnedOnly}
            onChange={(event) => setPinnedOnly(event.target.checked)}
          />
          Pinned only
        </label>
        <span className="toolbar-count">{list.length} projects</span>
      </div>

      {projects.loading && !projects.data ? <LoadingBlock label="Loading projects" /> : null}
      {projects.error ? <ErrorState message={projects.error.message} onRetry={projects.reload} /> : null}

      {projects.data && list.length === 0 ? (
        <EmptyState
          title="No projects match"
          description="Adjust the filters or create a project to begin."
          icon={<FolderKanban size={20} />}
          action={
            <button className="button button-secondary button-small" onClick={() => setAddOpen(true)}>
              Add project
            </button>
          }
        />
      ) : null}

      <div className="project-list">
        {list.map((project) => (
          <article className={`project-row ${project.pinned ? "is-pinned" : ""}`} key={project.id}>
            <div className="project-priority" aria-label={`Priority ${project.priority}`}>
              <span>{String(project.priority).padStart(2, "0")}</span>
              <div className="reorder-controls">
                <button
                  className="icon-button"
                  aria-label={`Move ${project.name} up`}
                  disabled={busyId === project.id}
                  onClick={() => void move(project, -1)}
                >
                  <ArrowUp size={14} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`Move ${project.name} down`}
                  disabled={busyId === project.id}
                  onClick={() => void move(project, 1)}
                >
                  <ArrowDown size={14} />
                </button>
              </div>
            </div>
            <div className="project-main">
              <div className="project-head">
                <div>
                  <div className="project-title-row">
                    <Link to={`/projects/${project.id}`} className="project-title">
                      {project.name}
                    </Link>
                    <Tag tone={project.kind === "book" ? "accent" : "default"}>
                      {projectLabel(project.kind)}
                    </Tag>
                    <SimpleStatusBadge state={project.status} />
                    {project.pinned ? <Pin size={13} className="pin-icon" aria-label="Pinned" /> : null}
                  </div>
                  <p className="project-description">{project.description}</p>
                </div>
                <div className="project-row-actions">
                  <button
                    className="button button-ghost button-small"
                    onClick={() => void setFocus(project)}
                    disabled={busyId === project.id}
                  >
                    <Crosshair size={14} /> Set focus
                  </button>
                  <button
                    className="icon-button"
                    onClick={() => void togglePin(project)}
                    aria-label={project.pinned ? `Unpin ${project.name}` : `Pin ${project.name}`}
                    disabled={busyId === project.id}
                  >
                    {project.pinned ? <PinOff size={15} /> : <Pin size={15} />}
                  </button>
                  <Link className="button button-secondary button-small" to={`/projects/${project.id}`}>
                    Open
                  </Link>
                </div>
              </div>
              <div className="project-facts">
                <span>{project.current_milestone || "No milestone recorded"}</span>
                <span>Updated {timeAgo(project.last_activity_at)}</span>
                <span>{project.open_task_count} open tasks</span>
                <span>{project.pending_recommendation_count} pending reviews</span>
              </div>
              <div className="project-repos">
                {project.repositories.length ? (
                  project.repositories.map((repository) => (
                    <span className="repo-chip" key={repository.id}>
                      {repository.role ? <span className="repo-role">{repository.role}</span> : null}
                      {repository.name}
                      {repository.branch ? <span className="repo-branch">{repository.branch}</span> : null}
                    </span>
                  ))
                ) : (
                  <span className="muted small">No repository associated</span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {addOpen ? (
        <AddProjectForm onClose={() => setAddOpen(false)} onSaved={projects.reload} />
      ) : null}
    </div>
  );
}
