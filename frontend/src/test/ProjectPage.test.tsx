import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectPage } from "../pages/ProjectPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeAdapter, makeProjectDetail, makeTask, makeWorkRecord } from "./fixtures";

function renderProject() {
  return renderRoute(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectPage />} />
    </Routes>,
    "/projects/math",
  );
}

describe("ProjectPage", () => {
  it("saves a checkpoint and completes a task through the API", async () => {
    const detail = makeProjectDetail({
      id: "math",
      name: "Math",
      tasks: [
        makeTask({
          id: "task-math",
          project_id: "math",
          project_name: "Math",
          title: "Inspect proof obligations",
        }),
      ],
      recommendations: [],
      adapters: [
        makeAdapter({
          available: false,
          detail: "Work has no verified read-only opportunity export configured.",
          capabilities: [],
        }),
      ],
    });
    const linked = makeWorkRecord({ id: "res-work-linked", project_id: "math", project_name: "Math" });
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET")
        return json([linked]);
      if (path === "/api/checkpoints" && method === "POST")
        return json({
          id: "cp-new",
          project_id: "math",
          project_name: "Math",
          summary: "Reviewed proof obligations.",
          last_completed: "Read report",
          next_action: "Check composition.",
          blockers: "",
          evidence_refs: ["artifacts/math01/report.json"],
          milestone: "MATH01",
          source: "user",
          created_at: new Date().toISOString(),
        });
      if (path === "/api/tasks/task-math" && method === "PATCH")
        return json({ ...detail.tasks[0], status: "done" });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProject();

    expect(await screen.findByRole("heading", { name: "Math" })).toBeInTheDocument();
    expect(screen.getByText("Work has no verified read-only opportunity export configured.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Cross-application context" })).toBeInTheDocument();
    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fixture qualified opportunity/i })).toHaveAttribute(
      "href",
      "/work?record=res-work-linked",
    );

    await user.type(screen.getByLabelText("What happened?"), "Reviewed proof obligations.");
    await user.type(screen.getByLabelText("Next intended action"), "Check composition.");
    await user.type(screen.getByLabelText("Milestone (optional)"), "MATH01");
    await user.type(screen.getByLabelText("Evidence references (one per line)"), "artifacts/math01/report.json");
    await user.click(screen.getByRole("button", { name: "Save checkpoint" }));

    await waitFor(() => {
      const checkpoint = calls.find(
        (call) => call.method === "POST" && call.path === "/api/checkpoints",
      );
      expect(checkpoint).toBeTruthy();
      expect(checkpoint?.body).toMatchObject({
        project_id: "math",
        summary: "Reviewed proof obligations.",
        next_action: "Check composition.",
        milestone: "MATH01",
      });
    });

    await user.click(screen.getByRole("button", { name: "Edit Inspect proof obligations" }));
    const titleInput = screen.getByLabelText("Edit title for Inspect proof obligations");
    await user.clear(titleInput);
    await user.type(titleInput, "Inspect all proof obligations");
    await user.click(screen.getByRole("button", { name: "Save task title" }));
    await waitFor(() => {
      const patches = calls.filter(
        (call) => call.method === "PATCH" && call.path === "/api/tasks/task-math",
      );
      expect(patches.some((call) => (call.body as { title?: string }).title === "Inspect all proof obligations")).toBe(true);
    });

    await user.click(screen.getByRole("button", { name: "Complete Inspect proof obligations" }));
    await waitFor(() => {
      const patches = calls.filter(
        (call) => call.method === "PATCH" && call.path === "/api/tasks/task-math",
      );
      expect(patches.some((call) => (call.body as { status?: string }).status === "done")).toBe(true);
    });
  });

  it("renders manuscript quality with real scorecards, history and workbench handoff", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const evaluation = (overrides: Record<string, unknown> = {}) => ({
      id: "mqeval:test",
      project_id: "math",
      book_id: "book-math",
      chapter_id: "01-chapter.md",
      source_path: "C:/books/math/01-chapter.md",
      chapter_revision: "a".repeat(64),
      rubric_id: "manuscript-prose-v1",
      rubric_version: 1,
      prompt_version: "1",
      requested_model: "m-a",
      actual_model: "m-a",
      status: "CURRENT",
      derived_state: "current",
      overall: 4.0,
      aggregation_method: "mean_equal_weights_v1",
      dimensions: {
        clarity: { dimension: "clarity", score: 4, evidence: "q", evidence_validated: true },
        argument: { dimension: "argument", score: 4, evidence: "q", evidence_validated: true },
        precision: { dimension: "precision", score: 5, evidence: "q", evidence_validated: true },
        economy: { dimension: "economy", score: 3, evidence: "q", evidence_validated: true },
        voice: { dimension: "voice", score: 4, evidence: "q", evidence_validated: true },
        structure: { dimension: "structure", score: 4, evidence: "q", evidence_validated: true },
      },
      findings: [],
      uncertainty: "",
      limitations: [],
      execution: {},
      previous_evaluation_id: null,
      supersedes: null,
      workbench_url: "http://workbench.test",
      workbench_link: "http://workbench.test/#chapter=01-chapter.md",
      section_id: null,
      section_title: null,
      char_span: [],
      section_sha: null,
      created_at: new Date().toISOString(),
      ...overrides,
    });
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/math/evidence-timeline" && method === "GET")
        return json({ workflows: [], observations: [] });
      if (path === "/api/quality/workspace" && method === "GET")
        return json({
          project_id: "math",
          book_id: "",
          chapters_total: 1,
          chapters_evaluated: 1,
          chapters_current: 1,
          chapters: [
            {
              chapter_id: "01-chapter.md",
              chapter_title: null,
              evaluations: [
                evaluation({ id: "mqeval:old", overall: 3.83, derived_state: "historical" }),
                evaluation({ id: "mqeval:new" }),
              ],
              sections: [evaluation({ id: "mqeval:sec", section_id: "u1", section_title: "S", overall: 4.0 })],
              current: evaluation({ id: "mqeval:new" }),
            },
          ],
          limitations: ["Two of 45 Inference chapters evaluated."],
        });
      if (path === "/api/quality/discovery" && method === "GET")
        return json([
          {
            chapter_id: "01-chapter.md",
            title: "Alpha",
            source_path: "C:/books/math/01-chapter.md",
            revision: "a".repeat(64),
            has_current: true,
            current_model: "m",
            current_id: "mqeval:new",
            compatible: true,
            eligibility: "current",
          },
        ]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({
          project_id: "math",
          book_id: "",
          chapters_total: 0,
          chapters_observed: 0,
          chapters_current: 0,
          chapters: [],
          limitations: [],
        });
      if (path === "/api/writer/books" && method === "GET")
        return json({
          available: true,
          detail: "",
          error: null,
          totals: {},
          review_queue: [],
          decision_queue: [
            {
              id: "q1",
              project_id: "math",
              severity: "medium",
              code: "READABILITY.SENTENCE_LOAD",
              count: 3,
              chapter_id: "c1",
              chapter_title: "On Proofs",
              chapter_name: "01-chapter.md",
              reason: "Several sentences carry three clauses.",
            },
          ],
          decision_totals: {},
          workbench: { url: "", book: null, ready: false, note: "" },
          books: [
            {
              project_id: "math",
              title: "Math",
              status: "NEEDS_REVIEW",
              profile: "technical-nonfiction-v1",
              chapters_available: 1,
              readability: null,
              highest_risk: null,
              chapters: [],
            },
          ],
          limitations: [],
        });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderProject();

    expect(await screen.findByRole("heading", { name: "Manuscript quality" })).toBeInTheDocument();
    expect(await screen.findByText("01-chapter.md")).toBeInTheDocument();
    expect(await screen.findByText("Not assessed")).toBeInTheDocument();
    expect(screen.getByText("Earlier observations (1)")).toBeInTheDocument();
    expect(screen.getByText("Section evaluations (1)")).toBeInTheDocument();
    expect(screen.getByText("Several sentences carry three clauses.")).toBeInTheDocument();
    const handoffs = screen.getAllByRole("link", { name: /Open chapter in Workbench/i });
    expect(handoffs.length).toBeGreaterThan(0);
    handoffs.forEach((link) =>
      expect(link).toHaveAttribute("href", "http://workbench.test/#chapter=01-chapter.md"),
    );
  });
});
