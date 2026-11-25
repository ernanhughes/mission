import { useMemo, useState } from "react";
import { useApi } from "../../api/useApi";
import { api, apiPath, errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import { Modal } from "../../components/Modal";
import type {
  WorkClaim,
  WorkClaimVerification,
  WorkConfirmation,
  WorkEnvelope,
  WorkEpisodeDetail,
  WorkEpisodeEvaluation,
  WorkEpisodeRow,
  WorkEvidenceLink,
  WorkFinding,
  WorkOverview,
  WorkRequirement,
  WorkRequirementAssessment,
} from "../../types/api";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  Section,
  Tag,
} from "../../components/ui";
import { assessmentTone, completionTone, formatTime, kindLabel, verdictTone } from "./labels";

type CompletionFilter = "" | "complete" | "partial" | "incomplete" | "blocked" | "unknown";
type KindFilter = "" | "task" | "stage" | "programme" | "chain" | "cluster" | "unresolved";

export function EpisodesView({ projectKey }: { projectKey: string }) {
  const [kind, setKind] = useState<KindFilter>("");
  const [completion, setCompletion] = useState<CompletionFilter>("");
  const [onlyFindings, setOnlyFindings] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const query = useMemo(
    () =>
      apiPath("/api/work-evaluation/overview", {
        project_key: projectKey || undefined,
        limit: 100,
      }),
    [projectKey],
  );
  const overview = useApi<WorkOverview>(query);

  if (overview.loading) return <LoadingBlock label="Loading work episodes" />;
  if (overview.error)
    return <ErrorState message={`Work episodes unavailable: ${overview.error.message}`} onRetry={overview.reload} />;

  const rows = (overview.data?.episodes ?? []).filter((row) => {
    if (kind && row.kind !== kind) return false;
    if (completion === "unknown" && row.completion !== null) return false;
    if (completion && completion !== "unknown" && row.completion !== completion) return false;
    if (onlyFindings && row.open_findings === 0) return false;
    return true;
  });

  return (
    <div>
      <div className="toolbar">
        <select aria-label="Filter by kind" value={kind} onChange={(e) => setKind(e.target.value as KindFilter)}>
          <option value="">All kinds</option>
          <option value="task">Task</option>
          <option value="stage">Stage</option>
          <option value="programme">Programme</option>
          <option value="chain">Session chain</option>
          <option value="cluster">Linked work</option>
          <option value="unresolved">Unresolved</option>
        </select>
        <select
          aria-label="Filter by completion"
          value={completion}
          onChange={(e) => setCompletion(e.target.value as CompletionFilter)}
        >
          <option value="">All states</option>
          <option value="complete">Complete · verified</option>
          <option value="partial">Partial</option>
          <option value="incomplete">Incomplete</option>
          <option value="blocked">Blocked</option>
          <option value="unknown">Unevaluated</option>
        </select>
        <label>
          <input type="checkbox" checked={onlyFindings} onChange={(e) => setOnlyFindings(e.target.checked)} />{" "}
          Only with findings
        </label>
        <span className="toolbar-count">{rows.length} episode(s)</span>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No episodes match"
          description="Adjust the filters, or run observation and reconstruction first. An empty result means no records, not finished work."
        />
      ) : (
        <ul className="activity-feed">
          {rows.map((row) => (
            <EpisodeRow key={row.id} row={row} onOpen={() => setDetailId(row.id)} />
          ))}
        </ul>
      )}

      {detailId ? <EpisodeDetailModal episodeId={detailId} onClose={() => setDetailId(null)} /> : null}
    </div>
  );
}

