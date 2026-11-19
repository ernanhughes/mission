import { RefreshCw, Sparkles, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { InlineError, LoadingBlock, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { formatDateTime } from "../../lib/format";
import type {
  LivingBookImprovementPreview,
  LivingBookImprovementRun,
} from "../../types/living-book";

function key(prefix: string): string {
  return `${prefix}-${
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}`
  }`;
}

function tone(status: string): string {
  const value = status.toLowerCase();
  if (["completed", "current", "accepted", "promising"].includes(value)) return "success";
  if (["failed", "rejected", "not_improved", "changed", "evaluation_failed"].includes(value))
    return "danger";
  if (["running", "queued", "pending", "mixed", "undetermined"].includes(value)) return "warning";
  return "default";
}

function score(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

function authorityLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function ImprovementPanel({
  projectId,
  chapterId,
  onSourceRefreshed,
}: {
  projectId: string;
  chapterId: string;
  onSourceRefreshed?: () => void;
}) {
  const toast = useToast();
  const [useExperience, setUseExperience] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [acknowledge, setAcknowledge] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const previewPath = `/api/living-book/projects/${projectId}/improvement/preview?chapter_id=${encodeURIComponent(
    chapterId,
  )}&focus=economy&use_experience=${useExperience}`;
  const preview = useApi<LivingBookImprovementPreview>(previewPath);
  const run = useApi<LivingBookImprovementRun>(
    runId
      ? `/api/living-book/projects/${projectId}/improvement/${encodeURIComponent(runId)}`
      : null,
    { pollMs: runId ? 2500 : 0 },
  );

  useEffect(() => {
    setRunId(null);
    setRunError(null);
    setComment("");
    setAcknowledge(false);
    setUseExperience(false);
  }, [chapterId]);

  async function start() {
    const value = preview.data;
    if (!value?.eligible || !value.plan || busy) return;
    setBusy(true);
    setRunError(null);
    try {
      const result = await api.post<LivingBookImprovementRun>(
        `/api/living-book/projects/${projectId}/improvement`,
        {
          chapter_id: chapterId,
          focus: "economy",
          intent_sha256: value.intent_sha256,
          plan_sha256: value.plan.plan_sha256,
          criteria: value.brief,
          model: value.model.name,
          use_experience: useExperience,
          confirmed: true,
          idempotency_key: key("mission-02b"),
        },
      );
      setRunId(result.run_id);
      toast.push(
        "success",
        "Improvement started",
        "ALIVE is retaining a proposal; the book is not being changed.",
      );
    } catch (caught) {
      setRunError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "accepted" | "rejected") {
    const value = run.data;
    if (!value?.proposal || busy) return;
    setBusy(true);
    setRunError(null);
    try {
      await api.post(
        `/api/living-book/projects/${projectId}/improvement/${encodeURIComponent(
          value.run_id,
        )}/decision`,
        {
          decision,
          proposal_sha256: value.proposal.sha256,
          comment,
          acknowledge_earlier_version: acknowledge,
          idempotency_key: key("mission-02b-decision"),
        },
      );
      run.reload();
      preview.reload();
      setComment("");
      toast.push(
        "success",
        decision === "accepted" ? "Proposal accepted" : "Proposal rejected",
        "The decision is retained. No manuscript file was changed.",
      );
    } catch (caught) {
      setRunError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function refreshSource() {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await api.post(`/api/living-book/projects/${projectId}/refresh`);
      toast.push(
        "success",
        "Book source refreshed",
        "The exact source and chapter are now current. Preview again before running.",
      );
      onSourceRefreshed?.();
      preview.reload();
    } catch (caught) {
      toast.push("error", "Could not refresh the book source", errorMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }

  if (runId) {
    return (
      <ImprovementRunView
        run={run.data}
        loading={run.loading}
        error={run.error ? errorMessage(run.error) : runError}
        busy={busy}
        comment={comment}
        acknowledge={acknowledge}
        onComment={setComment}
        onAcknowledge={setAcknowledge}
        onDecide={decide}
        onAnother={() => {
          setRunId(null);
          setUseExperience(true);
          preview.reload();
        }}
        onBack={() => setRunId(null)}
        onReload={run.reload}
      />
    );
  }

  if (preview.loading && !preview.data) {
    return <LoadingBlock label="Preparing the improvement preview" compact />;
  }
  if (preview.error) {
    return (
      <div className="living-improve">
        <InlineError message={errorMessage(preview.error)} />
        <button className="button button-secondary button-small" onClick={preview.reload}>
          <RefreshCw size={14} /> Try again
        </button>
      </div>
    );
  }
  const value = preview.data;
  if (!value) return null;
  const stale = value.blockers.some((item) => item.code === "source_attachment_stale");

  return (
    <div className="living-improve">
      <div className="living-improve-head">
        <div>
          <span className="eyebrow">Author mode</span>
          <h3>Improve this chapter</h3>
          <p className="muted small">
            Turn the current economy evidence into one retained proposal. ALIVE reviews,
            improves and evaluates; it does not write the book.
          </p>
        </div>
        <Tag tone={value.eligible ? "success" : "warning"}>
          {value.eligible ? "Ready to run" : "Blocked"}
        </Tag>
      </div>

      {value.blockers.length ? (
        <div className="living-improve-blockers" role="alert">
          <strong>This chapter cannot be improved yet.</strong>
          <ul>
            {value.blockers.map((item) => (
              <li key={item.code}>
                <code>{item.code}</code> — {item.detail}
              </li>
            ))}
          </ul>
          {stale ? (
            <button
              className="button button-primary button-small"
              onClick={() => void refreshSource()}
              disabled={refreshing}
            >
              <RefreshCw size={14} /> {refreshing ? "Refreshing…" : "Refresh book source"}
            </button>
          ) : null}
        </div>
      ) : null}

      {value.warnings.length ? (
        <p className="muted small">{value.warnings.join(" ")}</p>
      ) : null}

      <div className="living-improve-grid">
        <section className="living-improve-card">
          <span className="eyebrow">Evidence used</span>
          {value.evidence ? (
            <>
              <div className="living-improve-row">
                <strong>{value.evidence.measure_id}</strong>
                <Tag tone={tone(value.evidence.status)}>{value.evidence.status}</Tag>
              </div>
              <p className="muted small">
                {value.evidence.rubric} · observed{" "}
                {value.evidence.observed_at
                  ? formatDateTime(value.evidence.observed_at)
                  : "unknown"}{" "}
                · overall {score(value.evidence.value?.overall)} · economy{" "}
                {score(value.evidence.value?.economy)}
              </p>
              {value.evidence.quote ? (
                <blockquote>
                  {value.evidence.quote}
                  <small>
                    {value.evidence.quote_validated
                      ? "Quoted evidence was validated."
                      : "Quoted evidence is not independently verified."}
                  </small>
                </blockquote>
              ) : null}
              {value.evidence.limitations?.length ? (
                <ul className="living-improve-limits">
                  {value.evidence.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <p className="muted small">No current economy evidence.</p>
          )}
          <details>
            <summary>Editorial brief sent as criteria</summary>
            <p className="living-improve-brief">{value.brief || "No brief."}</p>
          </details>
        </section>

        <section className="living-improve-card">
          <span className="eyebrow">Plan and budget</span>
          {value.plan ? (
            <dl className="living-improve-facts">
              <div>
                <dt>Mode</dt>
                <dd>{value.plan.mode}</dd>
              </div>
              <div>
                <dt>Workflow</dt>
                <dd>v{value.plan.workflow_version}</dd>
              </div>
              <div>
                <dt>Sections</dt>
                <dd>{value.plan.section_count ?? "—"}</dd>
              </div>
              <div>
                <dt>Model calls</dt>
                <dd>{value.plan.model_calls}</dd>
              </div>
              <div>
                <dt>Output tokens</dt>
                <dd>{value.plan.output_tokens.toLocaleString("en-US")}</dd>
              </div>
              <div>
                <dt>Wall time</dt>
                <dd>{Math.round(value.plan.wall_seconds / 60)} min</dd>
              </div>
            </dl>
          ) : (
            <p className="muted small">No executable plan.</p>
          )}
          {value.plan ? (
            <code className="living-improve-hash">plan {value.plan.plan_sha256.slice(0, 16)}…</code>
          ) : null}
          <p className="muted small">
            Source {value.source.mode || "unknown"} · {value.source.status || "unknown"} · chapter{" "}
            {value.chapter.sha256.slice(0, 12)}…
          </p>
          <p className="muted small">
            Model {value.model.name} · {value.model.transport} ·{" "}
            {value.model.ready ? "ready" : "unavailable"}
          </p>
        </section>

        <section className="living-improve-card">
          <span className="eyebrow">Authority</span>
          <dl className="living-improve-authority">
            {Object.entries(value.authority).map(([name, text]) => (
              <div key={name}>
                <dt>{authorityLabel(name)}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
          <p className="muted small">
            Starting the run authorizes the workflow admission and model budget above. It does
            not authorize a manuscript write.
          </p>
        </section>

        <section className="living-improve-card">
          <span className="eyebrow">Earlier decisions</span>
          <p className="muted small">
            {value.experience?.eligible_candidates
              ? `${value.experience.eligible_candidates} eligible item(s).`
              : "No eligible earlier decision. The first run starts without experience."}
          </p>
          <label className="living-improve-check">
            <input
              type="checkbox"
              checked={useExperience}
              onChange={(event) => setUseExperience(event.target.checked)}
            />
            Use an eligible prior decision as experience
          </label>
          {value.experience?.items?.length ? (
            <ul className="living-improve-experience">
              {value.experience.items.slice(0, 3).map((item: Record<string, any>) => (
                <li key={item.ref || item.improvement_id}>
                  <strong>{item.decision}</strong>
                  {item.quality?.status ? (
                    <Tag tone={tone(item.quality.status)}>{item.quality.status}</Tag>
                  ) : null}
                  {item.quality?.quality_unverified ? (
                    <span className="muted small"> quality unverified</span>
                  ) : null}
                  {item.owner_comment ? <span> — {item.owner_comment}</span> : null}
                  <code>{item.ref || item.improvement_id}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">Nothing will be supplied unless it becomes eligible.</p>
          )}
          {value.experience?.promotion?.eligible === false ? (
            <p className="muted small">
              No item here is a proven lesson. Owner acceptance is context; quality evidence is
              attached but not promoted.
            </p>
          ) : null}
        </section>
      </div>

      {value.recent_improvements?.length ? (
        <section className="living-improve-card">
          <span className="eyebrow">Recent runs for this chapter</span>
          <ul className="living-improve-history">
            {value.recent_improvements.map((item) => (
              <li key={item.run_id}>
                <button className="text-link" onClick={() => setRunId(item.run_id)}>
                  Open run
                </button>
                <span> {item.decision || "pending"}</span>
                {item.evaluation_status ? (
                  <span className="muted small"> · evaluation {item.evaluation_status}</span>
                ) : null}
                {item.verdict ? <span className="muted small"> · {item.verdict}</span> : null}
                {item.created_at ? (
                  <span className="muted small"> · {formatDateTime(item.created_at)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="living-improve-excluded">
        <span className="eyebrow">Not used</span>
        <div>
          {value.excluded.map((item) => (
            <Tag key={item.ref} tone="default">
              {item.label || item.ref}: {item.status}
            </Tag>
          ))}
        </div>
      </div>

      <div className="living-improve-actions">
        <button
          className="button button-primary"
          onClick={() => void start()}
          disabled={!value.eligible || !value.plan || busy}
        >
          <Wrench size={15} /> {busy ? "Starting…" : "Start improvement"}
        </button>
        <span className="muted small">
          One retained proposal. No file is written. The author decides afterward.
        </span>
      </div>
      <p className="muted small">{value.notice}</p>
      {runError ? <InlineError message={runError} /> : null}
    </div>
  );
}

function ImprovementRunView({
  run,
  loading,
  error,
  busy,
  comment,
  acknowledge,
  onComment,
  onAcknowledge,
  onDecide,
  onAnother,
  onBack,
  onReload,
}: {
  run: LivingBookImprovementRun | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  comment: string;
  acknowledge: boolean;
  onComment: (value: string) => void;
  onAcknowledge: (value: boolean) => void;
  onDecide: (decision: "accepted" | "rejected") => void;
  onAnother: () => void;
  onBack: () => void;
  onReload: () => void;
}) {
  if (loading && !run) return <LoadingBlock label="Loading the improvement run" compact />;
  if (error) {
    return (
      <div className="living-improve">
        <InlineError message={error} />
        <button className="button button-secondary button-small" onClick={onReload}>
          <RefreshCw size={14} /> Reload
        </button>
      </div>
    );
  }
  if (!run) return null;
  const proposal = run.proposal;
  const pending = (run.state?.decision || "pending") === "pending";
  const earlier = run.source_version?.status !== "current";

  return (
    <div className="living-improve">
      <div className="living-improve-head">
        <div>
          <span className="eyebrow">Improvement run</span>
          <h3>{run.status_label}</h3>
          <p className="muted small">
            <code>{run.run_id}</code> · {run.workflow?.name || "chapter-improvement"} v
            {run.workflow?.version || "—"}
          </p>
        </div>
        <div className="living-improve-run-head-actions">
          <button className="text-link" onClick={onBack}>
            Back to preview
          </button>
          <Tag tone={tone(run.status)}>{run.status}</Tag>
        </div>
      </div>

      <div className="living-improve-run-meta">
        <span className="muted small">
          {run.usage?.calls ?? 0} model calls · {run.usage?.tokens ?? 0} tokens
        </span>
        <span className="muted small">
          Budget {run.budget?.max_model_calls ?? "—"} calls ·{" "}
          {run.budget?.max_output_tokens ?? "—"} output tokens
        </span>
      </div>

      <section className="living-improve-card">
        <span className="eyebrow">Stages</span>
        <ol className="living-improve-stages">
          {run.stages.map((stage) => (
            <li key={stage.stage_id}>
              <Tag tone={tone(stage.state)}>{stage.state}</Tag>
              <span>{stage.stage_id}</span>
              {stage.error_category ? <code>{stage.error_category}</code> : null}
            </li>
          ))}
        </ol>
        {run.reason ? <p className="muted small">{run.reason}</p> : null}
      </section>

      {proposal ? (
        <section className="living-improve-card">
          <span className="eyebrow">Retained proposal</span>
          <div className="living-improve-row">
            <strong>{run.status_label}</strong>
            <Tag tone="success">proposal {proposal.sha256.slice(0, 12)}…</Tag>
          </div>
          <p className="muted small">
            Coverage: {proposal.coverage || "unknown"} ·{" "}
            {run.change
              ? `${run.change.lines_added} added, ${run.change.lines_removed} removed`
              : "No diff"}
          </p>
          {proposal.limitations ? (
            <p className="muted small">Limitations: {proposal.limitations}</p>
          ) : null}
          {run.change?.unified?.length ? (
            <div className="living-improve-diff" aria-label="Proposal diff">
              {run.change.unified.slice(0, 400).map((line, index) => (
                <div
                  key={`${index}-${line.slice(0, 20)}`}
                  className={
                    line.startsWith("+")
                      ? "is-added"
                      : line.startsWith("-")
                        ? "is-removed"
                        : line.startsWith("@@")
                          ? "is-hunk"
                          : ""
                  }
                >
                  {line || " "}
                </div>
              ))}
              {run.change.truncated ? (
                <p className="muted small">The diff is truncated in this view.</p>
              ) : null}
            </div>
          ) : null}
          <details>
            <summary>Full proposed Markdown</summary>
            <pre className="living-improve-proposal">{proposal.markdown}</pre>
          </details>
        </section>
      ) : (
        <section className="living-improve-card">
          <span className="eyebrow">Proposal</span>
          <p className="muted small">
            No complete proposal is retained yet. This is not a failure claim; inspect the stages
            and run reason.
          </p>
        </section>
      )}

      {run.evaluation ? (
        <section className="living-improve-card">
          <span className="eyebrow">Evaluation</span>
          <div className="living-improve-row">
            <strong>{run.evaluation.verdict || run.evaluation.status}</strong>
            <Tag tone={tone(run.evaluation.verdict || run.evaluation.status)}>
              {run.evaluation.kind || run.evaluation.status}
            </Tag>
          </div>
          <p className="muted small">
            {run.evaluation.note ||
              (run.evaluation.status === "evaluation_failed"
                ? "The evaluation did not complete. No quality claim is made."
                : "An AI assessment, not an objective verdict and not owner acceptance.")}
          </p>
          {run.evaluation.assessment ? <p>{run.evaluation.assessment}</p> : null}
          {run.evaluation.limitations ? (
            <p className="muted small">{run.evaluation.limitations}</p>
          ) : null}
        </section>
      ) : null}

      <section className="living-improve-card">
        <span className="eyebrow">Source at review</span>
        <div className="living-improve-row">
          <strong>{run.source_version?.status || "unknown"}</strong>
          {earlier ? <Tag tone="warning">earlier or unverifiable</Tag> : <Tag tone="success">current</Tag>}
        </div>
        <p className="muted small">
          Original {run.original.sha256?.slice(0, 16)}… · chapter {run.chapter_path}
        </p>
        {earlier ? (
          <p className="muted small">
            This proposal was generated from an earlier or unverifiable chapter version. Accepting
            it requires an explicit acknowledgement.
          </p>
        ) : null}
      </section>

      <section className="living-improve-card">
        <span className="eyebrow">Decision</span>
        {pending && proposal ? (
          <>
            <label className="living-improve-field">
              Comment (optional)
              <textarea
                value={comment}
                onChange={(event) => onComment(event.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="What did you judge, and why?"
              />
            </label>
            {earlier ? (
              <label className="living-improve-check">
                <input
                  type="checkbox"
                  checked={acknowledge}
                  onChange={(event) => onAcknowledge(event.target.checked)}
                />
                I am accepting this proposal against the earlier chapter version shown above.
              </label>
            ) : null}
            <div className="living-improve-actions">
              <button
                className="button button-primary"
                onClick={() => void onDecide("accepted")}
                disabled={busy || (earlier && !acknowledge)}
              >
                Accept proposal
              </button>
              <button
                className="button button-secondary"
                onClick={() => void onDecide("rejected")}
                disabled={busy}
              >
                Reject proposal
              </button>
            </div>
            <p className="muted small">{run.notice}</p>
          </>
        ) : (
          <>
            <div className="living-improve-row">
              <strong>{run.state?.decision || "pending"}</strong>
              {run.state?.decided_at ? (
                <span className="muted small">{formatDateTime(run.state.decided_at)}</span>
              ) : null}
            </div>
            <p className="muted small">{run.notice}</p>
            <div className="living-improve-actions">
              <button className="button button-secondary button-small" onClick={onAnother}>
                <Sparkles size={14} /> Prepare another run
              </button>
              <button className="button button-secondary button-small" onClick={onReload}>
                <RefreshCw size={14} /> Reload
              </button>
            </div>
          </>
        )}
      </section>

      {run.history?.length > 1 ? (
        <section className="living-improve-card">
          <span className="eyebrow">Decision history</span>
          <ul className="living-improve-history">
            {run.history.map((item, index) => (
              <li key={item.event_id || index}>
                <strong>{item.decision}</strong>
                {item.comment ? <span> — {item.comment}</span> : null}
                {item.recorded_at ? (
                  <span className="muted small"> {formatDateTime(item.recorded_at)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
