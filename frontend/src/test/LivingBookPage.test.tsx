import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { LivingBookPage } from "../pages/LivingBookPage";
import { json, mockFetch, renderRoute } from "./helpers";

function renderReader() {
  return renderRoute(
    <Routes>
      <Route path="/projects/:projectId/read" element={<LivingBookPage />} />
    </Routes>,
    "/projects/distillation/read",
  );
}

const chapter = {
  chapter_id: "01-chapter.md",
  path: "content/books/distillation/01-chapter.md",
  title: "What Is Knowledge Distillation?",
  order: 1,
  word_count: 420,
  sha256: "a".repeat(64),
  markdown:
    "# What Is Knowledge Distillation?\n\nThe teacher carries more than a hard label.\n\n## A second section\n\nA student rebuilds the signal.\n",
  front_matter: { title: "What Is Knowledge Distillation?" },
  sections: [
    { level: 1, title: "What Is Knowledge Distillation?", line: 1 },
    { level: 2, title: "A second section", line: 5 },
  ],
  figures: [],
  status: "current",
};

function status(state = "ready") {
  return {
    project_id: "distillation",
    project_name: "Distillation",
    book_title: "Distillation From First Principles",
    manuscript_root: "C:\\books\\distillation\\content\\books\\distillation",
    available: state !== "unavailable",
    state,
    detail: state === "unavailable" ? "ALIVE is not running." : "",
    alive_url: "http://127.0.0.1:8000",
    quality: {
      schema: "book-quality-context.v1",
      coverage: {
        prose: { status: "CURRENT", current: 1, total: 1, rubric: "manuscript-prose-v1" },
        writer: { status: "NOT_RUN", detail: "No Writer report." },
        technical: { status: "NOT_RUN", claims_total: 0 },
        publication: { status: "NOT_RUN" },
        artifact_load: { status: "NOT_RUN" },
      },
      summary: {
        chapters_total: 1,
        chapters_current: 1,
        overall_min: 3,
        overall_max: 3,
        weakest_chapters: [{ chapter_id: "01-chapter.md", overall: 3 }],
      },
      limitations: ["Prose scores are single-run model judgments."],
    },
    candidates: [
      {
        kind: "repository",
        path: "C:\\books\\distillation",
        manuscript_root: "C:\\books\\distillation\\content\\books\\distillation",
        available: true,
        recommended: true,
        detail: "Whole book repository.",
      },
      {
        kind: "manuscript",
        path: "C:\\books\\distillation\\content\\books\\distillation",
        manuscript_root: "C:\\books\\distillation\\content\\books\\distillation",
        available: true,
        recommended: false,
        detail: "Only the manuscript chapter folder.",
      },
    ],
    book:
      state === "not_connected" || state === "unavailable"
        ? null
        : {
            id: "book-1",
            title: "Distillation From First Principles",
            label: "Distillation",
            workspace_id: "workspace-1",
            source_root: "C:\\books\\distillation",
            manuscript_root: "C:\\books\\distillation\\content\\books\\distillation",
            manuscript_relative: "content/books/distillation",
            ready: true,
            error: null,
            source: { status: "current", current: true },
            chapters: [chapter],
            chapter_count: 1,
            reading: null,
            annotations: [],
            notes: [],
            conversations: [],
            model: { name: "muse-spark-1.3-contributor", transport: "pi", ready: true },
            limitations: [],
          },
  };
}

const quality = {
  schema: "book-quality-context.v1",
  coverage: {
    prose: { status: "CURRENT", current: 1, total: 1, rubric: "manuscript-prose-v1" },
    writer: { status: "NOT_RUN" },
    technical: { status: "NOT_RUN", claims_total: 0 },
    publication: { status: "NOT_RUN" },
    artifact_load: { status: "NOT_RUN" },
  },
  measures: [
    {
      id: "mission.prose.manuscript-prose-v1",
      kind: "model_judgment",
      scope: "chapter",
      status: "CURRENT",
      label: "Manuscript prose evaluation",
      rubric: "manuscript-prose-v1",
      model: "model",
      value: {
        overall: 3,
        dimensions: {
          clarity: { score: 3, evidence: "A teacher signal.", evidence_validated: false },
          economy: { score: 2, evidence: "Compressed.", evidence_validated: false },
        },
      },
      limitations: ["Single-run model judgment."],
    },
  ],
  summary: {
    chapters_total: 1,
    chapters_current: 1,
    overall_min: 3,
    overall_max: 3,
    weakest_chapters: [{ chapter_id: "01-chapter.md", overall: 3 }],
  },
  limitations: ["Prose scores are single-run model judgments."],
};

