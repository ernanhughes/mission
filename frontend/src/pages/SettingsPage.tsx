import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  Database,
  FolderPlus,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
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
  Section,
  SimpleStatusBadge,
  Tag,
} from "../components/ui";
import { classificationLabel, formatDateTime, timeAgo, titleCase } from "../lib/format";
import type {
  Application,
  Candidate,
  DiscoveryScan,
  Settings,
} from "../types/api";

export function SettingsPage() {
  const settings = useApi<Settings>("/api/settings");
  const scan = useApi<DiscoveryScan>("/api/discovery/scan", {
    pollMs: 2500,
  });
  const candidates = useApi<Candidate[]>("/api/discovery/candidates?limit=250", {
    pollMs: scan.data?.running ? 4000 : 0,
  });
  const applications = useApi<Application[]>("/api/applications");
  const toast = useToast();

  const [exclusions, setExclusions] = useState("");
  const [maxDepth, setMaxDepth] = useState(1);
  const [maxCandidates, setMaxCandidates] = useState(500);
  const [scanTimeout, setScanTimeout] = useState(120);
  const [gitTimeout, setGitTimeout] = useState(5);
  const [editorCommand, setEditorCommand] = useState("");
  const [editorArgs, setEditorArgs] = useState("");
  const [appendPath, setAppendPath] = useState(true);
  const [browserMode, setBrowserMode] = useState("new_tab");
  const [maxManaged, setMaxManaged] = useState(5);
  const [healthInterval, setHealthInterval] = useState(30);
  const [logTail, setLogTail] = useState(200);
  const [adapterInterval, setAdapterInterval] = useState(10);
  const [adapterTimeout, setAdapterTimeout] = useState(5);
  const [activityDays, setActivityDays] = useState(365);
  const [briefingDays, setBriefingDays] = useState(90);
  const [logDays, setLogDays] = useState(30);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiConsent, setAiConsent] = useState(false);
  const [aiBaseUrl, setAiBaseUrl] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiKeyEnv, setAiKeyEnv] = useState("OPENAI_API_KEY");
  const [aiTimeout, setAiTimeout] = useState(45);
  const [profileEnabled, setProfileEnabled] = useState(false);
  const [profileApplications, setProfileApplications] = useState<string[]>([]);
  const [newRoot, setNewRoot] = useState("");
  const [candidateFilter, setCandidateFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rootBusy, setRootBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!settings.data) return;
    const data = settings.data;
    setExclusions(data.discovery.exclusions.join("\n"));
    setMaxDepth(data.discovery.max_depth);
    setMaxCandidates(data.discovery.max_candidates);
    setScanTimeout(data.discovery.timeout_seconds);
    setGitTimeout(data.discovery.git_timeout_seconds);
    setEditorCommand(data.editor.command);
    setEditorArgs(data.editor.arguments.join("\n"));
    setAppendPath(data.editor.append_path);
    setBrowserMode(data.browser.open_mode);
    setMaxManaged(data.processes.max_managed);
    setHealthInterval(data.processes.health_check_interval_seconds);
    setLogTail(data.processes.log_tail_lines);
    setAdapterInterval(data.adapters.refresh_interval_minutes);
    setAdapterTimeout(data.adapters.timeout_seconds);
    setActivityDays(data.retention.activity_days);
    setBriefingDays(data.retention.briefing_days);
    setLogDays(data.retention.log_days);
    setAiEnabled(data.ai.enabled);
    setAiConsent(data.ai.consent);
    setAiBaseUrl(data.ai.base_url);
    setAiModel(data.ai.model);
    setAiKeyEnv(data.ai.api_key_env);
    setAiTimeout(data.ai.timeout_seconds);
    setProfileEnabled(data.startup.profile_enabled);
    setProfileApplications(data.startup.profile_applications);
  }, [settings.data]);

  const filteredCandidates = useMemo(() => {
    if (!candidateFilter.trim()) return candidates.data ?? [];
    const needle = candidateFilter.toLocaleLowerCase();
    return (candidates.data ?? []).filter(
      (candidate) =>
        candidate.name.toLocaleLowerCase().includes(needle) ||
        candidate.classification.toLocaleLowerCase().includes(needle) ||
        candidate.path.toLocaleLowerCase().includes(needle),
    );
  }, [candidates.data, candidateFilter]);

  async function saveSettings() {
    setSaving(true);
    setError(null);
    try {
      await api.patch("/api/settings", {
        discovery: {
          exclusions: exclusions
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean),
          max_depth: maxDepth,
          max_candidates: maxCandidates,
          timeout_seconds: scanTimeout,
          git_timeout_seconds: gitTimeout,
        },
        editor: {
          command: editorCommand,
          arguments: editorArgs
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean),
          append_path: appendPath,
        },
        browser: { open_mode: browserMode },
        processes: {
          max_managed: maxManaged,
          health_check_interval_seconds: healthInterval,
          log_tail_lines: logTail,
        },
        adapters: {
          refresh_interval_minutes: adapterInterval,
          timeout_seconds: adapterTimeout,
        },
        retention: {
          activity_days: activityDays,
          briefing_days: briefingDays,
          log_days: logDays,
        },
        ai: {
          enabled: aiEnabled,
          consent: aiConsent,
          provider: "openai-compatible",
          base_url: aiBaseUrl,
          model: aiModel,
          api_key_env: aiKeyEnv,
          timeout_seconds: aiTimeout,
        },
        startup: {
          profile_enabled: profileEnabled,
          profile_applications: profileApplications,
        },
      });
      toast.push("success", "Settings saved");
      settings.reload();
      applications.reload();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast.push("error", "Could not save settings", message);
    } finally {
      setSaving(false);
    }
  }

  async function addRoot() {
    if (!newRoot.trim()) return;
    setRootBusy("add");
    try {
      await api.post("/api/discovery/roots", { path: newRoot.trim(), enabled: true });
      setNewRoot("");
      toast.push("success", "Discovery root added");
      settings.reload();
    } catch (caught) {
      toast.push("error", "Could not add discovery root", errorMessage(caught));
    } finally {
      setRootBusy(null);
    }
  }

  async function toggleRoot(path: string, enabled: boolean) {
    setRootBusy(path);
    try {
      await api.patch("/api/discovery/roots", { path, enabled });
      settings.reload();
    } catch (caught) {
      toast.push("error", "Could not update root", errorMessage(caught));
    } finally {
      setRootBusy(null);
    }
  }

  async function removeRoot(path: string) {
    if (!window.confirm(`Remove discovery root ${path}? No files are deleted.`)) return;
    setRootBusy(path);
    try {
      await api.delete(`/api/discovery/roots?path=${encodeURIComponent(path)}`);
      toast.push("success", "Discovery root removed", "No files were modified.");
      settings.reload();
    } catch (caught) {
      toast.push("error", "Could not remove root", errorMessage(caught));
    } finally {
      setRootBusy(null);
    }
  }

  async function startScan() {
    try {
      await api.post("/api/discovery/scan");
      toast.push("info", "Discovery scan started", "Read-only and bounded by the configured exclusions.");
      scan.reload();
    } catch (caught) {
      toast.push("error", "Could not start scan", errorMessage(caught));
    }
  }

  async function cancelScan() {
    try {
      await api.post("/api/discovery/scan/cancel");
      toast.push("info", "Cancellation requested");
      scan.reload();
    } catch (caught) {
      toast.push("error", "Could not cancel scan", errorMessage(caught));
    }
  }

  async function refreshRepositories() {
    try {
      const result = await api.post<{ detail: string }>("/api/discovery/refresh-repositories");
      toast.push("success", "Repository metadata refreshed", result.detail);
    } catch (caught) {
      toast.push("error", "Could not refresh repositories", errorMessage(caught));
    }
  }

  async function activateProfile() {
    try {
      const result = await api.post<{ activated: unknown[]; skipped: unknown[] }>("/api/startup/activate");
      toast.push(
        result.activated.length ? "success" : "info",
        `Startup profile activated`,
        `${result.activated.length} launched, ${result.skipped.length} skipped.`,
      );
      applications.reload();
    } catch (caught) {
      toast.push("error", "Could not activate startup profile", errorMessage(caught));
    }
  }

  function toggleProfileApp(appId: string) {
    setProfileApplications((current) =>
      current.includes(appId) ? current.filter((id) => id !== appId) : [...current, appId],
    );
  }

  if (settings.loading && !settings.data) {
    return (
      <div className="page">
        <LoadingBlock label="Loading settings" />
      </div>
    );
  }
  if (settings.error) {
    return (
      <div className="page">
        <ErrorState message={settings.error.message} onRetry={settings.reload} />
      </div>
    );
  }
  if (!settings.data) return null;
  const data = settings.data;
  const scanData = scan.data;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Local configuration. User choices survive restarts and are not overwritten by discovery."
        actions={
          <button className="button button-primary" onClick={() => void saveSettings()} disabled={saving}>
            <Save size={15} /> {saving ? "Saving…" : "Save settings"}
          </button>
        }
      />
      <InlineError message={error} />

      <div className="settings-grid">
        <Section
          title="Discovery"
          description="Read-only, bounded scans. Generated directories stay out of the registry."
          className="settings-section"
        >
          <div className="settings-block">
            <h3>Roots</h3>
            <ul className="root-list">
              {data.discovery_roots.map((root) => (
                <li key={root.path}>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={root.enabled}
                      disabled={rootBusy === root.path}
                      onChange={(event) => void toggleRoot(root.path, event.target.checked)}
                    />
                    <PathText>{root.path}</PathText>
                  </label>
                  <button
                    className="icon-button"
                    onClick={() => void removeRoot(root.path)}
                    aria-label={`Remove ${root.path}`}
                    disabled={rootBusy === root.path}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="inline-form">
              <input
                value={newRoot}
                onChange={(event) => setNewRoot(event.target.value)}
                placeholder="C:\another-root"
                aria-label="New discovery root"
              />
              <button
                className="button button-secondary button-small"
                onClick={() => void addRoot()}
                disabled={!newRoot.trim() || rootBusy === "add"}
              >
                <FolderPlus size={14} /> Add root
              </button>
            </div>
          </div>
          <label className="field">
            <span>Exclusion patterns (one per line, relative globs or directory names)</span>
            <textarea
              className="code-input"
              rows={8}
              value={exclusions}
              onChange={(event) => setExclusions(event.target.value)}
            />
          </label>
          <div className="form-grid four">
            <label className="field">
              <span>Max depth</span>
              <input type="number" min={1} max={3} value={maxDepth} onChange={(event) => setMaxDepth(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>Max candidates</span>
              <input
                type="number"
                min={1}
                max={2000}
                value={maxCandidates}
                onChange={(event) => setMaxCandidates(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Scan timeout (s)</span>
              <input
                type="number"
                min={10}
                max={600}
                value={scanTimeout}
                onChange={(event) => setScanTimeout(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Git timeout (s)</span>
              <input
                type="number"
                min={1}
                max={30}
                value={gitTimeout}
                onChange={(event) => setGitTimeout(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="settings-actions">
            <button className="button button-primary button-small" onClick={() => void startScan()} disabled={scanData?.running}>
              <Play size={14} /> {scanData?.running ? "Scan running…" : "Run discovery"}
            </button>
            {scanData?.running ? (
              <button className="button button-secondary button-small" onClick={() => void cancelScan()}>
                <Ban size={14} /> Cancel
              </button>
            ) : null}
            <button className="button button-ghost button-small" onClick={() => void refreshRepositories()}>
              <RefreshCw size={14} /> Refresh Git metadata
            </button>
          </div>
          {scanData ? (
            <div className="scan-summary">
              <div className="inline-meta">
                <SimpleStatusBadge
                  state={scanData.running ? "running" : scanData.status === "complete" ? "stopped" : "stale"}
                  label={scanData.running ? "Scanning" : titleCase(scanData.status)}
                />
                {scanData.scanned_directories ? <span>{scanData.scanned_directories} directories</span> : null}
                {scanData.candidate_count != null ? <span>{scanData.candidate_count} candidates</span> : null}
                {scanData.excluded_count != null ? <span>{scanData.excluded_count} excluded</span> : null}
                {scanData.elapsed_seconds ? <span>{scanData.elapsed_seconds}s</span> : null}
              </div>
              {scanData.counts && Object.keys(scanData.counts).length ? (
                <div className="count-chips">
                  {Object.entries(scanData.counts).map(([key, value]) => (
                    <span className="count-chip" key={key}>
                      {classificationLabel(key)} <strong>{value}</strong>
                    </span>
                  ))}
                </div>
              ) : null}
              {scanData.errors.length ? (
                <details className="scan-errors">
                  <summary>
                    <AlertTriangle size={13} /> {scanData.errors.length} inaccessible or bounded paths
                  </summary>
                  <ul>
                    {scanData.errors.map((item) => (
                      <li key={`${item.path}-${item.error}`}>
                        <code>{item.path}</code> {item.error}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
              {scanData.truncated ? (
                <p className="warn-text small">The scan reached its configured bound. Increase limits deliberately.</p>
              ) : null}
            </div>
          ) : null}
        </Section>

        <Section
          title="Editor and browser"
          description="Mission Control never assumes an editor path. Repository actions are disabled until one is configured."
          className="settings-section"
        >
          <div className="form-grid two">
            <label className="field">
              <span>Editor command</span>
              <input
                value={editorCommand}
                onChange={(event) => setEditorCommand(event.target.value)}
                placeholder="C:\...\Microsoft VS Code\Code.exe"
              />
              <small>Native executable or a command resolvable on PATH. Shell scripts are rejected.</small>
            </label>
            <label className="field">
              <span>Browser behaviour</span>
              <select value={browserMode} onChange={(event) => setBrowserMode(event.target.value)}>
                <option value="new_tab">Open a new tab in this browser</option>
                <option value="external">Use the system browser</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>Editor arguments (one per line)</span>
            <textarea
              className="code-input"
              rows={2}
              value={editorArgs}
              onChange={(event) => setEditorArgs(event.target.value)}
            />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={appendPath} onChange={(event) => setAppendPath(event.target.checked)} />
            Append the repository path to the editor command
          </label>
        </Section>

        <Section title="Process safety" description="Limits apply to Mission Control-owned processes only." className="settings-section">
          <div className="form-grid three">
            <label className="field">
              <span>Max managed processes</span>
              <input
                type="number"
                min={1}
                max={20}
                value={maxManaged}
                onChange={(event) => setMaxManaged(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Health interval (s)</span>
              <input
                type="number"
                min={10}
                max={3600}
                value={healthInterval}
                onChange={(event) => setHealthInterval(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Log tail lines</span>
              <input
                type="number"
                min={20}
                max={2000}
                value={logTail}
                onChange={(event) => setLogTail(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="form-grid two">
            <label className="field">
              <span>Adapter refresh interval (min)</span>
              <input
                type="number"
                min={1}
                max={1440}
                value={adapterInterval}
                onChange={(event) => setAdapterInterval(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Adapter timeout (s)</span>
              <input
                type="number"
                min={1}
                max={60}
                value={adapterTimeout}
                onChange={(event) => setAdapterTimeout(Number(event.target.value))}
              />
            </label>
          </div>
          <p className="muted small">
            Servers left running when Mission Control closes can be reattached after restart. Stop is
            only offered for processes Mission Control owns.
          </p>
        </Section>

        <Section
          title="AI advisory"
          description="Optional. The dashboard and briefing work without any provider."
          className="settings-section"
        >
          <div className="ai-status">
            <SimpleStatusBadge
              state={data.ai_configured ? "running" : "stopped"}
              label={data.ai_configured ? "Configured" : "Disabled"}
            />
            <span className={data.ai_key_present ? "muted small" : "warn-text small"}>
              {data.ai_key_present
                ? "API key environment variable is present."
                : "No API key is present in the configured environment variable. A local endpoint may not need one."}
            </span>
          </div>
          <div className="form-grid two">
            <label className="checkbox">
              <input type="checkbox" checked={aiEnabled} onChange={(event) => setAiEnabled(event.target.checked)} />
              Enable AI advisory features
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={aiConsent} onChange={(event) => setAiConsent(event.target.checked)} />
              I consent to explicit AI generation requests
            </label>
          </div>
          <div className="form-grid two">
            <label className="field">
              <span>Provider</span>
              <input value="openai-compatible" disabled />
            </label>
            <label className="field">
              <span>Base URL</span>
              <input
                value={aiBaseUrl}
                onChange={(event) => setAiBaseUrl(event.target.value)}
                placeholder="http://127.0.0.1:11434/v1"
              />
            </label>
          </div>
          <div className="form-grid three">
            <label className="field">
              <span>Model</span>
              <input value={aiModel} onChange={(event) => setAiModel(event.target.value)} placeholder="model-name" />
            </label>
            <label className="field">
              <span>API key environment variable</span>
              <input value={aiKeyEnv} onChange={(event) => setAiKeyEnv(event.target.value)} />
              <small>The key value is never stored or returned.</small>
            </label>
            <label className="field">
              <span>Timeout (s)</span>
              <input
                type="number"
                min={5}
                max={180}
                value={aiTimeout}
                onChange={(event) => setAiTimeout(Number(event.target.value))}
              />
            </label>
          </div>
          <p className="muted small">
            AI can summarise, compare and recommend. It cannot launch tools, modify repositories,
            publish or spend money.
          </p>
        </Section>

        <Section
          title="Startup profile"
          description="Never starts every application. Activation is explicit and bounded by process limits."
          className="settings-section"
        >
          <label className="checkbox">
            <input
              type="checkbox"
              checked={profileEnabled}
              onChange={(event) => setProfileEnabled(event.target.checked)}
            />
            Enable a startup profile
          </label>
          <fieldset className="check-list">
            <legend>Applications in profile</legend>
            {(applications.data ?? []).map((app) => (
              <label className="checkbox" key={app.id}>
                <input
                  type="checkbox"
                  checked={profileApplications.includes(app.id)}
                  onChange={() => toggleProfileApp(app.id)}
                />
                {app.name}
              </label>
            ))}
          </fieldset>
          <div className="settings-actions">
            <button
              className="button button-secondary button-small"
              onClick={() => void activateProfile()}
              disabled={!profileEnabled || !profileApplications.length}
              title={!profileEnabled ? "Enable and save the startup profile first" : undefined}
            >
              <Play size={14} /> Activate profile now
            </button>
            <span className="muted small">Activation is explicit; nothing is started at login automatically.</span>
          </div>
        </Section>

        <Section title="Retention" description="Data stays local. Retention limits are not deletion schedules yet." className="settings-section">
          <div className="form-grid three">
            <label className="field">
              <span>Activity days</span>
              <input
                type="number"
                min={1}
                max={3650}
                value={activityDays}
                onChange={(event) => setActivityDays(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Briefing days</span>
              <input
                type="number"
                min={1}
                max={3650}
                value={briefingDays}
                onChange={(event) => setBriefingDays(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Log days</span>
              <input
                type="number"
                min={1}
                max={3650}
                value={logDays}
                onChange={(event) => setLogDays(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="storage-note">
            <Database size={15} />
            <span>
              SQLite and logs live under <code>data/</code> in the Mission Control checkout. Back up by
              copying that directory while the server is stopped.
            </span>
          </div>
        </Section>
      </div>

      <Section
        title="Discovered repositories"
        description="Advisory classifications with evidence. Discovery never enables a launch command."
        actions={
          <span className="section-hint">
            <Search size={13} /> searchable
          </span>
        }
      >
        <div className="toolbar">
          <label className="search-field">
            <Search size={15} aria-hidden="true" />
            <input
              value={candidateFilter}
              onChange={(event) => setCandidateFilter(event.target.value)}
              placeholder="Filter by name, path or classification"
              aria-label="Filter candidates"
            />
          </label>
          <span className="toolbar-count">{filteredCandidates.length} candidates</span>
        </div>
        {candidates.loading && !candidates.data ? <LoadingBlock label="Loading candidates" compact /> : null}
        {candidates.data && filteredCandidates.length === 0 ? (
          <EmptyState
            title="No candidates"
            description="Run discovery or clear the filter. Generated directories stay excluded."
            icon={<FolderPlus size={20} />}
          />
        ) : null}
        {filteredCandidates.length ? (
          <div className="table-wrap">
            <table className="data-table candidate-table">
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Classification</th>
                  <th>Confidence</th>
                  <th>Git</th>
                  <th>Observed</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.slice(0, 100).map((candidate) => (
                  <tr key={candidate.id}>
                    <td>
                      <strong>{candidate.name}</strong>
                      <PathText>{candidate.path}</PathText>
                      {candidate.candidate ? null : <Tag tone="accent">linked</Tag>}
                    </td>
                    <td>
                      <span className={`classification classification-${candidate.classification}`}>
                        {classificationLabel(candidate.classification)}
                      </span>
                    </td>
                    <td>{Math.round(candidate.confidence * 100)}%</td>
                    <td>
                      {candidate.is_git ? (
                        <span>
                          {candidate.branch ?? "detached"}
                          {candidate.dirty ? <span className="warn-text"> · dirty</span> : null}
                        </span>
                      ) : (
                        <span className="muted">not Git</span>
                      )}
                    </td>
                    <td title={formatDateTime(candidate.last_observed_at)}>
                      {candidate.last_observed_at ? timeAgo(candidate.last_observed_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="muted small">
          Classification is advisory. To use one of these as an application, add it in the application
          registry with a verified launch command. To make it a project, associate its path when
          creating a project.
        </p>
      </Section>
    </div>
  );
}
