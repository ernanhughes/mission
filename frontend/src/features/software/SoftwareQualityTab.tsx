import { useMemo, useState } from "react";
import { Copy } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PathText,
  Section,
  Tag,
} from "../../components/ui";
import { copyText } from "../../lib/clipboard";
import { formatDateTime, timeAgo } from "../../lib/format";
import type {
  CultivationGoal,
  ProjectDetail,
  SoftwareCharter,
  SoftwareDimension,
  SoftwareEvaluation,
  SoftwareEvalReview,
  SoftwareFinding,
  SoftwarePrompt,
} from "../../types/api";

const RUBRIC_LABELS: Record<string, { label: string; weight: number }> = {
  purpose: { label: "Purpose alignment", weight: 150 },
  correctness: { label: "Correctness", weight: 170 },
  testing: { label: "Testing", weight: 130 },
  architecture: { label: "Architecture", weight: 130 },
  maintainability: { label: "Maintainability", weight: 100 },
  security: { label: "Security", weight: 100 },
  operations: { label: "Operations", weight: 70 },
  documentation: { label: "Documentation", weight: 50 },
  usage: { label: "Usage", weight: 50 },
  delivery: { label: "Delivery", weight: 50 },
};
const ORDER = Object.keys(RUBRIC_LABELS);

