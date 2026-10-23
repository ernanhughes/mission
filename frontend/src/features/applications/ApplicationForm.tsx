import { useState, type FormEvent } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { InlineError, Section } from "../../components/ui";
import type { Application, Outcome, Project } from "../../types/api";

const categories = [
  "research",
  "quality",
  "commercial",
  "writing",
  "publishing",
  "execution",
  "supporting",
  "other",
];

const adapterOptions = ["", "next", "cocoder", "worker", "work"];

type DefinitionForm = {
  key: string;
  id?: string;
  name: string;
  launch_type: string;
  executable: string;
  argumentsText: string;
  working_directory: string;
  envText: string;
  browser_url: string;
  health_type: string;
  health_url: string;
  expected_port: string;
  is_primary: boolean;
  enabled: boolean;
  verified: boolean;
  verification_note: string;
  shutdown_behavior: string;
};

function blankDefinition(primary = false): DefinitionForm {
  return {
    key: `new-${crypto.randomUUID()}`,
    name: primary ? "Primary launch" : "Launch",
    launch_type: "none",
    executable: "",
    argumentsText: "",
    working_directory: "",
    envText: "",
    browser_url: "",
    health_type: "none",
    health_url: "",
    expected_port: "",
    is_primary: primary,
    enabled: false,
    verified: false,
    verification_note: "",
    shutdown_behavior: "terminate",
  };
}

function definitionsFromApp(app: Application | undefined): DefinitionForm[] {
  if (!app) return [];
  return app.launch_definitions.map((definition, index) => ({
    key: definition.id,
    id: definition.id,
    name: definition.name,
    launch_type: definition.launch_type,
    executable: definition.executable ?? "",
    argumentsText: definition.arguments.join("\n"),
    working_directory: definition.working_directory ?? "",
    envText: definition.env_names.join(", "),
    browser_url: definition.browser_url ?? "",
    health_type: definition.health_type,
    health_url: definition.health_url ?? "",
    expected_port: definition.expected_port ? String(definition.expected_port) : "",
    is_primary: definition.is_primary,
    enabled: definition.enabled,
    verified: definition.verified,
    verification_note: definition.verification_note,
    shutdown_behavior: definition.shutdown_behavior || "terminate",
  }));
}

