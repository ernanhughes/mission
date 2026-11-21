import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import { EmptyState, InlineError, LoadingBlock, Tag } from "../../components/ui";
import { BookMarkdown } from "./BookMarkdown";
import type { LivingBookRepresentation, LivingBookRepresentationTask } from "../../types/living-book";

const TASKS: Array<{ id: LivingBookRepresentationTask; label: string; hint: string }> = [
  { id: "explain", label: "Explain", hint: "Reveal the distinctions already present" },
  { id: "relationships", label: "Relationships", hint: "Show directed connections" },
  { id: "diagram", label: "Diagram", hint: "Re-express as a mermaid flowchart" },
  { id: "compare", label: "Compare", hint: "Re-express as a comparison table" },
  { id: "assumptions", label: "Assumptions", hint: "Surface conditions and exceptions" },
];

function standingTone(standing?: string): "accent" | "warning" | "danger" | "default" {
  if (standing === "verified") return "accent";
  if (standing === "attention") return "warning";
  if (standing === "refused") return "danger";
  return "default";
}

export function ExplorePanel({
  projectId,
  chapterId,
  selection,
  conversationId,
  onAskAbout,
}: {
  projectId: string;
  chapterId: string;
  selection: string;
  conversationId: string | null;
  onAskAbout: (prompt: string, conversationId: string | null) => void;
}) {
  const toast = useToast();
  const [task, setTask] = useState<LivingBookRepresentationTask>("explain");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [record, setRecord] = useState<LivingBookRepresentation | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);

  async function explore() {
    if (!selection || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<LivingBookRepresentation>(
        `/api/living-book/projects/${projectId}/representations`,
        {
          chapter_id: chapterId,
          task,
          quote: selection.slice(0, 4000),
          conversation_id: conversationId,
          idempotency_key:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `explore-${Date.now()}`,
        },
      );
      setRecord(result);
      setShowOriginal(false);
      if (result.verification?.standing === "refused") {
        toast.push("info", "Left unchanged", result.verification.reason || "The transformation was refused.");
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!record) return;
    try {
      const updated = await api.post<LivingBookRepresentation>(
        `/api/living-book/projects/${projectId}/representations/${encodeURIComponent(record.id)}/reject`,
        {},
      );
      setRecord(updated);
      toast.push("success", "Representation rejected", "The original passage is unchanged.");
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  if (!selection) {
    return (
      <EmptyState
        title="Nothing selected"
        description="Select a passage in the chapter, then choose how ALIVE should represent it. Every view stays tied to its exact source."
      />
    );
  }

  const verification = record?.verification;
  return (
    <div className="living-explore">
      <span className="eyebrow">Explore this passage</span>
      <blockquote className="living-explore-source">{selection.slice(0, 400)}</blockquote>
      <div className="living-explore-tasks">
        {TASKS.map((item) => (
          <button
            key={item.id}
            className={task === item.id ? "is-current" : ""}
            onClick={() => setTask(item.id)}
            title={item.hint}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="form-actions">
        <button className="button button-primary button-small" onClick={() => void explore()} disabled={busy}>
          {busy ? "Representing…" : "Represent this passage"}
        </button>
      </div>
      <InlineError message={error} />
      {busy ? <LoadingBlock label="ALIVE is building the representation" compact /> : null}
      {record ? (
        <article className="living-representation">
          <div className="living-representation-head">
            <Tag tone={standingTone(verification?.standing)}>{verification?.standing ?? "unknown"}</Tag>
            <span className="muted small">{record.transformation_class}</span>
            {record.model?.fixture ? <Tag tone="warning">fixture · no model call</Tag> : null}
            {record.rejected ? <Tag tone="default">rejected</Tag> : null}
          </div>
          {verification?.reason ? <p className="muted small">{verification.reason}</p> : null}
          {showOriginal ? (
            <blockquote>{record.passage?.text ?? selection}</blockquote>
          ) : record.rendering?.content ? (
            <BookMarkdown content={record.rendering.content} projectId={projectId} />
          ) : (
            <p className="muted small">No rendering retained. The original passage is shown.</p>
          )}
          {record.added?.length ? (
            <details className="living-representation-added">
              <summary>Added explanation (not from the source)</summary>
              {record.added.map((item, index) => (
                <p key={index} className="muted small">
                  {item}
                </p>
              ))}
            </details>
          ) : null}
          {record.citations?.length ? (
            <details>
              <summary>{record.citations.length} source span(s)</summary>
              {record.citations.map((citation, index) => (
                <blockquote key={index}>{citation.quote}</blockquote>
              ))}
            </details>
          ) : null}
          {verification?.attention?.length ? (
            <p className="warn-text small">Needs review: {verification.attention.join(", ")}</p>
          ) : null}
          <div className="inline-meta">
            <code>{record.source?.chapter_sha256?.slice(0, 12)}</code>
            <span className="muted small">passage {record.passage?.sha256?.slice(0, 12)}</span>
          </div>
          <div className="form-actions">
            <button className="button button-secondary button-small" onClick={() => setShowOriginal((value) => !value)}>
              {showOriginal ? "Show representation" : "Show original"}
            </button>
            <button
              className="button button-secondary button-small"
              disabled={!record.conversation_id}
              onClick={() =>
                onAskAbout(
                  `Why does this ${record.task} view represent the passage this way? Challenge one element against its source span.`,
                  record.conversation_id ?? null,
                )
              }
            >
              Question this view
            </button>
            {!record.rejected ? (
              <button className="button button-secondary button-small" onClick={() => void reject()}>
                Reject
              </button>
            ) : null}
          </div>
        </article>
      ) : null}
    </div>
  );
}