export function EpisodeRow({ row, onOpen }: { row: WorkEpisodeRow; onOpen?: () => void }) {
  const tone = completionTone(row.completion);
  return (
    <li>
      <span className="activity-marker type-user" aria-hidden="true" />
      <div className="activity-entry">
        <div className="activity-head">
          {onOpen ? (
            <button className="link-button" onClick={onOpen} title={row.id}>
              <strong>{row.title || row.id}</strong>
            </button>
          ) : (
            <strong>{row.title || row.id}</strong>
          )}
          <Tag tone={tone.tone}>{tone.label}</Tag>
          {row.status === "candidate" ? <Tag>Conditional</Tag> : null}
        </div>
        <div className="activity-meta">
          <span>{kindLabel(row.kind)}</span>
          <span>Updated {formatTime(row.last_seen_ms)}</span>
          {row.open_findings > 0 ? <span>{row.open_findings} finding(s)</span> : <span>No open findings</span>}
          {!row.evaluated ? <span>Unevaluated</span> : null}
        </div>
        {onOpen ? (
          <div className="activity-actions">
            <button className="button button-ghost button-small" onClick={onOpen}>
              Inspect episode
            </button>
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function EpisodeDetailModal({ episodeId, onClose }: { episodeId: string; onClose: () => void }) {
  const toast = useToast();
  const [detailTab, setDetailTab] = useState<"summary" | "requirements" | "changes" | "evidence" | "evaluation" | "envelope" | "history">(
    "summary",
  );
  const detail = useApi<WorkEpisodeDetail>(apiPath(`/api/work-episodes/${encodeURIComponent(episodeId)}`));
  const evaluationPacket = useApi<{
    assessment: WorkEpisodeEvaluation | null;
    requirements: WorkRequirementAssessment[];
    claims: WorkClaimVerification[];
    findings: WorkFinding[];
  }>(apiPath(`/api/work-evaluation/episodes/${encodeURIComponent(episodeId)}`));
  const evaluation = evaluationPacket.data?.assessment ?? null;
  const packetRequirements = evaluationPacket.data?.requirements ?? [];
  const packetClaims = evaluationPacket.data?.claims ?? [];
  const requirements = useApi<{ requirements: WorkRequirement[] }>(
    apiPath("/api/work-intent/requirements", { episode_id: episodeId, limit: 200 }),
  );
  const claims = useApi<{ claims: WorkClaim[] }>(
    apiPath("/api/work-intent/claims", { episode_id: episodeId, limit: 200 }),
  );

  async function copyId() {
    try {
      await navigator.clipboard.writeText(episodeId);
      toast.push("success", "Copied", "Episode identifier copied.");
    } catch (caught) {
      toast.push("error", "Copy failed", errorMessage(caught));
    }
  }

  return (
    <Modal title={detail.data?.title || episodeId} onClose={onClose} wide>
      <div className="toolbar" role="tablist" aria-label="Episode detail">
        {(["summary", "requirements", "changes", "evidence", "evaluation", "envelope", "history"] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={detailTab === t}
            className={`button button-small ${detailTab === t ? "button-primary" : "button-ghost"}`}
            onClick={() => setDetailTab(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
        <span className="toolbar-count">
          <button className="link-button" onClick={() => void copyId()}>
            {episodeId}
          </button>
        </span>
      </div>

      {detail.loading || evaluationPacket.loading ? <LoadingBlock label="Loading episode" /> : null}
      {detail.error ? <InlineError message={`Episode unavailable: ${detail.error.message}`} /> : null}

      {detailTab === "summary" && detail.data ? (
        <SummaryTab episodeId={episodeId} detail={detail.data} evaluation={evaluation} />
      ) : null}
      {detailTab === "requirements" ? (
        <RequirementsTab
          episodeId={episodeId}
          loading={requirements.loading || evaluationPacket.loading}
          error={requirements.error?.message ?? evaluationPacket.error?.message ?? null}
          items={requirements.data?.requirements ?? []}
          verdicts={packetRequirements}
          onChanged={() => { requirements.reload(); }}
        />
      ) : null}
      {detailTab === "changes" ? (
        <ChangesTab detail={detail.data ?? null} />
      ) : null}
      {detailTab === "evidence" ? (
        <EvidenceTab
          evaluation={evaluation}
          claims={claims.data?.claims ?? []}
          verifications={packetClaims}
          claimsError={claims.error?.message ?? null}
        />
      ) : null}
      {detailTab === "evaluation" ? (
        <EvaluationTab evaluation={evaluation} error={evaluationPacket.error?.message ?? null} />
      ) : null}
      {detailTab === "envelope" ? (
        <EnvelopeTab episodeId={episodeId} />
      ) : null}
      {detailTab === "history" ? (
        <HistoryTab episodeId={episodeId} version={detail.data?.version ?? null} />
      ) : null}
    </Modal>
  );
}

function SummaryTab({
  episodeId,
  detail,
  evaluation,
}: {
  episodeId: string;
  detail: WorkEpisodeDetail;
  evaluation: WorkEpisodeEvaluation | null;
}) {
  const completion = evaluation ? completionTone(evaluation.completion.verdict) : null;
  const findings = useApi<{ findings: WorkFinding[] }>(
    apiPath("/api/work-evaluation/findings", { episode_id: episodeId, limit: 50 }),
  );
  const top = (findings.data?.findings ?? []).slice(0, 3);
  return (
    <div>
      <Section title="Objective">
        <p>{detail.title || "Untitled work"}</p>
        <div className="activity-meta">
          <span>{kindLabel(detail.kind)}</span>
          <span>First seen {formatTime(detail.first_seen_ms)}</span>
          <span>Last activity {formatTime(detail.last_seen_ms)}</span>
          {completion ? (
            <Tag tone={completion.tone}>{completion.label}</Tag>
          ) : (
            <Tag>Unevaluated</Tag>
          )}
          {detail.status === "candidate" ? <Tag>Conditionally accepted</Tag> : null}
        </div>
      </Section>
      <Section title="Most important actions">
        {findings.loading ? (
          <LoadingBlock compact label="Loading findings" />
        ) : top.length === 0 ? (
          <p className="muted">No open findings recorded for this episode (recorded findings only; absence of a record is not proof of completeness).</p>
        ) : (
          <ul className="activity-feed">
            {top.map((f) => (
              <li key={f.id}>
                <span className="activity-marker type-user" aria-hidden="true" />
                <div className="activity-entry">
                  <div className="activity-head">
                    <strong>{f.title}</strong>
                    <Tag tone={f.severity === "major" ? "danger" : "default"}>{f.severity}</Tag>
                  </div>
                  <div className="activity-meta">
                    <span>{f.kind}</span>
                    <span>{f.status}</span>
                  </div>
                  {f.next_action ? <p className="muted">{f.next_action}</p> : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function RequirementsTab({
  episodeId,
  loading,
  error,
  items,
  verdicts,
  onChanged,
}: {
  episodeId: string;
  loading: boolean;
  error: string | null;
  items: WorkRequirement[];
  verdicts: WorkRequirementAssessment[];
  onChanged: () => void;
}) {
  const [reviewer, setReviewer] = useState("");
  const confirmations = useApi<{ confirmations: WorkConfirmation[] }>(
    apiPath("/api/work-intent/confirmations", { episode_id: episodeId }),
  );
  if (loading) return <LoadingBlock label="Loading requirements" />;
  if (error) return <InlineError message={error} />;
  if (items.length === 0)
    return (
      <EmptyState
        title="No requirements extracted"
        description="The objective has not been decomposed into assessable requirements, or extraction is pending."
      />
    );
  const byReq = new Map(verdicts.map((v) => [v.requirement_id, v]));
  const decided = new Map<string, WorkConfirmation>();
  for (const c of confirmations.data?.confirmations ?? []) {
    if (!decided.has(c.requirement_id)) decided.set(c.requirement_id, c);
  }
  return (
    <div>
      <div className="toolbar">
        <input
          className="input input-small"
          style={{ maxWidth: 220 }}
          placeholder="Reviewer name (required to decide)"
          aria-label="Reviewer name for requirement decisions"
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
        />
      </div>
      <ul className="activity-feed">
        {items.map((req) => (
          <RequirementRow
            key={req.id}
            req={req}
            assessed={byReq.get(req.id)}
            decision={decided.get(req.id)}
            reviewer={reviewer}
            onChanged={() => { onChanged(); confirmations.reload(); }}
          />
        ))}
      </ul>
    </div>
  );
}

function RequirementRow({
  req,
  assessed,
  decision,
  reviewer,
  onChanged,
}: {
  req: WorkRequirement;
  assessed: WorkRequirementAssessment | undefined;
  decision: WorkConfirmation | undefined;
  reviewer: string;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [amendOpen, setAmendOpen] = useState(false);
  const [amendText, setAmendText] = useState(req.text);
  const toast = useToast();
  const authLabel = req.authority === "ambiguous" ? "Ambiguous — abstained" : req.authority;
  const tone = assessed ? verdictTone(assessed.verdict) : null;

  async function decide(kind: string, text?: string) {
    if (!reviewer.trim()) {
      toast.push("error", "Enter a reviewer name first — decisions are never anonymous.");
      return;
    }
    setBusy(true);
    try {
      const out = await api.post<{ status: string; error?: string }>(
        "/api/work-intent/confirmations",
        { requirement_id: req.id, decision: kind, reviewer: reviewer.trim(), amended_text: text ?? "" },
      );
      if (out.status !== "completed") throw new Error(out.error ?? "rejected");
      toast.push("success", `Requirement ${kind}`);
      onChanged();
    } catch (caught) {
      toast.push("error", `Decision failed: ${errorMessage(caught)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li>
      <span className="activity-marker type-user" aria-hidden="true" />
      <div className="activity-entry">
        <div className="activity-head">
          <strong>{req.text}</strong>
          <Tag tone={req.mandatory ? "danger" : "default"}>{req.mandatory ? "Mandatory" : "Optional"}</Tag>
          {tone ? <Tag tone={tone.tone}>{tone.label}</Tag> : <Tag>Unevaluated</Tag>}
          {decision ? <Tag>Human: {decision.decision} by {decision.reviewer}</Tag> : null}
        </div>
        <div className="activity-meta">
          <span>Authority: {authLabel}</span>
          <span>State: {req.state}</span>
          <span>Kind: {req.kind}</span>
          <span>v{req.version}</span>
        </div>
        {assessed ? (
          <div className="activity-meta">
            <span>Evidence: {(assessed.evidence_refs ?? []).length} ref(s)</span>
            <span>{assessed.method}</span>
          </div>
        ) : null}
        <div className="activity-actions">
          {(["confirm", "reject", "defer", "insufficient"] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              className="button button-ghost button-small"
              disabled={busy}
              onClick={() => void decide(kind)}
            >
              {kind === "insufficient" ? "Insufficient evidence" : kind[0].toUpperCase() + kind.slice(1)}
            </button>
          ))}
          <button
            type="button"
            className="button button-ghost button-small"
            disabled={busy}
            onClick={() => setAmendOpen((v) => !v)}
          >
            Amend
          </button>
        </div>
        {amendOpen ? (
          <div>
            <textarea
              className="input"
              rows={3}
              style={{ width: "100%" }}
              aria-label="Amended requirement text"
              value={amendText}
              onChange={(e) => setAmendText(e.target.value)}
            />
            <div className="activity-actions">
              <button
                type="button"
                className="button button-small"
                disabled={busy || amendText.trim().length < 12}
                onClick={() => void decide("amend", amendText.trim()).then(() => setAmendOpen(false))}
              >
                Save amendment (creates v{req.version + 1})
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </li>
  );
}

function ChangesTab({ detail }: { detail: WorkEpisodeDetail | null }) {
  if (!detail)
    return <EmptyState title="No episode loaded" description="Episode references are unavailable." />;
  const commits = (detail.associations ?? []).filter((a) => a.assoc_type === "commit");
  const repos = [...new Set((detail.associations ?? []).filter((a) => a.assoc_type === "repository").map((a) => a.target_ref))];
  if (commits.length === 0 && repos.length === 0)
    return (
      <EmptyState
        title="No repository changes associated"
        description="Legitimate non-code work has no commits. Absence of commits is not evidence of absence of work."
      />
    );
  return (
    <div>
      {repos.length > 0 ? (
        <Section title="Repositories">
          <ul className="activity-feed">
            {repos.map((r) => (
              <li key={r}>
                <span className="activity-marker type-user" aria-hidden="true" />
                <div className="activity-entry">
                  <div className="activity-head">
                    <strong>{r}</strong>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
      <Section title="Associated commits">
        <ul className="activity-feed">
          {commits.map((c) => (
            <li key={c.target_ref}>
              <span className="activity-marker type-user" aria-hidden="true" />
              <div className="activity-entry">
                <div className="activity-head">
                  <strong>{c.target_ref}</strong>
                  <Tag tone={c.method === "explicit" ? "accent" : "default"}>{c.method}</Tag>
                </div>
                <div className="activity-meta">
                  <span>Confidence: {c.confidence}</span>
                  <span>{c.reason}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function EvidenceTab({
  evaluation,
  claims,
  verifications,
  claimsError,
}: {
  evaluation: WorkEpisodeEvaluation | null;
  claims: WorkClaim[];
  verifications: WorkClaimVerification[];
  claimsError: string | null;
}) {
  const byClaim = new Map(verifications.map((v) => [v.claim_id, v]));
  return (
    <div>
      <Section title="Participant claims vs verified outcomes">
        <p className="muted">
          Claims below are assertions from the work record — not independently verified results unless
          marked verified.
        </p>
        {claimsError ? <InlineError message={claimsError} /> : null}
        {claims.length === 0 ? (
          <p className="muted">No claims recorded for this episode.</p>
        ) : (
          <ul className="activity-feed">
            {claims.slice(0, 30).map((c) => {
              const verified = byClaim.get(c.id);
              const tone = verified ? verdictTone(verified.verdict) : null;
              return (
                <li key={c.id}>
                  <span className="activity-marker type-user" aria-hidden="true" />
                  <div className="activity-entry">
                    <div className="activity-head">
                      <strong>{c.text.slice(0, 200)}</strong>
                      {tone ? <Tag tone={tone.tone}>{tone.label}</Tag> : <Tag>Unverified assertion</Tag>}
                    </div>
                    <div className="activity-meta">
                      <span>Claimant: {c.claimant}</span>
                      <span>Scope: {c.scope || "—"}</span>
                      {c.qualified ? <span>Qualified</span> : null}
                      <span>{c.evidence_available ? "Evidence linked" : "Evidence outstanding"}</span>
                      {verified ? <span>Method: {verified.method}</span> : null}
                    </div>
                    {verified && verified.rationale ? (
                      <p className="muted">{verified.rationale.slice(0, 300)}</p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
      {evaluation ? (
        <Section title="Verification states">
          <div className="activity-meta">
            <span>Execution: {evaluation.execution.verdict}</span>
            <span>Outcome: {evaluation.outcome.verdict}</span>
            <span>Completion: {evaluation.completion.verdict}</span>
          </div>
        </Section>
      ) : null}
    </div>
  );
}

function EvaluationTab({
  evaluation,
  error,
}: {
  evaluation: WorkEpisodeEvaluation | null;
  error: string | null;
}) {
  if (error) return <InlineError message={error} />;
  if (!evaluation)
    return (
      <EmptyState
        title="Not evaluated"
        description="No evaluation exists for this episode. Unevaluated does not mean incomplete."
      />
    );
  const exec = assessmentTone(evaluation.execution.verdict);
  const out = assessmentTone(evaluation.outcome.verdict);
  const comp = completionTone(evaluation.completion.verdict);
  return (
    <div>
      <Section title="Execution quality">
        <Tag tone={exec.tone}>{exec.label}</Tag>
        <p className="muted">{evaluation.execution.rationale || "No rationale recorded."}</p>
      </Section>
      <Section title="Outcome quality">
        <Tag tone={out.tone}>{out.label}</Tag>
        <p className="muted">{evaluation.outcome.rationale || "No rationale recorded."}</p>
      </Section>
      <Section title="Completion">
        <Tag tone={comp.tone}>{comp.label}</Tag>
        <p className="muted">{evaluation.completion.rationale || "No rationale recorded."}</p>
      </Section>
      <Section title="Evaluation provenance">
        <div className="activity-meta">
          <span>Evaluator: {evaluation.evaluator || "—"}</span>
          <span>Rubric: {evaluation.rubric_version || "—"}</span>
        </div>
      </Section>
    </div>
  );
}

function EnvelopeTab({ episodeId }: { episodeId: string }) {
  const envelopes = useApi<{ envelopes: WorkEnvelope[] }>(
    apiPath("/api/work-envelopes", { episode_id: episodeId }),
  );
  if (envelopes.loading) return <LoadingBlock label="Loading work envelope" />;
  if (envelopes.error)
    return <InlineError message={`Envelope unavailable: ${envelopes.error.message}`} />;
  const rows = envelopes.data?.envelopes ?? [];
  if (rows.length === 0)
    return (
      <EmptyState
        title="No prospective envelope"
        description="This episode was reconstructed retrospectively. Register an envelope via POST /api/work-envelopes to bind authorized intent before future execution."
      />
    );
  return (
    <ul className="activity-feed">
      {rows.map((e) => (
        <li key={e.id}>
          <span className="activity-marker type-user" aria-hidden="true" />
          <div className="activity-entry">
            <div className="activity-head">
              <strong>{e.id}</strong>
              <Tag>{e.status}</Tag>
              <Tag>v{e.version}</Tag>
            </div>
            <div className="activity-meta">
              <span>{e.schema_version}</span>
              <span>{e.programme_id} / {e.stage_id}</span>
              <span>digest {e.commission_digest.slice(0, 12)}…</span>
            </div>
            <div className="activity-meta">
              <span>Objective: {e.objective_ref}</span>
              <span>Requirements: {(e.requirement_refs ?? []).map((r) => typeof r === "string" ? r : `${r.id}@v${r.v}`).join(", ") || "(none)"}</span>
            </div>
            <div className="activity-meta">
              <span>Repos: {e.repositories.join(", ") || "(none)"}</span>
              <span>Policy: {e.acceptance_policy_ref}</span>
            </div>
            {e.authorization_ref ? <p className="muted">Authorized: {e.authorization_ref}</p> : null}
            {e.originating_findings.length > 0 ? <p className="muted">From findings: {e.originating_findings.join(", ")}</p> : null}
            {e.supersedes ? <p className="muted">Supersedes: {e.supersedes}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

function HistoryTab({ episodeId, version }: { episodeId: string; version: number | null }) {
  void episodeId;
  return (
    <div>
      <p className="muted">
        Historical assessments are preserved as new rows; the current view always shows the latest.
        {version != null ? ` Current reconstruction version: ${version}.` : ""}
      </p>
      <p className="muted">Assessment history browsing is a W6 continuous-evaluation concern.</p>
    </div>
  );
}