function lines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function list(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ApplicationForm({
  app,
  onClose,
  onSaved,
}: {
  app?: Application;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const projects = useApi<Project[]>("/api/projects");
  const outcomes = useApi<Outcome[]>("/api/outcomes");
  const [name, setName] = useState(app?.name ?? "");
  const [description, setDescription] = useState(app?.description ?? "");
  const [category, setCategory] = useState(app?.category ?? "supporting");
  const [icon, setIcon] = useState(app?.icon ?? "");
  const [tags, setTags] = useState((app?.tags ?? []).join(", "));
  const [enabled, setEnabled] = useState(app?.enabled ?? true);
  const [pinned, setPinned] = useState(app?.pinned ?? false);
  const [repositoryPath, setRepositoryPath] = useState(app?.repository_path ?? "");
  const [additionalPaths, setAdditionalPaths] = useState((app?.additional_paths ?? []).join("\n"));
  const [workingDirectory, setWorkingDirectory] = useState(app?.working_directory ?? "");
  const [documentationPaths, setDocumentationPaths] = useState(
    (app?.documentation_paths ?? []).join("\n"),
  );
  const [outputPaths, setOutputPaths] = useState((app?.output_paths ?? []).join("\n"));
  const [notes, setNotes] = useState(app?.notes ?? "");
  const [adapter, setAdapter] = useState(app?.integration_adapter ?? "");
  const [adapterEnabled, setAdapterEnabled] = useState(app?.adapter_enabled ?? false);
  const [adapterConfig, setAdapterConfig] = useState(
    JSON.stringify(app?.adapter_config ?? {}, null, 2),
  );
  const [relatedProjects, setRelatedProjects] = useState<string[]>(app?.related_projects ?? []);
  const [relatedOutcomes, setRelatedOutcomes] = useState<string[]>(app?.outcomes ?? []);
  const [allowLaunch, setAllowLaunch] = useState(app?.control_policy.allow_launch ?? true);
  const [requireConfirmation, setRequireConfirmation] = useState(
    app?.control_policy.confirmation_required ?? false,
  );
  const [definitions, setDefinitions] = useState<DefinitionForm[]>(definitionsFromApp(app));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggle(listValue: string[], setter: (value: string[]) => void, id: string) {
    setter(listValue.includes(id) ? listValue.filter((item) => item !== id) : [...listValue, id]);
  }

  function updateDefinition(index: number, patch: Partial<DefinitionForm>) {
    setDefinitions((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      let config: Record<string, unknown> = {};
      if (adapterConfig.trim()) {
        try {
          config = JSON.parse(adapterConfig) as Record<string, unknown>;
        } catch {
          throw new Error("Adapter configuration must be valid JSON");
        }
      }
      const payload = {
        name: name.trim(),
        description,
        category,
        icon,
        tags: list(tags),
        enabled,
        pinned,
        repository_path: repositoryPath.trim() || null,
        additional_paths: lines(additionalPaths),
        working_directory: workingDirectory.trim() || null,
        documentation_paths: lines(documentationPaths),
        output_paths: lines(outputPaths),
        notes,
        integration_adapter: adapter || null,
        adapter_enabled: adapterEnabled,
        adapter_config: config,
        related_projects: relatedProjects,
        outcomes: relatedOutcomes,
        control_policy: {
          allow_launch: allowLaunch,
          confirmation_required: requireConfirmation,
        },
        launch_definitions: definitions.map((definition) => ({
          ...(definition.id ? { id: definition.id } : {}),
          name: definition.name.trim(),
          launch_type: definition.launch_type,
          executable: definition.executable.trim() || null,
          arguments: lines(definition.argumentsText),
          working_directory: definition.working_directory.trim() || null,
          env_names: list(definition.envText),
          browser_url: definition.browser_url.trim() || null,
          health_type: definition.health_type,
          health_url: definition.health_url.trim() || null,
          expected_port: definition.expected_port ? Number(definition.expected_port) : null,
          is_primary: definition.is_primary,
          enabled: definition.enabled,
          verified: definition.verified,
          verification_note: definition.verification_note,
          shutdown_behavior: definition.shutdown_behavior,
        })),
      };
      if (app) await api.patch(`/api/applications/${app.id}`, payload);
      else await api.post("/api/applications", payload);
      toast.push("success", app ? "Application updated" : "Application registered");
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
      title={app ? `Configure ${app.name}` : "Register application"}
      eyebrow={app ? "Application registry" : "New registry entry"}
      onClose={onClose}
      wide
      footer={
        <>
          <button className="button button-ghost" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button button-primary" type="submit" form="application-form" disabled={saving}>
            {saving ? "Saving…" : app ? "Save changes" : "Register application"}
          </button>
        </>
      }
    >
      <form id="application-form" onSubmit={(event) => void save(event)} className="form-stack">
        <InlineError message={error} />
        <Section title="Identity" className="form-section">
          <div className="form-grid two">
            <label className="field">
              <span>Name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} />
            </label>
            <label className="field">
              <span>Category</span>
              <select value={category} onChange={(event) => setCategory(event.target.value)}>
                {categories.map((item) => (
                  <option value={item} key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="field">
            <span>Description</span>
            <textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="form-grid three">
            <label className="field">
              <span>Icon label</span>
              <input value={icon} onChange={(event) => setIcon(event.target.value)} maxLength={4} placeholder="e.g. N" />
            </label>
            <label className="field">
              <span>Tags (comma separated)</span>
              <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="research, books" />
            </label>
            <div className="field checkbox-stack">
              <label className="checkbox">
                <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
                Enabled
              </label>
              <label className="checkbox">
                <input type="checkbox" checked={pinned} onChange={(event) => setPinned(event.target.checked)} />
                Pinned
              </label>
            </div>
          </div>
          <label className="field">
            <span>Notes</span>
            <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
        </Section>

        <Section title="Filesystem" className="form-section">
          <label className="field">
            <span>Primary repository path</span>
            <input
              value={repositoryPath}
              onChange={(event) => setRepositoryPath(event.target.value)}
              placeholder="C:\Projects\example"
            />
            <small>An absolute path. Mission Control never modifies it.</small>
          </label>
          <label className="field">
            <span>Working directory (optional)</span>
            <input
              value={workingDirectory}
              onChange={(event) => setWorkingDirectory(event.target.value)}
              placeholder="Defaults to the repository path"
            />
          </label>
          <div className="form-grid two">
            <label className="field">
              <span>Additional paths (one per line)</span>
              <textarea rows={2} value={additionalPaths} onChange={(event) => setAdditionalPaths(event.target.value)} />
            </label>
            <label className="field">
              <span>Documentation paths (one per line)</span>
              <textarea
                rows={2}
                value={documentationPaths}
                onChange={(event) => setDocumentationPaths(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span>Output/report paths (one per line)</span>
            <textarea rows={2} value={outputPaths} onChange={(event) => setOutputPaths(event.target.value)} />
          </label>
        </Section>

        <Section title="Integration" className="form-section">
          <div className="form-grid three">
            <label className="field">
              <span>Adapter</span>
              <select value={adapter} onChange={(event) => setAdapter(event.target.value)}>
                {adapterOptions.map((item) => (
                  <option value={item} key={item || "none"}>
                    {item || "None"}
                  </option>
                ))}
              </select>
            </label>
            <label className="checkbox field-checkbox">
              <input
                type="checkbox"
                checked={adapterEnabled}
                onChange={(event) => setAdapterEnabled(event.target.checked)}
              />
              Enable read-only adapter
            </label>
          </div>
          {adapter ? (
            <label className="field">
              <span>Adapter configuration (JSON)</span>
              <textarea
                className="code-input"
                rows={4}
                value={adapterConfig}
                onChange={(event) => setAdapterConfig(event.target.value)}
              />
            </label>
          ) : null}
          <div className="form-grid two">
            <fieldset className="check-list">
              <legend>Related projects</legend>
              {(projects.data ?? []).map((project) => (
                <label className="checkbox" key={project.id}>
                  <input
                    type="checkbox"
                    checked={relatedProjects.includes(project.id)}
                    onChange={() => toggle(relatedProjects, setRelatedProjects, project.id)}
                  />
                  {project.name}
                </label>
              ))}
            </fieldset>
            <fieldset className="check-list">
              <legend>Supported outcomes</legend>
              {(outcomes.data ?? []).map((outcome) => (
                <label className="checkbox" key={outcome.id}>
                  <input
                    type="checkbox"
                    checked={relatedOutcomes.includes(outcome.id)}
                    onChange={() => toggle(relatedOutcomes, setRelatedOutcomes, outcome.id)}
                  />
                  {outcome.name}
                </label>
              ))}
            </fieldset>
          </div>
        </Section>

        <Section
          title="Launch definitions"
          description="Commands are stored here. Launch requests never accept an executable, working directory or raw shell command."
          className="form-section"
          actions={
            <button
              type="button"
              className="button button-secondary button-small"
              onClick={() => setDefinitions((current) => [...current, blankDefinition(current.length === 0)])}
            >
              <Plus size={14} /> Add definition
            </button>
          }
        >
          {definitions.length === 0 ? (
            <p className="muted">
              No launch definitions. Repository and URL actions still work where configured.
            </p>
          ) : null}
          <div className="launch-definitions">
            {definitions.map((definition, index) => (
              <details className="launch-form" key={definition.key} open={definitions.length === 1}>
                <summary>
                  <span>{definition.name || "Untitled launch"}</span>
                  <span className="launch-summary-meta">
                    {definition.launch_type}
                    {definition.enabled ? " · enabled" : " · disabled"}
                    {definition.verified ? " · verified" : ""}
                  </span>
                </summary>
                <div className="launch-form-body">
                  <div className="form-grid three">
                    <label className="field">
                      <span>Name</span>
                      <input
                        value={definition.name}
                        onChange={(event) => updateDefinition(index, { name: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      <span>Type</span>
                      <select
                        value={definition.launch_type}
                        onChange={(event) => updateDefinition(index, { launch_type: event.target.value })}
                      >
                        <option value="none">None</option>
                        <option value="command">Command</option>
                        <option value="server">Server</option>
                        <option value="url">URL only</option>
                        <option value="editor">Editor</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Executable</span>
                      <input
                        value={definition.executable}
                        onChange={(event) => updateDefinition(index, { executable: event.target.value })}
                        placeholder="Code.exe or a command on PATH"
                      />
                    </label>
                  </div>
                  <div className="form-grid two">
                    <label className="field">
                      <span>Arguments (one per line — no shell)</span>
                      <textarea
                        className="code-input"
                        rows={3}
                        value={definition.argumentsText}
                        onChange={(event) => updateDefinition(index, { argumentsText: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>Working directory</span>
                      <input
                        value={definition.working_directory}
                        onChange={(event) => updateDefinition(index, { working_directory: event.target.value })}
                      />
                    </label>
                  </div>
                  <div className="form-grid two">
                    <label className="field">
                      <span>Allowed environment variable names</span>
                      <input
                        value={definition.envText}
                        onChange={(event) => updateDefinition(index, { envText: event.target.value })}
                        placeholder="WORK_DATABASE_URL"
                      />
                      <small>Values stay in the Mission Control process environment; they are not stored.</small>
                    </label>
                    <label className="field">
                      <span>Browser URL</span>
                      <input
                        value={definition.browser_url}
                        onChange={(event) => updateDefinition(index, { browser_url: event.target.value })}
                        placeholder="http://127.0.0.1:8765/"
                      />
                    </label>
                  </div>
                  <div className="form-grid three">
                    <label className="field">
                      <span>Health check</span>
                      <select
                        value={definition.health_type}
                        onChange={(event) => updateDefinition(index, { health_type: event.target.value })}
                      >
                        <option value="none">None</option>
                        <option value="http">HTTP</option>
                        <option value="tcp">TCP</option>
                        <option value="process">Managed process</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Health URL</span>
                      <input
                        value={definition.health_url}
                        onChange={(event) => updateDefinition(index, { health_url: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>Expected port</span>
                      <input
                        type="number"
                        min={1}
                        max={65535}
                        value={definition.expected_port}
                        onChange={(event) => updateDefinition(index, { expected_port: event.target.value })}
                      />
                    </label>
                  </div>
                  <label className="field">
                    <span>Verification note</span>
                    <input
                      value={definition.verification_note}
                      onChange={(event) => updateDefinition(index, { verification_note: event.target.value })}
                      placeholder="How was this command verified?"
                    />
                  </label>
                  <div className="checkbox-row">
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={definition.enabled}
                        onChange={(event) => updateDefinition(index, { enabled: event.target.checked })}
                      />
                      Enabled
                    </label>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={definition.verified}
                        onChange={(event) => updateDefinition(index, { verified: event.target.checked })}
                      />
                      Verified by a person
                    </label>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={definition.is_primary}
                        onChange={(event) => updateDefinition(index, { is_primary: event.target.checked })}
                      />
                      Primary
                    </label>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={definition.shutdown_behavior === "wait"}
                        onChange={(event) =>
                          updateDefinition(index, { shutdown_behavior: event.target.checked ? "wait" : "terminate" })
                        }
                      />
                      Allow up to 15s before forcing shutdown
                    </label>
                  </div>
                  <div className="launch-form-actions">
                    <button
                      type="button"
                      className="button button-danger button-small"
                      onClick={() => setDefinitions((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    >
                      <Trash2 size={14} /> Remove definition
                    </button>
                  </div>
                </div>
              </details>
            ))}
          </div>
        </Section>

        <Section title="Control policy" className="form-section">
          <div className="checkbox-row">
            <label className="checkbox">
              <input type="checkbox" checked={allowLaunch} onChange={(event) => setAllowLaunch(event.target.checked)} />
              Allow launch actions
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={requireConfirmation}
                onChange={(event) => setRequireConfirmation(event.target.checked)}
              />
              Require confirmation before launch
            </label>
          </div>
        </Section>
      </form>
    </Modal>
  );
}