function CopyBlock({ text, label }: { text: string; label: string }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await copyText(text);
      setCopied(true);
      toast.push("success", "Copied", "Paste it into your local agent. Nothing was executed.");
      window.setTimeout(() => setCopied(false), 2000);
    } catch (caught) {
      toast.push("error", "Could not copy", errorMessage(caught));
    }
  }
  return (
    <div>
      <pre className="log-view" style={{ whiteSpace: "pre-wrap" }}>{text}</pre>
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={() => void copy()} aria-label={label}>
          <Copy size={13} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

export function SoftwareQualityTab({ projectId, data }: { projectId: string; data: ProjectDetail }) {
  const charters = useApi<SoftwareCharter[]>(`/api/software-quality/charters?project_id=${projectId}`, { pollMs: 30000 });
  const evaluations = useApi<SoftwareEvaluation[]>(`/api/software-quality/evaluations?project_id=${projectId}&limit=50`, { pollMs: 10000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const sorted = useMemo(
    () => [...(evaluations.data ?? [])].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [evaluations.data],
  );
  const selected = selectedId ?? sorted[0]?.id ?? null;
  const latest = sorted[0] ?? null;
  const running = sorted.some((item) => ["queued", "running"].includes(item.status));

  return (
    <div>
      <CharterSection projectId={projectId} charters={charters} />
      {latest ? (
        <AssessmentOverview evaluation={latest} onOpen={() => setSelectedId(latest.id)} />
      ) : (
        <Section
          title="Quality"
          description="No quality evaluation has been recorded for this workspace. Unassessed is reported honestly — never as zero."
          actions={<Tag>Unassessed</Tag>}
        >
          {!running ? (
            <p className="muted small">
              Evaluate the project to produce the first evidence-backed assessment. Missing
              evidence stays missing; the report will say what is unknown.
            </p>
          ) : (
            <p className="muted small">An evaluation is running… results appear below when it completes.</p>
          )}
        </Section>
      )}
      <EvaluateSection projectId={projectId} onStarted={() => evaluations.reload()} />
      {selected ? (
        <EvaluationDetail
          key={selected}
          projectId={projectId}
          evaluationId={selected}
          onChanged={() => evaluations.reload()}
        />
      ) : null}
      <HistorySection
        projectId={projectId}
        evaluations={sorted}
        selectedId={selected}
        onSelect={setSelectedId}
        loading={evaluations.loading}
        error={evaluations.error?.message ?? null}
        onReload={evaluations.reload}
      />
    </div>
  );
}

function CharterSection({
  projectId,
  charters,
}: {
  projectId: string;
  charters: { data: SoftwareCharter[] | null; loading: boolean; error: { message: string } | null; reload: () => void };
}) {
  const toast = useToast();
  const [proposeOpen, setProposeOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const current = (charters.data ?? []).find((c) => c.status === "confirmed") ?? (charters.data ?? [])[0] ?? null;

  async function confirm(id: string) {
    setBusy(true);
    try {
      await api.post(`/api/software-quality/charters/${id}/confirm`);
      toast.push("success", "Charter confirmed", "Evaluations can now judge purpose alignment against owner intent.");
      charters.reload();
    } catch (caught) {
      toast.push("error", "Could not confirm charter", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      title="Project charter"
      description="What this project is for, in the owner's words. Drafts are unconfirmed inference; only a confirmed charter counts as intent."
      actions={
        current ? (
          <Tag tone={current.status === "confirmed" ? "accent" : "warn"}>
            {current.status} · r{current.revision}
          </Tag>
        ) : undefined
      }
    >
      {charters.loading ? <LoadingBlock label="Loading charter" compact /> : null}
      {charters.error ? <InlineError message={charters.error.message} /> : null}
      {!current && !charters.loading ? (
        <p className="muted small">
          No charter recorded. Purpose alignment will be reported as provisional until a
          charter is confirmed.
        </p>
      ) : null}
      {current ? (
        <div>
          <p><strong>Purpose:</strong> {current.purpose || "—"}</p>
          <p className="muted small">
            Users: {current.users || "—"} · Lifecycle: {current.lifecycle || "—"}
          </p>
          {current.acceptance.length ? (
            <p className="muted small">Acceptance: {current.acceptance.join(" · ").slice(0, 400)}</p>
          ) : null}
          {current.status !== "confirmed" ? (
            <div className="button-row">
              <button className="button button-primary button-small" disabled={busy} onClick={() => void confirm(current.id)}>
                Confirm this charter
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={() => setProposeOpen((v) => !v)} aria-expanded={proposeOpen}>
          {proposeOpen ? "Hide proposal" : "Propose from evidence"}
        </button>
      </div>
      {proposeOpen ? <CharterProposer projectId={projectId} onSaved={() => { charters.reload(); setProposeOpen(false); }} /> : null}
    </Section>
  );
}

function draftValue(field: { value?: string; source?: string } | undefined): string {
  return typeof field?.value === "string" ? field.value : "";
}

function CharterProposer({ projectId, onSaved }: { projectId: string; onSaved: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ purpose: "", users: "", lifecycle: "", verification: "" });

  async function propose() {
    setBusy(true);
    try {
      const result = await api.post<Record<string, unknown>>(
        `/api/software-quality/charters/propose?project_id=${projectId}`, {},
      );
      setDraft(result);
      setForm({
        purpose: draftValue(result.purpose as { value?: string }) ,
        users: draftValue(result.users as { value?: string }),
        lifecycle: draftValue(result.lifecycle as { value?: string }),
        verification: draftValue(result.verification_expectations as { value?: string }),
      });
    } catch (caught) {
      toast.push("error", "Could not propose charter", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!form.purpose.trim()) {
      toast.push("error", "Purpose is required", "A charter without a purpose cannot guide evaluation.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/software-quality/charters", {
        project_id: projectId,
        purpose: form.purpose,
        users: form.users,
        capabilities: [],
        interfaces: [],
        acceptance: [],
        non_goals: [],
        constraints: [],
        lifecycle: form.lifecycle,
        dependencies: [],
        verification_expectations: form.verification,
        evidence_refs: [],
        provenance: { proposed_from: "evidence", unconfirmed: true },
      });
      toast.push("success", "Draft charter saved", "Review and confirm it to make it owner intent.");
      onSaved();
    } catch (caught) {
      toast.push("error", "Could not save charter", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="form-stack">
      {!draft ? (
        <button className="button button-secondary button-small" disabled={busy} onClick={() => void propose()}>
          {busy ? "Proposing…" : "Generate evidence-based draft"}
        </button>
      ) : (
        <>
          <p className="warn-text small">Every field below is UNCONFIRMED. Correct it before saving, and confirm after saving.</p>
          <label className="field">
            <span>Purpose</span>
            <textarea rows={3} value={form.purpose} onChange={(event) => setForm({ ...form, purpose: event.target.value })} aria-label="Charter purpose" />
          </label>
          <label className="field">
            <span>Intended users / consuming systems</span>
            <input value={form.users} onChange={(event) => setForm({ ...form, users: event.target.value })} aria-label="Charter users" />
          </label>
          <label className="field">
            <span>Lifecycle</span>
            <input value={form.lifecycle} onChange={(event) => setForm({ ...form, lifecycle: event.target.value })} aria-label="Charter lifecycle" />
          </label>
          <label className="field">
            <span>Verification expectations</span>
            <textarea rows={2} value={form.verification} onChange={(event) => setForm({ ...form, verification: event.target.value })} aria-label="Charter verification expectations" />
          </label>
          <div className="button-row">
            <button className="button button-primary button-small" disabled={busy} onClick={() => void save()}>
              Save as draft
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function AssessmentOverview({ evaluation, onOpen }: { evaluation: SoftwareEvaluation; onOpen: () => void }) {
  const dims = ORDER.map((id) => ({ id, ...(evaluation.dimensions[id] ?? { state: "abstained" }) })) as Array<SoftwareDimension & { id: string }>;
  const assessed = dims.filter((d) => d.state === "assessed");
  return (
    <Section
      title="Latest assessment"
      description={`${evaluation.id.slice(0, 18)} · ${formatDateTime(evaluation.created_at)} · model ${evaluation.observed_model ?? evaluation.requested_model ?? "unknown"} (${evaluation.model_route || "route unknown"})`}
      actions={
        <>
          {evaluation.freshness === "current" ? <Tag tone="accent">Current</Tag> : <Tag tone="warn">Stale</Tag>}
          {evaluation.overall != null ? (
            <Tag tone="accent">{Math.round(evaluation.overall)} / {Math.round(evaluation.max_attainable)}</Tag>
          ) : (
            <Tag>Partial · no overall</Tag>
          )}
        </>
      }
    >
      {evaluation.freshness !== "current" ? (
        <p className="warn-text small">{evaluation.freshness_reasons.join(" · ")}</p>
      ) : null}
      <div className="writer-mini-scores">
        {dims.map((dim) => (
          <span key={dim.id} title={RUBRIC_LABELS[dim.id]?.label ?? dim.id}>
            {RUBRIC_LABELS[dim.id]?.label ?? dim.id}:{" "}
            {dim.state === "assessed" ? `${dim.score}` : dim.state === "na" ? "n/a" : "—"}
            {dim.state === "assessed" ? ` / ${dim.max}` : ""}
          </span>
        ))}
      </div>
      <p className="muted small">
        Coverage {evaluation.coverage_percent ?? 0}% ({assessed.length}/10 dimensions) ·
        confidence {assessed.length ? Math.round((assessed.reduce((sum, d) => sum + (d.confidence ?? 0), 0) / assessed.length) * 100) : 0}% avg
      </p>
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={onOpen}>Open detail</button>
      </div>
    </Section>
  );
}

function EvaluateSection({ projectId, onStarted }: { projectId: string; onStarted: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [model, setModel] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const models = useApi<{ models?: Array<{ id: string }>; detail?: string }>(open ? "/api/software-quality/models" : null);
  const evidence = useApi<Record<string, unknown>>(open ? `/api/software-quality/evidence?project_id=${projectId}` : null);

  async function loadPreview() {
    setBusy("preview");
    try {
      const result = await api.post<Record<string, unknown>>("/api/software-quality/evaluations/preview", {
        project_id: projectId, model: model || undefined,
      });
      setPreview(result);
    } catch (caught) {
      toast.push("error", "Could not build prompt", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function execute() {
    setBusy("run");
    try {
      const created = await api.post<{ id: string }>("/api/software-quality/evaluations", {
        project_id: projectId, model: model || undefined,
      });
      toast.push("success", "Evaluation started", created.id);
      onStarted();
    } catch (caught) {
      toast.push("error", "Could not start evaluation", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Evaluate project"
      description="Inspect the evidence scope, copy the exact prompt, then execute explicitly. Nothing runs implicitly."
    >
      <div className="button-row">
        <button className="button button-secondary button-small" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Hide evaluation flow" : "Evaluate project"}
        </button>
      </div>
      {open ? (
        <div className="form-stack">
          {evidence.loading ? <LoadingBlock label="Collecting evidence" compact /> : null}
          {evidence.error ? <InlineError message={evidence.error.message} /> : null}
          {evidence.data ? (
            <p className="muted small">
              Evidence fingerprint <code className="mono">{String(evidence.data.fingerprint ?? "").slice(0, 16)}</code> ·{" "}
              {String((evidence.data.file_count as number) ?? 0)} files ·{" "}
              {(evidence.data.evidence as Array<unknown> ?? []).length} cited evidence ids ·{" "}
              {evidence.data.truncated_total ? "evidence truncated to budget" : "within budget"}
            </p>
          ) : null}
          <div className="inline-form">
            <label className="muted small">
              Model{" "}
              <input
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder={(models.data?.models?.[0] as { id: string } | undefined)?.id ?? "default route"}
                aria-label="Evaluation model"
                size={30}
                list="sq-models"
              />
            </label>
            <datalist id="sq-models">
              {(models.data?.models ?? []).map((entry: unknown) => (
                <option key={String((entry as { id: string }).id)} value={String((entry as { id: string }).id)} />
              ))}
            </datalist>
            {models.data?.detail ? <span className="muted small">{String(models.data.detail).slice(0, 160)}</span> : null}
            <button className="button button-secondary button-small" disabled={busy !== null} onClick={() => void loadPreview()}>
              {busy === "preview" ? "Building…" : "Preview prompt"}
            </button>
            <button className="button button-primary button-small" disabled={busy !== null} onClick={() => void execute()}>
              {busy === "run" ? "Starting…" : "Execute evaluation"}
            </button>
          </div>
          {preview ? (
            <div>
              <p className="muted small">
                Model {String(preview.model)} ({String(preview.route)}) ·{" "}
                {String((preview as { calls_planned?: unknown }).calls_planned ?? 10)} bounded calls ·{" "}
                {String(preview.prompt_chars)} chars total · {String(preview.evidence_id_count)} evidence ids · hash{" "}
                <code className="mono">{String(preview.prompt_hash).slice(0, 12)}</code>
              </p>
              <p className="muted small">
                Showing the first dimension prompt; execution runs one bounded prompt per
                dimension so no single model call exceeds its budget.
              </p>
              <CopyBlock text={String(preview.prompt ?? "")} label="Copy evaluation prompt" />
            </div>
          ) : null}
        </div>
      ) : null}
    </Section>
  );
}

function EvaluationDetail({
  projectId,
  evaluationId,
  onChanged,
}: {
  projectId: string;
  evaluationId: string;
  onChanged: () => void;
}) {
  const toast = useToast();
  const detail = useApi<{
    evaluation: SoftwareEvaluation;
    reviews: SoftwareEvalReview[];
    findings: SoftwareFinding[];
  }>(`/api/software-quality/evaluations/${evaluationId}`, { pollMs: 5000 });
  const [reviewModel, setReviewModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [compareId, setCompareId] = useState("");
  const [compare, setCompare] = useState<Record<string, unknown> | null>(null);
  const [goalId, setGoalId] = useState("");
  const goals = useApi<CultivationGoal[]>("/api/cultivation/goals");

  const evaluation = detail.data?.evaluation ?? null;

  async function requestReview() {
    if (!evaluation) return;
    setBusy(true);
    try {
      await api.post(`/api/software-quality/evaluations/${evaluation.id}/reviews`, { model: reviewModel || undefined });
      toast.push("success", "Independent review started", "It judges the evidence, not the first conclusion.");
      detail.reload();
    } catch (caught) {
      toast.push("error", "Could not start review", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function runCompare() {
    if (!evaluation || !compareId) return;
    try {
      const result = await api.get<Record<string, unknown>>(
        `/api/software-quality/evaluations/${evaluation.id}/compare/${compareId}`,
      );
      setCompare(result);
    } catch (caught) {
      toast.push("error", "Could not compare", errorMessage(caught));
    }
  }

  async function reportEvaluation() {
    if (!evaluation || !goalId) return;
    try {
      const result = await api.post<{ verified: boolean; reference: string }>("/api/software-quality/cultivation-report", {
        project_id: projectId, goal_id: goalId, evaluation_id: evaluation.id,
      });
      toast.push(
        result.verified ? "success" : "info",
        result.verified ? "Verified progress reported" : "Recorded as observation (not qualification)",
        result.reference,
      );
    } catch (caught) {
      toast.push("error", "Could not report", errorMessage(caught));
    }
  }

  if (detail.loading && !detail.data) return <LoadingBlock label="Loading evaluation" compact />;
  if (detail.error) return <ErrorState message={detail.error.message} onRetry={detail.reload} />;
  if (!evaluation) return null;

  const dims = ORDER.map((id) => ({ id, ...(evaluation.dimensions[id] ?? { state: "abstained" }) })) as Array<SoftwareDimension & { id: string }>;
  const disagreements = (detail.data?.reviews ?? []).filter((r) => r.verdict === "disagree" || r.verdict === "partial");

  return (
    <Section
      title={`Evaluation ${evaluation.id.slice(0, 18)}`}
      description={`${formatDateTime(evaluation.created_at)} · ${evaluation.status} · rubric ${evaluation.rubric_id} v${evaluation.rubric_version}`}
      actions={
        evaluation.overall != null ? (
          <Tag tone="accent">{Math.round(evaluation.overall)} / {Math.round(evaluation.max_attainable)}</Tag>
        ) : (
          <Tag>{evaluation.status}</Tag>
        )
      }
    >
      {evaluation.freshness !== "current" ? (
        <p className="warn-text small">Stale: {evaluation.freshness_reasons.join(" · ")}</p>
      ) : null}
      {evaluation.error ? <p className="warn-text small">{evaluation.error}</p> : null}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr><th>Dimension</th><th>Score</th><th>Conf</th><th>Rationale</th></tr>
          </thead>
          <tbody>
            {dims.map((dim) => (
              <tr key={dim.id}>
                <td>{RUBRIC_LABELS[dim.id]?.label ?? dim.id}</td>
                <td>{dim.state === "assessed" ? `${dim.score} / ${dim.max}` : dim.state === "na" ? "n/a" : "—"}</td>
                <td>{Math.round((dim.confidence ?? 0) * 100)}%</td>
                <td className="muted small">{(dim.rationale ?? "").slice(0, 220)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {evaluation.uncertainty ? <p className="muted small"><strong>Uncertainty:</strong> {evaluation.uncertainty.slice(0, 500)}</p> : null}
      {evaluation.limitations.length ? (
        <p className="warn-text small"><strong>Limits:</strong> {evaluation.limitations.join(" · ").slice(0, 500)}</p>
      ) : null}

      <h4 className="writer-section-heading">Independent reviews ({(detail.data?.reviews ?? []).length})</h4>
      {disagreements.length ? (
        <p className="warn-text small">
          {disagreements.length} review(s) disagree or partially agree — conflicting assessments are preserved, not overwritten.
        </p>
      ) : null}
      {(detail.data?.reviews ?? []).map((review) => (
        <div className="adapter-card" key={review.id}>
          <div className="adapter-head">
            <div><strong>{review.reviewer_model || "review"}</strong> · {review.status}{review.verdict ? ` · ${review.verdict}` : ""}</div>
            <Tag tone={review.verdict === "agree" ? "accent" : review.verdict ? "warn" : "default"}>{review.verdict || review.status}</Tag>
          </div>
          {review.rationale ? <p className="muted small">{review.rationale.slice(0, 400)}</p> : null}
          {review.error ? <p className="warn-text small">{review.error.slice(0, 300)}</p> : null}
        </div>
      ))}
      <div className="inline-form">
        <label className="muted small">
          Review model{" "}
          <input value={reviewModel} onChange={(event) => setReviewModel(event.target.value)} placeholder="must differ from evaluation model" aria-label="Independent review model" size={30} />
        </label>
        <button className="button button-secondary button-small" disabled={busy} onClick={() => void requestReview()}>
          Request independent review
        </button>
      </div>

      <h4 className="writer-section-heading">Compare with another assessment</h4>
      <div className="inline-form">
        <label className="muted small">
          Other evaluation{" "}
          <input value={compareId} onChange={(event) => setCompareId(event.target.value)} placeholder="sqeval:…" aria-label="Comparison evaluation id" size={24} />
        </label>
        <button className="button button-secondary button-small" onClick={() => void runCompare()}>Compare</button>
      </div>
      {compare ? (
        <p className={compare.compatible ? "muted small" : "warn-text small"}>
          {String(compare.compatible ? "Comparable" : `Not directly comparable: ${compare.reason}`)}
          {typeof compare.delta === "number" ? ` · delta ${compare.delta > 0 ? "+" : ""}${compare.delta}` : ""}
        </p>
      ) : null}

      <h4 className="writer-section-heading">Report to Cultivation</h4>
      <p className="muted small">
        A bare score is recorded as an observation, never as qualification. Qualification stays an owner decision.
      </p>
      <div className="inline-form">
        <label className="muted small">
          Goal{" "}
          <select value={goalId} onChange={(event) => setGoalId(event.target.value)} aria-label="Cultivation goal">
            <option value="">Select a goal…</option>
            {(goals.data ?? []).map((goal) => (
              <option key={goal.id} value={goal.id}>{goal.name}</option>
            ))}
          </select>
        </label>
        <button className="button button-secondary button-small" disabled={!goalId} onClick={() => void reportEvaluation()}>
          Report evaluation
        </button>
      </div>
    </Section>
  );
}

function HistorySection({
  evaluations,
  selectedId,
  onSelect,
  loading,
  error,
  onReload,
}: {
  projectId: string;
  evaluations: SoftwareEvaluation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  error: string | null;
  onReload: () => void;
}) {
  if (loading && !evaluations.length) return <LoadingBlock label="Loading history" compact />;
  if (error) return <ErrorState message={error} onRetry={onReload} />;
  if (!evaluations.length) return null;
  const maxOverall = Math.max(...evaluations.map((e) => e.overall ?? 0), 0);
  return (
    <Section title="History" description="Append-only. Previous assessments are never rewritten to make the latest look better.">
      <ul className="plain-list">
        {evaluations.map((item) => (
          <li key={item.id}>
            <button
              className={`writer-queue-row ${selectedId === item.id ? "active" : ""}`}
              onClick={() => onSelect(item.id)}
              aria-expanded={selectedId === item.id}
            >
              <span className="writer-queue-main">
                <strong>{item.overall != null ? `${Math.round(item.overall)} / ${Math.round(item.max_attainable)}` : item.status}</strong>
                <small>
                  {formatDateTime(item.created_at)} · {item.observed_model ?? item.requested_model ?? "no model"} ·
                  coverage {item.coverage_percent ?? 0}% · {item.freshness}
                </small>
              </span>
              <span className="muted small" aria-hidden="true">
                {maxOverall > 0 && item.overall != null ? "█".repeat(Math.max(1, Math.round((item.overall / maxOverall) * 12))) : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function FindingsSection({ projectId }: { projectId: string }) {
  const toast = useToast();
  const [status, setStatus] = useState("ALL");
  const findings = useApi<SoftwareFinding[]>(
    `/api/software-quality/findings?project_id=${projectId}${status === "ALL" ? "" : `&status=${status}`}`,
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [resolveFor, setResolveFor] = useState<string | null>(null);
  const [resolveEvidence, setResolveEvidence] = useState("");
  const [goalId, setGoalId] = useState("");
  const goals = useApi<CultivationGoal[]>("/api/cultivation/goals");

  async function act(path: string, body: unknown, label: string) {
    setBusy(label);
    try {
      await api.post(path, body);
      toast.push("success", label);
      findings.reload();
    } catch (caught) {
      toast.push("error", `Could not ${label.toLowerCase()}`, errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function reportProgress(findingId: string) {
    if (!goalId) {
      toast.push("error", "Select a goal first", "Verified progress must attach to an explicit goal.");
      return;
    }
    setBusy(`report-${findingId}`);
    try {
      const result = await api.post<{ verified: boolean; reference: string }>("/api/software-quality/cultivation-report", {
        project_id: projectId, goal_id: goalId, finding_id: findingId,
      });
      toast.push(result.verified ? "success" : "info", result.verified ? "Verified progress reported" : "Recorded without verification", result.reference);
    } catch (caught) {
      toast.push("error", "Could not report", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  const items = findings.data ?? [];
  return (
    <Section
      title="Findings"
      description="Verified defects are distinguished from AI hypotheses. Only resolved findings with evidence count as progress."
      actions={<Tag tone={items.some((f) => f.status === "proposed") ? "warn" : "accent"}>{items.length} findings</Tag>}
    >
      <div className="inline-form">
        <label className="muted small">
          Status{" "}
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Finding status filter">
            {["ALL", "proposed", "accepted", "in_progress", "needs_verification", "resolved", "rejected", "deferred", "investigate", "reopened"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Cultivation goal{" "}
          <select value={goalId} onChange={(event) => setGoalId(event.target.value)} aria-label="Cultivation goal for progress reports">
            <option value="">Select a goal…</option>
            {(goals.data ?? []).map((goal) => (
              <option key={goal.id} value={goal.id}>{goal.name}</option>
            ))}
          </select>
        </label>
      </div>
      {findings.loading ? <LoadingBlock label="Loading findings" compact /> : null}
      {findings.error ? <ErrorState message={findings.error.message} onRetry={findings.reload} /> : null}
      {items.length === 0 && !findings.loading ? (
        <p className="muted small">No findings in this filter. Absence here is not proof of quality — check coverage above.</p>
      ) : null}
      {items.map((finding) => (
        <article className="writer-decision-card" key={finding.id}>
          <div className="writer-decision-head">
            <Tag tone={finding.severity === "critical" || finding.severity === "high" ? "danger" : "default"}>{finding.severity}</Tag>
            <strong>{finding.title}</strong>
            <span className="writer-decision-count">{finding.status}{finding.verified ? " · verified" : ""}</span>
          </div>
          <p className="muted small"><strong>Component:</strong> {finding.component || "—"}</p>
          <p className="muted small"><strong>Observed:</strong> {finding.observed.slice(0, 300)}</p>
          <p className="muted small"><strong>Expected:</strong> {finding.expected.slice(0, 300)}</p>
          {finding.proposal ? <p className="muted small"><strong>Proposal:</strong> {finding.proposal.slice(0, 300)}</p> : null}
          {finding.evidence_refs.length ? (
            <p className="muted small"><strong>Evidence:</strong> {finding.evidence_refs.join(", ").slice(0, 300)}</p>
          ) : null}
          {finding.resolution_evidence.length ? (
            <p className="muted small"><strong>Resolution evidence:</strong> {finding.resolution_evidence.join(", ").slice(0, 300)}</p>
          ) : null}
          <div className="button-row">
            {(["ACCEPT", "REJECT", "DEFER", "INVESTIGATE"] as const).map((decision) => (
              <button
                key={decision}
                className="button button-secondary button-small"
                disabled={busy !== null}
                onClick={() => void act(`/api/software-quality/findings/${finding.id}/reviews`, { decision, reason: "", reviewer: "owner" }, `Finding ${decision.toLowerCase()}`)}
              >
                {decision}
              </button>
            ))}
            {finding.status === "accepted" ? (
              <button className="button button-secondary button-small" disabled={busy !== null} onClick={() => void act(`/api/software-quality/findings/${finding.id}/start`, {}, "Work started")}>
                Start work
              </button>
            ) : null}
            {["accepted", "in_progress", "needs_verification"].includes(finding.status) ? (
              <button className="button button-secondary button-small" onClick={() => setResolveFor(resolveFor === finding.id ? null : finding.id)}>
                Record resolution
              </button>
            ) : null}
            {finding.status === "needs_verification" ? (
              <button className="button button-primary button-small" disabled={busy !== null} onClick={() => void act(`/api/software-quality/findings/${finding.id}/confirm-resolution`, {}, "Resolution confirmed")}>
                Confirm resolution
              </button>
            ) : null}
            {["resolved", "rejected", "deferred", "investigate"].includes(finding.status) ? (
              <button className="button button-ghost button-small" disabled={busy !== null} onClick={() => void act(`/api/software-quality/findings/${finding.id}/reopen`, { reason: "reopened by owner" }, "Finding reopened")}>
                Reopen
              </button>
            ) : null}
            {finding.status === "resolved" ? (
              <button className="button button-secondary button-small" disabled={busy !== null || !goalId} title={goalId ? "Report verified progress to Cultivation" : "Select a goal first"} onClick={() => void reportProgress(finding.id)}>
                Report verified progress
              </button>
            ) : null}
          </div>
          {resolveFor === finding.id ? (
            <div className="inline-form">
              <label className="muted small">
                Resolution evidence{" "}
                <input
                  value={resolveEvidence}
                  onChange={(event) => setResolveEvidence(event.target.value)}
                  placeholder="tests/test_main.py, commit abc123…"
                  aria-label="Resolution evidence"
                  size={40}
                />
              </label>
              <button
                className="button button-primary button-small"
                disabled={busy !== null || !resolveEvidence.trim()}
                onClick={() => {
                  void act(
                    `/api/software-quality/findings/${finding.id}/resolve`,
                    { resolution_evidence: resolveEvidence.split(",").map((s) => s.trim()).filter(Boolean) },
                    "Resolution recorded",
                  );
                  setResolveFor(null);
                  setResolveEvidence("");
                }}
              >
                Save evidence
              </button>
            </div>
          ) : null}
        </article>
      ))}
    </Section>
  );
}

export function PromptsSection({ projectId }: { projectId: string }) {
  const toast = useToast();
  const findings = useApi<SoftwareFinding[]>(`/api/software-quality/findings?project_id=${projectId}&status=accepted`);
  const inProgress = useApi<SoftwareFinding[]>(`/api/software-quality/findings?project_id=${projectId}&status=in_progress`);
  const prompts = useApi<SoftwarePrompt[]>(`/api/software-quality/prompts?project_id=${projectId}`);
  const [selected, setSelected] = useState<string[]>([]);
  const [scope, setScope] = useState("");
  const [busy, setBusy] = useState(false);
  const [generated, setGenerated] = useState<SoftwarePrompt | null>(null);

  const candidates = useMemo(
    () => [...(findings.data ?? []), ...(inProgress.data ?? [])],
    [findings.data, inProgress.data],
  );

  function toggle(id: string) {
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  }

  async function generate() {
    if (!selected.length) {
      toast.push("error", "Select findings first", "Prompts are built from accepted findings only.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.post<SoftwarePrompt>("/api/software-quality/prompts", {
        project_id: projectId, finding_ids: selected, scope,
      });
      setGenerated(saved);
      toast.push("success", "Prompt saved", "Execution stays an explicit, separately authorized action.");
      prompts.reload();
    } catch (caught) {
      toast.push("error", "Could not generate prompt", errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      title="Improvement prompts"
      description="Scoped prompts for a local implementation agent, built from accepted findings with provenance. Generating never modifies code."
      actions={<Tag>{(prompts.data ?? []).length} saved</Tag>}
    >
      {(findings.loading || inProgress.loading) ? <LoadingBlock label="Loading accepted findings" compact /> : null}
      {candidates.length === 0 && !findings.loading ? (
        <p className="muted small">No accepted findings to build from. Accept findings in the queue above first.</p>
      ) : (
        candidates.map((finding) => (
          <label key={finding.id} className="checkbox" style={{ display: "block" }}>
            <input type="checkbox" checked={selected.includes(finding.id)} onChange={() => toggle(finding.id)} />{" "}
            <strong>[{finding.severity}] {finding.title}</strong>{" "}
            <span className="muted small">{finding.component}</span>
          </label>
        ))
      )}
      <div className="inline-form">
        <label className="muted small">
          Scope{" "}
          <input value={scope} onChange={(event) => setScope(event.target.value)} placeholder="bounded fix batch" aria-label="Prompt scope" size={30} />
        </label>
        <button className="button button-primary button-small" disabled={busy || !selected.length} onClick={() => void generate()}>
          {busy ? "Generating…" : "Generate implementation prompt"}
        </button>
      </div>
      {generated ? <CopyBlock text={generated.prompt} label="Copy implementation prompt" /> : null}
      <h4 className="writer-section-heading">Saved prompts</h4>
      {prompts.error ? <InlineError message={prompts.error.message} /> : null}
      {(prompts.data ?? []).map((item) => (
        <details className="history-list" key={item.id}>
          <summary>
            {timeAgo(item.created_at)} · {item.finding_ids.length} finding(s){item.scope ? ` · ${item.scope}` : ""}
          </summary>
          <CopyBlock text={item.prompt} label={`Copy prompt ${item.id.slice(0, 12)}`} />
        </details>
      ))}
      {(prompts.data ?? []).length === 0 && !prompts.loading ? (
        <p className="muted small">No saved prompts yet.</p>
      ) : null}
    </Section>
  );
}

export function SoftwareQualityPlaceholder() {
  return (
    <EmptyState
      title="Quality evaluation is unavailable"
      description="The software-quality service is not available."
    />
  );
}
