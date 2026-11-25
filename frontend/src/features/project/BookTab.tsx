import { useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Play } from "lucide-react";
import { LivingBookCard } from "../living-book/LivingBookCard";
import { EmptyState, Section, SimpleStatusBadge, Tag } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { timeAgo } from "../../lib/format";
import { ChapterRunDialog } from "./ChapterRunDialog";
import type {
  PipelineBookMatrix,
  ProjectDetail,
  QualityCampaign,
  QualityDiscovery,
} from "../../types/api";

const ACTIVE_CAMPAIGN_STATES = ["pending", "running", "cancelling"];
const DEFAULT_REVIEW_MODEL = "opencode-go/deepseek-v4.1-flash";

export function BookTab({
  projectId,
  data,
  discovery,
  onRefresh,
}: {
  projectId: string;
  data: ProjectDetail;
  discovery: QualityDiscovery[] | null;
  onRefresh?: () => void;
}) {
  const living = useApi<{ book_title?: string; detail?: string; state?: string; book?: { chapters?: Array<{ chapter_id: string; title?: string | null }> } | null }>(
    `/api/living-book/projects/${projectId}`,
  );
  const toast = useToast();
  const campaigns = useApi<QualityCampaign[]>(
    `/api/quality/campaigns?project_id=${projectId}`,
    { pollMs: 15000 },
  );
  const pipeline = useApi<PipelineBookMatrix>(
    data.book ? `/api/pipeline/books/${projectId}` : null,
    { pollMs: 60000 },
  );
  const [runChapter, setRunChapter] = useState<QualityDiscovery | null>(null);
  const [campaignBusy, setCampaignBusy] = useState(false);

  if (!data.book && data.kind !== "book") {
    return (
      <Section title="Book" description="Manuscript workspace for book projects.">
        <EmptyState
          title="Not a book project"
          description="This project has no manuscript attached. Book tools are hidden rather than shown empty."
        />
      </Section>
    );
  }

  const chapters = discovery ?? [];
  const book = data.book;
  const activeProse =
    (campaigns.data ?? []).find(
      (campaign) =>
        (campaign.assessment_type ?? "prose") === "prose" &&
        ACTIVE_CAMPAIGN_STATES.includes(campaign.status),
    ) ?? null;
  const pendingChapters = chapters.filter((chapter) => !chapter.has_current);

  function refreshAfterRun() {
    campaigns.reload();
    pipeline.reload();
    onRefresh?.();
  }

  async function evaluateMissing() {
    if (activeProse || campaignBusy || pendingChapters.length === 0) return;
    if (
      !window.confirm(
        `Start a prose review campaign for ${pendingChapters.length} chapter${
          pendingChapters.length === 1 ? "" : "s"
        }? This is model-backed work and may incur cost.`,
      )
    ) {
      return;
    }
    setCampaignBusy(true);
    try {
      const created = await api.post<QualityCampaign>("/api/quality/campaigns", {
        project_id: projectId,
        mode: "missing",
        model: DEFAULT_REVIEW_MODEL,
        strategy: "direct",
      });
      await api.post(`/api/quality/campaigns/${created.id}/run`);
      toast.push(
        "success",
        "Evaluation campaign started",
        `${created.chapter_selection.length} chapters queued. Progress is recorded in the Quality tab.`,
      );
      refreshAfterRun();
    } catch (caught) {
      toast.push("error", "Could not start evaluation campaign", errorMessage(caught));
    } finally {
      setCampaignBusy(false);
    }
  }

  return (
    <div>
      <LivingBookCard projectId={projectId} />
      <Section
        title="Reading"
        description="Continue where the reading stopped. The Reading Room remains the canonical reading experience."
        actions={
          <Link className="button button-primary button-small" to={`/projects/${projectId}/read`}>
            <BookOpen size={14} /> Open reading room
          </Link>
        }
      >
        {living.loading ? <p className="muted small">Loading reading progress…</p> : null}
        {living.data?.book ? (
          <p className="muted small">
            {living.data.book.chapters?.length ?? chapters.length} chapters inventoried · state{" "}
            {living.data.state ?? "unknown"}
          </p>
        ) : (
          <p className="muted small">{living.data?.detail ?? "Reading progress loads with the Living Book."}</p>
        )}
        {book ? (
          <div className="inline-meta">
            <SimpleStatusBadge state={book.status} />
            <span className="muted small">{book.quality_review_state.replace(/_/g, " ")}</span>
            {book.next_action ? <span className="muted small">Next: {book.next_action}</span> : null}
          </div>
        ) : (
          <p className="muted small">
            No book record linked yet. Chapter inventory below reflects discovered manuscript sources, not a
            reconciled book count.
          </p>
        )}
      </Section>

      <Section
        title="Manuscript and chapter inventory"
        description="Discovered chapters. Counts are reported as observed, never reconciled across pillars. Runs record evidence; they never edit the manuscript."
        actions={
          <div className="button-row">
            {chapters.length ? <Tag>{chapters.length} chapters</Tag> : null}
            {activeProse ? (
              <Tag tone="accent">
                Prose review {activeProse.completed}/{activeProse.total}
              </Tag>
            ) : pendingChapters.length ? (
              <button
                type="button"
                className="button button-primary button-small"
                disabled={campaignBusy}
                onClick={() => void evaluateMissing()}
              >
                {campaignBusy
                  ? "Starting…"
                  : `Evaluate prose (${pendingChapters.length})`}
              </button>
            ) : null}
          </div>
        }
      >
        {campaigns.error ? (
          <p className="muted small">
            Campaign status is unavailable: {campaigns.error.message}. Runs may still be
            available.
          </p>
        ) : null}
        {chapters.length === 0 ? (
          <EmptyState
            title="No chapters discovered"
            description="Run quality discovery or link the manuscript root. An empty inventory is unknown, not zero evidence."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Chapter</th>
                  <th>Title</th>
                  <th>Evaluation</th>
                  <th>Run</th>
                </tr>
              </thead>
              <tbody>
                {chapters.map((row) => (
                  <tr key={row.chapter_id}>
                    <td>{row.chapter_id}</td>
                    <td className="muted small">{row.title ?? "untitled"}</td>
                    <td>
                      {row.has_current ? (
                        <Tag tone="accent">current</Tag>
                      ) : (
                        <Tag>{row.eligibility}</Tag>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="button button-secondary button-small"
                        aria-label={`Run chapter work for ${row.chapter_id}`}
                        onClick={() => setRunChapter(row)}
                      >
                        <Play size={13} /> Run…
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {runChapter ? (
        <ChapterRunDialog
          projectId={projectId}
          chapter={runChapter}
          campaigns={campaigns.data ?? []}
          pipeline={pipeline.data}
          pipelineLoading={pipeline.loading}
          onClose={() => setRunChapter(null)}
          onStarted={refreshAfterRun}
        />
      ) : null}

      <Section title="Book outcomes" description="Outcome relationships for this manuscript.">
        {data.outcomes.length ? (
          <ul className="plain-list">
            {data.outcomes.map((outcome) => (
              <li key={outcome.id}>
                <strong>{outcome.name}</strong> · <span className="muted small">{outcome.status}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">No outcome relationship configured.</p>
        )}
      </Section>

      {data.notes ? (
        <Section title="Manuscript notes" description="Author notes and manuscript context.">
          <p className="small">{data.notes}</p>
          <p className="muted small">Last activity {timeAgo(data.last_activity_at)}</p>
        </Section>
      ) : null}
    </div>
  );
}
