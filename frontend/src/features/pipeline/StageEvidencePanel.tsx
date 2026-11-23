import { useMemo } from "react";
import { useApi } from "../../api/useApi";
import type { PipelineEvidenceCell, PipelineStage } from "../../types/api";
import {
  ErrorState,
  KeyValue,
  LoadingBlock,
  PathText,
} from "../../components/ui";
import { Modal } from "../../components/Modal";

function shortDigest(value: string | null): string {
  if (!value) return "—";
  return value.length > 24 ? `${value.slice(0, 16)}…${value.slice(-6)}` : value;
}

function DetailValues({ cell }: { cell: PipelineEvidenceCell }) {
  const entries = useMemo(() => {
    const detail = cell.detail ?? {};
    return Object.entries(detail).filter(
      ([, value]) =>
        value === null ||
        typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean",
    ) as Array<[string, string | number | boolean | null]>;
  }, [cell]);
  if (!entries.length) return null;
  return (
    <dl className="kv-list">
      {entries.map(([key, value]) => (
        <KeyValue key={key} label={key.replace(/_/g, " ")}>
          <span className="muted">{String(value)}</span>
        </KeyValue>
      ))}
    </dl>
  );
}

export function StageEvidencePanel({
  projectId,
  bookTitle,
  chapterId,
  stage,
  onClose,
}: {
  projectId: string;
  bookTitle: string;
  chapterId: string;
  stage: PipelineStage;
  onClose: () => void;
}) {
  const detailQuery = useApi<{
    project_id: string;
    stage: PipelineStage;
    cells: PipelineEvidenceCell[];
    diagnostics?: string;
  }>(`/api/pipeline/books/${projectId}/stages/${stage.stage_id}`);
  const cell = detailQuery.data?.cells.find((item) => item.chapter_id === chapterId) ?? null;

  return (
    <Modal
      wide
      eyebrow={`${bookTitle} · ${chapterId}`}
      title={`${stage.name} evidence`}
      onClose={onClose}
      footer={
        <span className="muted small">
          Analysis execution is not available in this view — execution arrives with M3.
        </span>
      }
    >
      {detailQuery.loading && !detailQuery.data ? (
        <LoadingBlock label="Reading stage evidence…" />
      ) : null}
      {detailQuery.error ? (
        <ErrorState message={detailQuery.error.message} onRetry={detailQuery.reload} />
      ) : null}
      {detailQuery.data && !cell ? (
        <ErrorState
          message={`No ${stage.name} evidence is projected for ${chapterId}. The chapter may be new, the stage may not apply, or the source may be unavailable.`}
          onRetry={detailQuery.reload}
        />
      ) : null}
      {cell ? (
        <div className="stack">
          <div className="inline-meta" role="group" aria-label="Result and freshness">
            <span className="eyebrow">Result</span>
            <span className={`pipe-badge pipe-tone-${cell.result === "passed" ? "current" : cell.result === "failed" ? "failed" : cell.result === "pending" ? "unknown" : cell.result === "unavailable" ? "na" : "unknown"}`}>
              <span className="pipe-dot" aria-hidden="true" />
              {cell.result}
            </span>
            <span className="eyebrow">Freshness</span>
            <span className={`pipe-badge pipe-tone-${cell.freshness === "current" ? "current" : cell.freshness === "stale" ? "stale" : cell.freshness === "unknown" ? "unknown" : "na"}`}>
              <span className="pipe-dot" aria-hidden="true" />
              {cell.freshness}
            </span>
            <span className="muted small">provider: {cell.provider}</span>
          </div>

          {cell.result === "failed" && cell.freshness === "stale" ? (
            <p className="resume-blocker">
              Failed and stale are separate: this analysis reported a real failure, and its
              evidence also no longer matches the live manuscript. Refreshing the analysis is
              still required after the failure is understood.
            </p>
          ) : null}
          {cell.stage_id === "editing" && cell.freshness === "current" ? (
            <p className="muted small">
              A current editing audit does not mean the chapter was edited or improved — it
              means the stored audit evidence matches the live manuscript.
            </p>
          ) : null}

          <dl className="kv-list">
            <KeyValue label="Artifact">
              {cell.artifact_ref ? <PathText>{cell.artifact_ref}</PathText> : <span className="muted">No qualifying artifact</span>}
            </KeyValue>
            <KeyValue label="Digest contract">
              <span className="muted">{cell.digest_algorithm ?? "Not established in M1"}</span>
            </KeyValue>
            <KeyValue label="Stored digest">
              <code title={cell.stored_digest ?? undefined}>{shortDigest(cell.stored_digest)}</code>
            </KeyValue>
            <KeyValue label="Live digest">
              <code title={cell.live_digest ?? undefined}>{shortDigest(cell.live_digest)}</code>
            </KeyValue>
            <KeyValue label="Digests match">
              {cell.digest_match === null || cell.digest_match === undefined ? (
                <span className="muted">not comparable</span>
              ) : cell.digest_match ? (
                "yes — evidence is bound to the live source"
              ) : (
                "no — evidence predates the live source"
              )}
            </KeyValue>
            {cell.observed_at ? (
              <KeyValue label="Artifact observed">
                <span className="muted">{cell.observed_at}</span>
              </KeyValue>
            ) : null}
            {cell.executed_at ? (
              <KeyValue label="Analysis recorded">
                <span className="muted">{cell.executed_at}</span>
              </KeyValue>
            ) : null}
            {cell.stage_version ? (
              <KeyValue label="Stage version">
                <span className="muted">{cell.stage_version}</span>
              </KeyValue>
            ) : null}
          </dl>

          <div className="mini-block">
            <span>Diagnostics</span>
            <p>{cell.diagnostics || "No diagnostics recorded."}</p>
          </div>

          <DetailValues cell={cell} />

          <div className="mini-block">
            <span>Stage notes</span>
            <p className="muted small">{stage.freshness_method}</p>
            {stage.availability !== "implemented" ? (
              <p className="muted small">{stage.availability_reason}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
