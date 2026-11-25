import { useState } from "react";
import { Link } from "react-router-dom";
import { Play, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { Modal } from "../../components/Modal";
import { KeyValue, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";
import type {
  PipelineBookMatrix,
  PipelineStage,
  QualityCampaign,
  QualityDiscovery,
} from "../../types/api";

const DEFAULT_REVIEW_MODEL = "opencode-go/deepseek-v4.1-flash";
const ACTIVE_CAMPAIGN_STATES = ["pending", "running", "cancelling"];

function activeCampaignFor(
  campaigns: QualityCampaign[],
  kind: "prose" | "technical",
): QualityCampaign | null {
  return (
    campaigns.find(
      (campaign) =>
        (campaign.assessment_type ?? "prose") === kind &&
        ACTIVE_CAMPAIGN_STATES.includes(campaign.status),
    ) ?? null
  );
}

function chapterKey(chapterId: string): string {
  return chapterId.replace(/\.md$/, "");
}

function cellFor(
  pipeline: PipelineBookMatrix | null,
  stageId: string,
  chapterId: string,
) {
  return (
    pipeline?.matrix[stageId]?.find((cell) => cell.chapter_id === chapterKey(chapterId)) ??
    null
  );
}

function eligibilityTone(eligibility: string): string {
  if (eligibility === "current") return "accent";
  if (eligibility === "stale") return "danger";
  if (eligibility === "missing") return "default";
  return "default";
}

function executionLabel(stage: PipelineStage): string {
  if (stage.execution_class === "automatic") return "automatic";
  if (stage.availability === "implemented") return "governed";
  return stage.availability;
}

function executionReason(stage: PipelineStage): string {
  if (stage.execution_class === "automatic") {
    return stage.execution_note || "Allowlisted for automatic maintenance.";
  }
  if (stage.availability !== "implemented") {
    return stage.availability_reason || "Not available for execution.";
  }
  return stage.execution_note || "Explicit authorization is required.";
}

function campaignProgress(campaign: QualityCampaign): string {
  return `${campaign.completed} done · ${campaign.failed} failed · ${campaign.remaining} remaining`;
}

function EvidenceState({
  cell,
}: {
  cell: { result: string; freshness: string; has_evidence: boolean } | null;
}) {
  if (!cell) return <Tag>not projected</Tag>;
  if (!cell.has_evidence) {
    return <Tag>{cell.result === "unavailable" ? "unavailable" : "not run"}</Tag>;
  }
  if (cell.result === "unknown") {
    return (
      <>
        <Tag tone="accent">evidence present</Tag>
        <Tag>state unknown</Tag>
      </>
    );
  }
  return (
    <>
      <Tag>{cell.result}</Tag>
      <Tag>{cell.freshness}</Tag>
    </>
  );
}

export function ChapterRunDialog({
  projectId,
  chapter,
  campaigns,
  pipeline,
  pipelineLoading,
  onClose,
  onStarted,
}: {
  projectId: string;
  chapter: QualityDiscovery;
  campaigns: QualityCampaign[];
  pipeline: PipelineBookMatrix | null;
  pipelineLoading?: boolean;
  onClose: () => void;
  onStarted: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const proseCampaign = activeCampaignFor(campaigns, "prose");
  const technicalCampaign = activeCampaignFor(campaigns, "technical");
  const mriStage = pipeline?.stages.find((stage) => stage.stage_id === "mri") ?? null;
  const mriCell = cellFor(pipeline, "mri", chapter.chapter_id);
  const mriAvailable = Boolean(
    pipeline?.known && mriStage?.execution_class === "automatic" && mriCell?.applicable,
  );
  const otherStages = [...(pipeline?.stages ?? [])]
    .filter((stage) => stage.stage_id !== "mri")
    .sort((a, b) => a.presentation_order - b.presentation_order);
  const proseState = chapter.has_current ? "current" : chapter.eligibility;

  async function startCampaign(kind: "prose" | "technical") {
    setBusy(kind);
    try {
      const base =
        kind === "technical" ? "/api/technical/campaigns" : "/api/quality/campaigns";
      const created = await api.post<QualityCampaign>(base, {
        project_id: projectId,
        mode: "selected",
        chapters: [chapter.chapter_id],
        model: DEFAULT_REVIEW_MODEL,
        strategy: "direct",
      });
      await api.post(`${base}/${created.id}/run`);
      toast.push(
        "success",
        kind === "technical" ? "Technical analysis started" : "Prose review started",
        `${chapter.chapter_id} is queued. Progress is recorded in the Quality tab.`,
      );
      onStarted();
    } catch (caught) {
      toast.push(
        "error",
        kind === "technical" ? "Could not start technical analysis" : "Could not start prose review",
        errorMessage(caught),
      );
    } finally {
      setBusy(null);
    }
  }

  async function runMri() {
    setBusy("mri");
    try {
      const queued = await api.post<{ execution_id: string; status: string }>(
        "/api/pipeline/maintenance/retry",
        {
          project_id: projectId,
          chapter_id: chapterKey(chapter.chapter_id),
          stage_id: "mri",
        },
      );
      toast.push(
        "success",
        "MRI observation queued",
        `Execution ${queued.execution_id} will write Writer-owned evidence only.`,
      );
      onStarted();
    } catch (caught) {
      toast.push("error", "Could not queue MRI observation", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal
      wide
      eyebrow={`${chapter.chapter_id} · ${chapter.title ?? "untitled"}`}
      title="Run chapter work"
      onClose={onClose}
      footer={
        <span className="muted small">
          Runs record evidence. They never rewrite the chapter, and unrun stages stay visibly
          unrun rather than being inferred.
        </span>
      }
    >
      <div className="stack">
        <div className="inline-meta">
          <Tag tone={eligibilityTone(proseState)}>{proseState}</Tag>
          {chapter.current_model ? (
            <span className="muted small">current model: {chapter.current_model}</span>
          ) : null}
          <span className="muted small">revision {chapter.revision.slice(0, 12)}</span>
        </div>

        <article className="writer-decision-card">
          <div className="writer-decision-head">
            <strong>Prose review</strong>
            <Tag tone={eligibilityTone(proseState)}>{proseState}</Tag>
          </div>
          <p className="muted small">
            Model-backed review of the chapter&rsquo;s prose against the manuscript rubric. It
            records findings and scores without changing the manuscript.
          </p>
          {proseCampaign ? (
            <p className="muted small">
              A prose campaign is {proseCampaign.status}: {campaignProgress(proseCampaign)}
              {proseCampaign.current_chapter ? ` · now ${proseCampaign.current_chapter}` : ""}.
            </p>
          ) : null}
          <div className="button-row">
            <button
              type="button"
              className="button button-primary button-small"
              disabled={busy !== null || proseCampaign !== null}
              onClick={() => void startCampaign("prose")}
            >
              <Play size={13} />{" "}
              {busy === "prose"
                ? "Starting…"
                : chapter.has_current
                  ? "Re-run prose review"
                  : "Run prose review"}
            </button>
            {proseCampaign ? (
              <span className="muted small">Only one prose campaign may run at a time.</span>
            ) : null}
          </div>
        </article>

        <article className="writer-decision-card">
          <div className="writer-decision-head">
            <strong>Technical analysis</strong>
            <Tag>claims</Tag>
          </div>
          <p className="muted small">
            Extracts technical claims and verification obligations for this chapter. It writes
            assessment evidence and leaves the manuscript untouched.
          </p>
          {technicalCampaign ? (
            <p className="muted small">
              A technical campaign is {technicalCampaign.status}:{" "}
              {campaignProgress(technicalCampaign)}
              {technicalCampaign.current_chapter
                ? ` · now ${technicalCampaign.current_chapter}`
                : ""}
              .
            </p>
          ) : null}
          <div className="button-row">
            <button
              type="button"
              className="button button-secondary button-small"
              disabled={busy !== null || technicalCampaign !== null}
              onClick={() => void startCampaign("technical")}
            >
              <Play size={13} />{" "}
              {busy === "technical" ? "Starting…" : "Run technical analysis"}
            </button>
            {technicalCampaign ? (
              <span className="muted small">Only one technical campaign may run at a time.</span>
            ) : null}
          </div>
        </article>

        <article className="writer-decision-card">
          <div className="writer-decision-head">
            <strong>MRI observation</strong>
            <span className="inline-meta">
              {pipelineLoading ? <Tag>loading</Tag> : <EvidenceState cell={mriCell} />}
            </span>
          </div>
          <p className="muted small">
            Deterministic chapter observation. It writes Writer-owned MRI reports and does not
            modify the manuscript or call a model.
          </p>
          {pipelineLoading ? (
            <p className="muted small">Loading pipeline evidence…</p>
          ) : null}
          {!pipelineLoading && !pipeline ? (
            <p className="muted small">
              Production evidence is unavailable for this project, so the MRI action cannot be
              verified here.
            </p>
          ) : null}
          {pipeline && !mriStage?.execution_class ? (
            <p className="muted small">
              The stage registry did not report an execution class for MRI.
            </p>
          ) : null}
          {pipeline && mriStage && !mriCell ? (
            <p className="muted small">
              This chapter is not projected by the Writer registry, so MRI cannot be queued here.
            </p>
          ) : null}
          {pipeline && mriStage && mriCell && !mriCell.applicable ? (
            <p className="muted small">
              MRI is not applicable to this chapter in the current Writer registry.
            </p>
          ) : null}
          {pipeline && mriStage && mriCell?.applicable && !mriAvailable ? (
            <p className="muted small">{executionReason(mriStage)}</p>
          ) : null}
          <div className="button-row">
            <button
              type="button"
              className="button button-secondary button-small"
              disabled={busy !== null || !mriAvailable}
              onClick={() => void runMri()}
            >
              <RefreshCw size={13} />{" "}
              {busy === "mri"
                ? "Queueing…"
                : mriCell?.has_evidence
                  ? "Refresh MRI observation"
                  : "Run MRI observation"}
            </button>
          </div>
        </article>

        <article className="writer-decision-card">
          <div className="writer-decision-head">
            <strong>Review recorded findings</strong>
          </div>
          <p className="muted small">
            Accept, reject, defer, or investigate findings in the Quality workspace. Review
            decisions are recorded against the evaluated source revision.
          </p>
          <Link
            className="button button-secondary button-small"
            to={`/projects/${projectId}?tab=quality&qview=chapters&qchapter=${encodeURIComponent(
              chapter.chapter_id,
            )}`}
          >
            Open in Quality
          </Link>
        </article>

        <section aria-label="Production pipeline stages">
          <span className="eyebrow">Production pipeline</span>
          {pipelineLoading ? (
            <p className="muted small">Loading pipeline evidence…</p>
          ) : pipeline ? (
            <dl className="kv-list">
              {otherStages.map((stage) => {
                const cell = cellFor(pipeline, stage.stage_id, chapter.chapter_id);
                return (
                  <KeyValue key={stage.stage_id} label={stage.name}>
                    <span className="inline-meta">
                      {stage.availability === "implemented" ? (
                        <>
                          <EvidenceState cell={cell} />
                          <Tag>{executionLabel(stage)}</Tag>
                        </>
                      ) : (
                        <Tag>{stage.availability}</Tag>
                      )}
                    </span>
                    <span className="muted small" style={{ display: "block" }}>
                      {executionReason(stage)}
                    </span>
                  </KeyValue>
                );
              })}
            </dl>
          ) : (
            <p className="muted small">
              No pipeline projection is available. Registered stages and their evidence appear
              here once the book is known to the Writer registry.
            </p>
          )}
          <p className="muted small">
            Metadata, patterns, strengthening, editing, validation, and graph remain governed or
            unavailable here. Visual assets (SVG, Mermaid, tables) and text simplification are
            chapter-scoped Reading Room operations in ALIVE, not Mission evaluation stages, so
            they are not launched from this dialog.
          </p>
          <p className="muted small">
            Publication readiness is assessed for the whole book, not one chapter.{" "}
            <Link className="text-link" to={`/projects/${projectId}?tab=publishing`}>
              Open Publishing
            </Link>
            .
          </p>
        </section>
      </div>
    </Modal>
  );
}