describe("LivingBookPage", () => {
  it("renders the manuscript, quality evidence and a grounded companion answer", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/living-book/projects/distillation" && method === "GET")
        return json(status());
      if (path.endsWith("/chapters/01-chapter.md") && method === "GET") return json(chapter);
      if (path.endsWith("/quality") && method === "GET") return json(quality);
      if (path.endsWith("/notes/01-chapter.md") && method === "GET") return json(null);
      if (path.endsWith("/ask") && method === "POST") {
        return json({
          id: "conversation-1",
          title: "Distillation · What Is Knowledge Distillation?",
          messages: [
            {
              id: "message-1",
              role: "assistant",
              content: "The chapter separates transfer from imitation.",
              status: "completed",
              citations: [
                {
                  document_id: "content/books/distillation/01-chapter.md",
                  quote: "The teacher carries more than a hard label.",
                },
              ],
            },
          ],
          calls: [],
          answer: "The chapter separates transfer from imitation.",
          citations: [
            {
              document_id: "content/books/distillation/01-chapter.md",
              quote: "The teacher carries more than a hard label.",
            },
          ],
          status: "completed",
          session: { id: "consent-1", state: "approved", max_calls: 100, usage: { calls: 1 } },
        });
      }
      return json(null);
    });
    const user = userEvent.setup();
    renderReader();

    expect(
      await screen.findByRole("heading", { name: "Distillation From First Principles" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: "What Is Knowledge Distillation?",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/The teacher carries more than a hard label/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Quality$/i }));
    expect(await screen.findByText("3 / 5")).toBeInTheDocument();
    expect(screen.getAllByText("NOT RUN").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /^Ask$/i }));
    const composer = screen.getByPlaceholderText(/Ask about this chapter/i);
    await user.type(composer, "What is this chapter establishing?");
    await user.click(screen.getByRole("button", { name: /^Send$/i }));

    await waitFor(() =>
      expect(screen.getByText("The chapter separates transfer from imitation.")).toBeInTheDocument(),
    );
    expect(screen.getByText(/1 citation/)).toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/ask"))).toBe(true);
  });

  it("shows the explicit source approval flow when the book is not connected", async () => {
    mockFetch(({ path, method }) => {
      if (path === "/api/living-book/projects/distillation" && method === "GET")
        return json(status("not_connected"));
      return json(null);
    });
    renderReader();

    expect(await screen.findByText("Connect this book")).toBeInTheDocument();
    expect(screen.getByText("Whole book repository · recommended")).toBeInTheDocument();
    const connect = screen.getByRole("button", { name: /Connect and approve/i });
    expect(connect).toBeDisabled();
  });

  it("states plainly when ALIVE is unavailable", async () => {
    mockFetch(({ path, method }) => {
      if (path === "/api/living-book/projects/distillation" && method === "GET")
        return json(status("unavailable"));
      return json(null);
    });
    renderReader();
    expect(await screen.findByText("ALIVE is not running")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Applications/i })).toBeInTheDocument();
  });
});

  it("runs the narrow improvement journey without writing the book", async () => {
    const preview = {
      schema: "living-book-improvement-preview.v1",
      generated_at: new Date().toISOString(),
      eligible: true,
      blockers: [],
      warnings: [],
      focus: "economy",
      project_id: "distillation",
      book_id: "book-1",
      workspace_id: "workspace-1",
      chapter: {
        chapter_id: "01-chapter.md",
        path: "content/books/distillation/01-chapter.md",
        title: "What Is Knowledge Distillation?",
        sha256: "a".repeat(64),
        word_count: 420,
        status: "current",
      },
      source: { binding_ref: "binding-1", approval_ref: "approval-1", capture_ref: "capture-1", status: "current" },
      model: { name: "muse-spark-1.3-contributor", transport: "pi", ready: true },
      quality: {},
      evidence: {
        ref: "mission:quality:prose:01",
        kind: "model_judgment",
        status: "CURRENT",
        measure_id: "mission.prose.manuscript-prose-v1",
        rubric: "manuscript-prose-v1",
        observed_at: "2026-11-16T21:47:33Z",
        chapter_revision: "a".repeat(64),
        quote: "Compressed.",
        quote_validated: false,
        value: { overall: 3, economy: 2 },
        limitations: ["Single-run model judgment."],
      },
      excluded: [{ ref: "mission:quality:technical", label: "Technical claims", status: "NOT_RUN", reason: "NOT_RUN is missing evidence, not zero." }],
      brief: "Improve economy in the chapter without dropping technical claims.",
      criteria_sha256: "d".repeat(64),
      intent: {},
      intent_sha256: "e".repeat(64),
      plan: {
        mode: "sections",
        workflow_version: 806,
        workflow_definition_id: "definition-1",
        workflow_definition_sha256: "f".repeat(64),
        workflow_binding_sha256: "1".repeat(64),
        model_calls: 8,
        output_tokens: 12288,
        wall_seconds: 900,
        section_count: 6,
        plan_sha256: "2".repeat(64),
      },
      experience: {
        eligible_candidates: 1,
        items: [
          {
            ref: "improvement:old-1",
            decision: "accepted",
            quality: { status: "evaluation_failed", quality_unverified: true },
            owner_comment: "economy: retained, evaluation failed",
          },
        ],
        selected: [],
        abstained: false,
      },
      authority: { read: "Approved source", model: "Separate admission", action: "Proposal only", write: "None" },
      notice: "No manuscript file is changed.",
      use_experience: false,
    };
    const pending = {
      schema: "living-book-improvement-run.v1",
      book_id: "book-1",
      workspace_id: "workspace-1",
      run_id: "run-1",
      status: "COMPLETED",
      terminal: true,
      status_label: "Proposal retained; awaiting author decision",
      reason: null,
      workflow: { name: "chapter-improvement", version: 806 },
      budget: { max_model_calls: 8, max_output_tokens: 12288 },
      usage: { calls: 8, tokens: 1000 },
      stages: [{ stage_id: "review", state: "COMPLETED" }],
      chapter_path: "content/books/distillation/01-chapter.md",
      provenance: "complete",
      missing: [],
      original: { path: "content/books/distillation/01-chapter.md", sha256: "a".repeat(64) },
      proposal: {
        artifact_id: "artifact-1",
        artifact_sha256: "b".repeat(64),
        sha256: "c".repeat(64),
        markdown: "# What Is Knowledge Distillation?\n\nA tighter signal.\n",
        coverage: "complete",
        limitations: "",
      },
      change: {
        differs: true,
        lines_added: 1,
        lines_removed: 1,
        blocks: [],
        unified: ["--- original", "+++ proposal", "@@ -1,1 +1,1 @@", "-old", "+new"],
        truncated: false,
      },
      evaluation: { status: "evaluated", kind: "model_assessment", verdict: "promising", note: "An AI assessment, not owner acceptance." },
      source_version: { status: "current" },
      state: { decision: "pending" },
      history: [],
      experience: { enabled: false },
      notice: "No manuscript file is changed.",
      applied: false,
    };
    const accepted = {
      ...pending,
      status_label: "Accepted",
      state: { decision: "accepted", decided_at: "2026-11-19T22:00:00Z" },
      history: [{ decision: "accepted", recorded_at: "2026-11-19T22:00:00Z" }],
    };
    let decided = false;
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/living-book/projects/distillation" && method === "GET")
        return json(status());
      if (path.endsWith("/chapters/01-chapter.md") && method === "GET") return json(chapter);
      if (path.endsWith("/quality") && method === "GET") return json(quality);
      if (path.endsWith("/notes/01-chapter.md") && method === "GET") return json(null);
      if (path.includes("/improvement/preview") && method === "GET") return json(preview);
      if (path.endsWith("/improvement") && method === "POST") return json(pending);
      if (path.endsWith("/improvement/run-1") && method === "GET")
        return json(decided ? accepted : pending);
      if (path.endsWith("/improvement/run-1/decision") && method === "POST") {
        decided = true;
        return json(accepted);
      }
      return json(null);
    });
    const user = userEvent.setup();
    renderReader();

    await screen.findByRole("heading", { level: 2, name: "What Is Knowledge Distillation?" });
    await user.click(screen.getByRole("button", { name: /^Improve$/i }));
    expect(
      await screen.findByRole("heading", { level: 3, name: "Improve this chapter" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Improve economy in the chapter/)).toBeInTheDocument();
    expect(screen.getByText(/v806/)).toBeInTheDocument();
    expect(screen.getByText(/quality unverified/)).toBeInTheDocument();
    expect(screen.getByText(/No manuscript file is changed/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Start improvement/i }));
    expect(
      await screen.findByRole("heading", {
        name: /Proposal retained; awaiting author decision/,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/model_assessment/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/No manuscript file is changed/).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Accept proposal/i }));
    expect((await screen.findAllByText("Accepted")).length).toBeGreaterThan(0);
    expect(calls.some((call) => call.path.endsWith("/decision"))).toBe(true);
    expect(calls.some((call) => call.method === "POST" && call.path.endsWith("/improvement"))).toBe(true);
  });
