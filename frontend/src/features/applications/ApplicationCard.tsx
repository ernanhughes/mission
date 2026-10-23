import { useState } from "react";
import {
  BookOpen,
  ExternalLink,
  FolderOpen,
  Play,
  RotateCw,
  ScrollText,
  Settings2,
  Square,
  X,
} from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import { Modal } from "../../components/Modal";
import {
  ActionButton,
  DisabledReasons,
  InlineError,
  PathText,
  StatusBadge,
} from "../../components/ui";
import { formatDateTime, timeAgo, titleCase } from "../../lib/format";
import type { Application, LogData } from "../../types/api";

export function ApplicationCard({
  app,
  onChanged,
  onConfigure,
  compact = false,
}: {
  app: Application;
  onChanged: () => void;
  onConfigure?: (app: Application) => void;
  compact?: boolean;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logsOpen, setLogsOpen] = useState(false);
  const logs = useApi<LogData>(logsOpen ? `/api/applications/${app.id}/logs?lines=300` : null);

  async function run(action: () => Promise<unknown>, success: string, reloadDelay = 0) {
    setBusy(true);
    setError(null);
    try {
      await action();
      toast.push("success", success);
      if (reloadDelay) window.setTimeout(onChanged, reloadDelay);
      else onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", `${app.name}: action failed`, message);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  function launch() {
    if (app.control_policy.confirmation_required) {
      const confirmed = window.confirm(
        `${app.name} is configured to require confirmation. Launch it now?`,
      );
      if (!confirmed) return;
    }
    void run(
      () => api.post(`/api/applications/${app.id}/launch`, { confirm: true }),
      `${app.name} launch requested`,
      900,
    );
  }

  async function openUrl() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ url: string; opened_externally?: boolean }>(
        `/api/applications/${app.id}/open-url`,
      );
      if (!result.opened_externally) {
        window.open(result.url, "_blank", "noopener,noreferrer");
      }
      toast.push("info", "Opened web interface", result.url);
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not open URL", message);
    } finally {
      setBusy(false);
    }
  }

  const failure =
    app.status.state === "launch_failed" && app.last_failure_detail
      ? app.last_failure_detail
      : null;

  return (
    <article className={`app-card ${compact ? "app-card-compact" : ""}`}>
      <header className="app-card-head">
        <div className="app-identity">
          <span className="app-icon" aria-hidden="true">
            {app.icon || app.name.slice(0, 2)}
          </span>
          <div>
            <h3>{app.name}</h3>
            <span className="app-category">{titleCase(app.category)}</span>
          </div>
        </div>
        <StatusBadge status={app.status} />
      </header>

      {!compact ? <p className="app-description">{app.description}</p> : null}
      <p className="status-detail">{app.status.detail}</p>

      {app.repository_path ? (
        <div className="app-path">
          <PathText>{app.repository_path}</PathText>
        </div>
      ) : null}

      <InlineError message={error} />
      {failure ? (
        <div className="failure-note">
          <strong>Last launch failed</strong>
          <span>{failure}</span>
          {app.last_launch_failure_at ? <small>{formatDateTime(app.last_launch_failure_at)}</small> : null}
        </div>
      ) : null}

      <div className="app-actions">
        <ActionButton
          action={app.actions.launch}
          onClick={launch}
          variant="primary"
          small
          icon={<Play size={14} />}
        >
          Launch
        </ActionButton>
        <ActionButton
          action={app.actions.stop}
          onClick={() =>
            void run(() => api.post(`/api/applications/${app.id}/stop`), `${app.name} stopped`)
          }
          small
          icon={<Square size={13} />}
        >
          Stop
        </ActionButton>
        <ActionButton
          action={app.actions.restart}
          onClick={() =>
            void run(
              () => api.post(`/api/applications/${app.id}/restart`, { confirm: true }),
              `${app.name} restart requested`,
              900,
            )
          }
          small
          icon={<RotateCw size={13} />}
        >
          Restart
        </ActionButton>
        <ActionButton
          action={app.actions.open_repository}
          onClick={() =>
            void run(
              () => api.post(`/api/applications/${app.id}/open-repository`),
              "Repository opened",
            )
          }
          small
          icon={<FolderOpen size={14} />}
        >
          Repository
        </ActionButton>
        <ActionButton
          action={app.actions.open_documentation}
          onClick={() =>
            void run(
              () => api.post(`/api/applications/${app.id}/open-documentation`),
              "Documentation opened",
            )
          }
          small
          icon={<BookOpen size={14} />}
        >
          Docs
        </ActionButton>
        <ActionButton
          action={app.actions.open_url}
          onClick={() => void openUrl()}
          small
          icon={<ExternalLink size={14} />}
        >
          Open URL
        </ActionButton>
        <ActionButton
          action={app.actions.logs}
          onClick={() => setLogsOpen(true)}
          small
          icon={<ScrollText size={14} />}
        >
          Logs
        </ActionButton>
        {onConfigure ? (
          <button className="button button-ghost button-small" onClick={() => onConfigure(app)}>
            <Settings2 size={14} /> Configure
          </button>
        ) : null}
        {busy ? <span className="working-label">Working…</span> : null}
      </div>

      {!compact ? (
        <div className="app-card-foot">
          <span>Last successful launch: {timeAgo(app.last_launch_success_at)}</span>
          {app.tags.length ? (
            <span className="tag-row">
              {app.tags.slice(0, 4).map((tag) => (
                <span className="tag" key={tag}>
                  {tag}
                </span>
              ))}
            </span>
          ) : null}
        </div>
      ) : null}

      <DisabledReasons
        actions={[
          ["Launch", app.actions.launch],
          ["Stop", app.actions.stop],
          ["Restart", app.actions.restart],
          ["Repository", app.actions.open_repository],
          ["Documentation", app.actions.open_documentation],
          ["URL", app.actions.open_url],
          ["Logs", app.actions.logs],
        ]}
      />

      {logsOpen ? (
        <Modal
          title={`${app.name} logs`}
          eyebrow="Managed process"
          onClose={() => setLogsOpen(false)}
          wide
        >
          {logs.loading ? <p>Loading logs…</p> : null}
          {logs.error ? <InlineError message={logs.error.message} /> : null}
          {logs.data ? (
            <>
              <div className="log-meta">
                <span>{logs.data.path ?? "No log path"}</span>
                {logs.data.truncated ? <span>Showing latest output only</span> : null}
              </div>
              <pre className="log-view">{logs.data.lines.join("\n") || "No output recorded."}</pre>
              <p className="muted small">
                Secrets are redacted when read. Environment values are never recorded in the log header.
              </p>
            </>
          ) : null}
          <div className="modal-actions">
            <button className="button button-secondary" onClick={() => logs.reload()}>
              Refresh
            </button>
            <button className="button button-ghost" onClick={() => setLogsOpen(false)}>
              <X size={14} /> Close
            </button>
          </div>
        </Modal>
      ) : null}
    </article>
  );
}
