import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  CheckCircle2,
  PlugZap,
  RefreshCw,
  Settings2,
  ShieldAlert,
  Telescope,
  BriefcaseBusiness,
  ShieldCheck,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  PathText,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import { timeAgo, titleCase } from "../lib/format";
import type { Integration } from "../types/api";

const icons = {
  next: Telescope,
  work: BriefcaseBusiness,
  cocoder: ShieldCheck,
};

const secretMarkers = ["secret", "password", "token", "api_key", "apikey"];

function visibleConfigEntries(config: Record<string, unknown>) {
  return Object.entries(config).filter(
    ([key]) => !secretMarkers.some((marker) => key.toLowerCase().includes(marker)),
  );
}

function IntegrationCard({ integration, onChanged }: { integration: Integration; onChanged: () => void }) {
  const toast = useToast();
  const Icon = icons[integration.application_id as keyof typeof icons] ?? PlugZap;
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<Record<string, string>>({});

  useEffect(() => {
    const current = integration.config || {};
    const next: Record<string, string> = {};
    for (const key of ["dsn_env", "sqlite_path", "executable", "working_directory", "artifact_dir"]) {
      next[key] = String(current[key] ?? "");
    }
    next.limit = String(current.limit ?? (integration.application_id === "next" ? 200 : 300));
    next.timeout_seconds = String(current.timeout_seconds ?? (integration.application_id === "work" ? 90 : 180));
    next.arguments = Array.isArray(current.arguments) ? (current.arguments as string[]).join("\n") : "";
    next.env_names = Array.isArray(current.env_names) ? (current.env_names as string[]).join(", ") : "";
    setConfig(next);
  }, [integration]);

  async function test() {
    setBusy("test");
    setError(null);
    try {
      const result = await api.post<Integration>(`/api/integrations/${integration.application_id}/test`);
      toast.push(result.available ? "success" : "error", `${integration.name}: ${result.available ? "connection successful" : "unavailable"}`);
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Connection test failed", message);
    } finally {
      setBusy(null);
    }
  }

  async function refresh() {
    setBusy("refresh");
    setError(null);
    try {
      const result = await api.post<Integration>(`/api/integrations/${integration.application_id}/refresh`);
      toast.push(result.available ? "success" : "info", `${integration.name} read model refreshed`);
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Refresh failed", message);
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy("save");
    setError(null);
    try {
      const payload: Record<string, unknown> = {};
      if (integration.application_id === "next") {
        payload.dsn_env = config.dsn_env || "NEXT_DSN";
        payload.sqlite_path = config.sqlite_path;
        payload.limit = Number(config.limit);
      } else if (integration.application_id === "work") {
        payload.executable = config.executable;
        payload.working_directory = config.working_directory;
        payload.arguments = config.arguments.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
        payload.env_names = config.env_names.split(",").map((item) => item.trim()).filter(Boolean);
        payload.timeout_seconds = Number(config.timeout_seconds);
        payload.limit = Number(config.limit);
      } else {
        payload.executable = config.executable;
        payload.artifact_dir = config.artifact_dir;
        payload.timeout_seconds = Number(config.timeout_seconds);
      }
      await api.patch(`/api/integrations/${integration.application_id}`, {
        adapter_config: payload,
        adapter_enabled: true,
      });
      toast.push("success", `${integration.name} configuration saved`);
      setEditing(false);
      onChanged();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Configuration rejected", message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="integration-card">
      <header className="integration-card-head">
        <div className="integration-card-identity">
          <span className="integration-logo"><Icon size={21} /></span>
          <div>
            <span className="eyebrow">Application engine</span>
            <h2>{integration.name}</h2>
          </div>
        </div>
        <SimpleStatusBadge
          state={integration.available ? "running" : integration.enabled ? "unavailable" : "stopped"}
          label={integration.available ? "Connected" : integration.enabled ? "Unavailable" : "Disabled"}
        />
      </header>
      <p className="integration-detail">{integration.detail}</p>
      {integration.error ? (
        <div className="integration-diagnostic"><ShieldAlert size={15} /> {integration.error}</div>
      ) : null}
      <div className="integration-meta-grid">
        <div><span>Mode</span><strong>{integration.mode}</strong></div>
        <div><span>Protocol</span><strong>{integration.protocol_version}</strong></div>
        <div><span>Last sync</span><strong>{integration.last_checked_at ? timeAgo(integration.last_checked_at) : "Never"}</strong></div>
        <div><span>Records</span><strong>{Object.values(integration.resource_counts).reduce((sum, value) => sum + value, 0)}</strong></div>
      </div>
      <div className="tag-row integration-capabilities">
        {integration.capabilities.map((capability) => (
          <Tag key={capability}>{capability}</Tag>
        ))}
      </div>
      {integration.repository_path ? <PathText>{integration.repository_path}</PathText> : null}

      <div className="integration-config-summary">
        {visibleConfigEntries(integration.config || {}).map(([key, value]) => (
          <span key={key}>
            <strong>{key}</strong> {Array.isArray(value) ? value.join(" ") : String(value)}
          </span>
        ))}
        {!visibleConfigEntries(integration.config || {}).length ? (
          <span>Using adapter defaults</span>
        ) : null}
      </div>

      {editing ? (
        <div className="integration-edit form-stack">
          <InlineError message={error} />
          {integration.application_id === "next" ? (
            <>
              <label className="field">
                <span>DSN environment variable</span>
                <input
                  value={config.dsn_env ?? ""}
                  onChange={(event) => setConfig({ ...config, dsn_env: event.target.value })}
                />
              </label>
              <label className="field">
                <span>SQLite fallback path</span>
                <input
                  value={config.sqlite_path ?? ""}
                  onChange={(event) => setConfig({ ...config, sqlite_path: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Opportunity limit</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={config.limit ?? "200"}
                  onChange={(event) => setConfig({ ...config, limit: event.target.value })}
                />
              </label>
            </>
          ) : null}
          {integration.application_id === "work" ? (
            <>
              <label className="field">
                <span>Work executable</span>
                <input
                  value={config.executable ?? ""}
                  onChange={(event) => setConfig({ ...config, executable: event.target.value })}
                  placeholder="Default: <work repo>\.venv\Scripts\work.exe"
                />
              </label>
              <label className="field">
                <span>Working directory</span>
                <input
                  value={config.working_directory ?? ""}
                  onChange={(event) => setConfig({ ...config, working_directory: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Arguments (one per line)</span>
                <textarea
                  rows={3}
                  value={config.arguments ?? ""}
                  onChange={(event) => setConfig({ ...config, arguments: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Allowed environment variable names</span>
                <input
                  value={config.env_names ?? ""}
                  onChange={(event) => setConfig({ ...config, env_names: event.target.value })}
                />
              </label>
              <div className="form-grid two">
                <label className="field">
                  <span>Timeout (seconds)</span>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={config.timeout_seconds ?? "90"}
                    onChange={(event) => setConfig({ ...config, timeout_seconds: event.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Limit</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={config.limit ?? "300"}
                    onChange={(event) => setConfig({ ...config, limit: event.target.value })}
                  />
                </label>
              </div>
            </>
          ) : null}
          {integration.application_id === "cocoder" ? (
            <>
              <label className="field">
                <span>CoCoder executable</span>
                <input
                  value={config.executable ?? ""}
                  onChange={(event) => setConfig({ ...config, executable: event.target.value })}
                  placeholder="Default: <cocoder repo>\venv\Scripts\cocoder.exe"
                />
              </label>
              <label className="field">
                <span>Artifact directory (relative to Mission Control data)</span>
                <input
                  value={config.artifact_dir ?? ""}
                  onChange={(event) => setConfig({ ...config, artifact_dir: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Review timeout (seconds)</span>
                <input
                  type="number"
                  min={10}
                  max={300}
                  value={config.timeout_seconds ?? "180"}
                  onChange={(event) => setConfig({ ...config, timeout_seconds: event.target.value })}
                />
              </label>
            </>
          ) : null}
          <div className="button-row">
            <button className="button button-primary button-small" onClick={() => void save()} disabled={busy !== null}>
              Save configuration
            </button>
            <button className="button button-ghost button-small" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <div className="integration-actions">
        <button className="button button-secondary button-small" onClick={() => void test()} disabled={busy !== null}>
          <Activity size={14} /> Test connection
        </button>
        <button className="button button-secondary button-small" onClick={() => void refresh()} disabled={busy !== null}>
          <RefreshCw size={14} /> Refresh read model
        </button>
        <button className="button button-ghost button-small" onClick={() => setEditing((value) => !value)}>
          <Settings2 size={14} /> Configure
        </button>
        {["next", "work", "cocoder"].includes(integration.application_id) ? (
          <Link className="button button-primary button-small" to={`/${integration.application_id}`}>
            Open workspace
          </Link>
        ) : null}
      </div>
      <div className="integration-action-list">
        {integration.actions.map((action) => (
          <div className="integration-action-row" key={action.id}>
            <CheckCircle2 size={14} className={action.enabled ? "text-good" : "text-muted"} />
            <div>
              <strong>{action.title}</strong>
              <span>
                {titleCase(action.risk)} · {action.side_effect.replace(/_/g, " ")}
                {action.approval_required ? " · approval required" : ""}
              </span>
              {!action.enabled && action.unavailable_reason ? <em>{action.unavailable_reason}</em> : null}
            </div>
          </div>
        ))}
        {!integration.actions.length ? (
          <span className="muted small">No registered operations. Read-only integration.</span>
        ) : null}
      </div>
    </article>
  );
}

export function IntegrationsPage() {
  const integrations = useApi<Integration[]>("/api/integrations", { pollMs: 45000 });
  return (
    <div className="page">
      <PageHeader
        eyebrow="Integration foundation"
        title="Integrations"
        description="Versioned adapter contracts over independent engines. Reads are read-only; operations are registered and confirmed."
      />
      {integrations.loading && !integrations.data ? <LoadingBlock label="Loading integrations" /> : null}
      {integrations.error ? <ErrorState message={integrations.error.message} onRetry={integrations.reload} /> : null}
      {integrations.data && integrations.data.length === 0 ? (
        <EmptyState
          title="No integrations registered"
          description="Register Next, Work or CoCoder in Applications with an adapter."
          icon={<PlugZap size={20} />}
        />
      ) : null}
      <div className="integration-grid">
        {integrations.data?.map((integration) => (
          <IntegrationCard key={integration.application_id} integration={integration} onChanged={integrations.reload} />
        ))}
      </div>
      <div className="integration-boundary-note">
        <ShieldAlert size={16} />
        <p>
          Next is read through a SELECT-only PostgreSQL session because it does not expose a stable
          JSON export. Work is read through its documented <code>opportunities --json</code> CLI.
          CoCoder reads review artifacts and can run only the registered bounded review action.
          Mission Control does not write source databases, repositories or decisions in this release.
          Selections and decisions are stored locally with <code>local_only</code> provenance.
        </p>
      </div>
    </div>
  );
}
