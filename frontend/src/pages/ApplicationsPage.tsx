import { useMemo, useState } from "react";
import { AppWindow, Plus, Search } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { ApplicationCard } from "../features/applications/ApplicationCard";
import { ApplicationForm } from "../features/applications/ApplicationForm";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Section,
  SimpleStatusBadge,
} from "../components/ui";
import { formatDateTime, timeAgo, titleCase } from "../lib/format";
import type { Application, ProcessInstance } from "../types/api";

export function ApplicationsPage() {
  const applications = useApi<Application[]>("/api/applications?include_archived=false", {
    pollMs: 45000,
  });
  const processes = useApi<ProcessInstance[]>("/api/processes?limit=12", { pollMs: 45000 });
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [editing, setEditing] = useState<Application | "new" | null>(null);
  const [stopping, setStopping] = useState<string | null>(null);

  const categories = useMemo(
    () => Array.from(new Set((applications.data ?? []).map((app) => app.category))).sort(),
    [applications.data],
  );
  const list = useMemo(() => {
    return (applications.data ?? [])
      .filter((app) => (pinnedOnly ? app.pinned : true))
      .filter((app) => (category === "all" ? true : app.category === category))
      .filter((app) => {
        if (!search.trim()) return true;
        const needle = search.toLocaleLowerCase();
        return (
          app.name.toLocaleLowerCase().includes(needle) ||
          app.description.toLocaleLowerCase().includes(needle) ||
          app.tags.some((tag) => tag.toLocaleLowerCase().includes(needle))
        );
      })
      .sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name));
  }, [applications.data, pinnedOnly, category, search]);

  async function stopProcess(process: ProcessInstance) {
    setStopping(process.id);
    try {
      await api.post(`/api/processes/${process.id}/stop`);
      toast.push("success", "Process stopped");
      processes.reload();
      applications.reload();
    } catch (caught) {
      toast.push("error", "Could not stop process", errorMessage(caught));
    } finally {
      setStopping(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Application registry"
        title="Applications"
        description="Configured local tools. Mission Control launches only stored definitions and never accepts a shell command from the browser."
        actions={
          <button className="button button-primary" onClick={() => setEditing("new")}>
            <Plus size={15} /> Add application
          </button>
        }
      />

      <div className="toolbar">
        <label className="search-field">
          <Search size={15} aria-hidden="true" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search applications"
            aria-label="Search applications"
          />
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by category</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All categories</option>
            {categories.map((item) => (
              <option value={item} key={item}>
                {titleCase(item)}
              </option>
            ))}
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
        <span className="toolbar-count">{list.length} applications</span>
      </div>

      {applications.loading && !applications.data ? <LoadingBlock label="Loading applications" /> : null}
      {applications.error ? (
        <ErrorState message={applications.error.message} onRetry={applications.reload} />
      ) : null}
      {applications.data && list.length === 0 ? (
        <EmptyState
          title="No applications match"
          description="Adjust the filters or register an application without changing code."
          icon={<AppWindow size={20} />}
          action={
            <button className="button button-secondary button-small" onClick={() => setEditing("new")}>
              Register application
            </button>
          }
        />
      ) : null}

      <div className="card-grid two app-grid">
        {list.map((app) => (
          <ApplicationCard
            key={app.id}
            app={app}
            onChanged={() => {
              applications.reload();
              processes.reload();
            }}
            onConfigure={(selected) => setEditing(selected)}
          />
        ))}
      </div>

      <Section
        title="Managed process history"
        description="Only processes launched by Mission Control can be stopped here. Externally detected listeners are never terminated."
        actions={
          <button className="button button-ghost button-small" onClick={() => processes.reload()}>
            Refresh
          </button>
        }
      >
        {processes.error ? <ErrorState message={processes.error.message} onRetry={processes.reload} /> : null}
        {processes.data && processes.data.length === 0 ? (
          <EmptyState title="No managed processes" description="Launch a verified application to create a process record." />
        ) : null}
        {processes.data && processes.data.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Application</th>
                  <th>Status</th>
                  <th>PID</th>
                  <th>Started</th>
                  <th>Command</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {processes.data.map((process) => (
                  <tr key={process.id}>
                    <td>
                      <strong>{process.application_name ?? process.application_id}</strong>
                      {process.reattached ? <span className="table-note">reattached</span> : null}
                    </td>
                    <td>
                      <SimpleStatusBadge
                        state={
                          process.status === "running"
                            ? "running"
                            : process.status === "failed"
                              ? "launch_failed"
                              : "stopped"
                        }
                        label={titleCase(process.status)}
                      />
                    </td>
                    <td>{process.pid ?? "—"}</td>
                    <td title={formatDateTime(process.started_at)}>{timeAgo(process.started_at)}</td>
                    <td>
                      <code className="table-command">{process.command_preview ?? "—"}</code>
                    </td>
                    <td className="table-actions">
                      {process.status === "running" ? (
                        <button
                          className="button button-danger button-small"
                          onClick={() => void stopProcess(process)}
                          disabled={stopping === process.id}
                        >
                          Stop
                        </button>
                      ) : (
                        <span className="muted small">{process.error ?? "—"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Section>

      {editing ? (
        <ApplicationForm
          app={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
          onSaved={applications.reload}
        />
      ) : null}
    </div>
  );
}
