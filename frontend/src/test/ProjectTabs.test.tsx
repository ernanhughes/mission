import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectPage } from "../pages/ProjectPage";
import { json, apiError, mockFetch, renderRoute } from "./helpers";
import { makeProjectDetail } from "./fixtures";

function baseMocks(detail: ReturnType<typeof makeProjectDetail>) {
  return mockFetch(({ path, method }) => {
    if (path === "/api/projects/math" && method === "GET") return json(detail);
    if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
    if (path === "/api/projects/math/evidence-timeline" && method === "GET")
      return json({ workflows: [], observations: [] });
    if (path === "/api/quality/discovery" && method === "GET") return json([]);
    if (path === "/api/quality/campaigns" && method === "GET") return json([]);
    if (path === "/api/technical/overview" && method === "GET")
      return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
    if (path === "/api/publication/calibration/runs" && method === "GET") return json([]);
    if (path === "/api/quality/workspace" && method === "GET")
      return json({ project_id: "math", chapters: [], limitations: [] });
    if (path === "/api/artifact-load/workspace" && method === "GET")
      return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
    if (path === "/api/writer/books" && method === "GET")
      return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
    if (path === "/api/writer/evaluations" && method === "GET") return json([]);
    if (path === "/api/publication/assessments" && method === "GET") return json([]);
    if (path === "/api/publication/publishing" && method === "GET")
      return json({ project_id: "math", chapter_count: 0, lifecycle: null, publication_gate: "Unknown", evidence: [], blockers: { failed: [], stale: [], missing: [], identity_conflicts: [] }, refresh_note: "" });
    if (path === "/api/living-book/projects/math" && method === "GET") return apiError(404, "no book");
    if (path === "/api/publication/calibration" && method === "GET") return json([]);
    if (path === "/api/publication/calibration/stats" && method === "GET") return json({});
    if (path === "/api/publication/calibration/sample" && method === "GET") return json({});
    if (path === "/api/publication/calibration/packets" && method === "GET") return json({ count: 0, packets: [] });
    return apiError(404, `Unhandled ${method} ${path}`);
  });
}

function renderAt(route: string) {
  return renderRoute(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectPage />} />
    </Routes>,
    route,
  );
}

describe("Project workspace tabs", () => {
  it("opens Overview by default with compact header", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    baseMocks(detail);
    renderAt("/projects/math");
    expect(await screen.findByRole("heading", { name: "Math" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Overview/ })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("heading", { name: "Project summary" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Quick navigation" })).toBeInTheDocument();
    // Heavy workspaces stay unmounted
    expect(screen.queryByRole("heading", { name: "Book Quality Map" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Calibration review queue" })).not.toBeInTheDocument();
  });

  it("falls back to Overview for unknown tab identifiers", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    baseMocks(detail);
    renderAt("/projects/math?tab=bogus-tab");
    expect(await screen.findByRole("heading", { name: "Project summary" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Overview/ })).toHaveAttribute("aria-selected", "true");
  });

  it("deep-links directly into Quality, Technical, Publishing, Work and Activity", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    baseMocks(detail);
    const cases: Array<[string, string]> = [
      ["/projects/math?tab=quality", "Manuscript quality"],
      ["/projects/math?tab=technical", "Technical Confidence"],
      ["/projects/math?tab=publishing", "Publication Readiness"],
      ["/projects/math?tab=work", "Recommendations awaiting review"],
      ["/projects/math?tab=activity", "Activity"],
      ["/projects/math?tab=book", "Manuscript and chapter inventory"],
      ["/projects/math?tab=calibration", "Calibration review queue"],
    ];
    for (const [route, heading] of cases) {
      const { unmount } = renderAt(route);
      expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
      unmount();
    }
  });

  it("shows tab badges for quality, calibration and work", async () => {
    const detail = makeProjectDetail({
      id: "math",
      name: "Math",
      tasks: [{ id: "t1", project_id: "math", project_name: "Math", title: "Do", description: "", status: "open", priority: 1, source: "user", due_at: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }],
      recommendations: [
        { id: "r1", project_id: "math", project_name: "Math", title: "Rec", rationale: "why", evidence: [], source_application: null, source_ref: null, external_id: null, provenance: "derived_observation", review_state: "pending", created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      ],
    });
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/math/evidence-timeline" && method === "GET") return json({ workflows: [], observations: [] });
      if (path === "/api/quality/discovery" && method === "GET")
        return json([
          { chapter_id: "01-chapter.md", title: "A", source_path: "x", revision: "a".repeat(64), has_current: false, current_model: null, current_id: null, compatible: true, eligibility: "missing" },
          { chapter_id: "02-chapter.md", title: "B", source_path: "x", revision: "b".repeat(64), has_current: true, current_model: "m", current_id: "id", compatible: true, eligibility: "current" },
        ]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/publication/calibration/runs" && method === "GET")
        return json([{ run_id: "CAL04A02-20261112", awaiting: 5, reviewed: 1 }]);
      if (path === "/api/quality/workspace" && method === "GET") return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/artifact-load/workspace" && method === "GET") return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET") return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      if (path === "/api/writer/evaluations" && method === "GET") return json([]);
      if (path === "/api/publication/assessments" && method === "GET") return json([]);
      if (path === "/api/publication/publishing" && method === "GET") return json({ project_id: "math", chapter_count: 0, lifecycle: null, publication_gate: "Unknown", evidence: [], blockers: { failed: [], stale: [], missing: [], identity_conflicts: [] }, refresh_note: "" });
      if (path === "/api/living-book/projects/math" && method === "GET") return apiError(404, "no book");
      if (path === "/api/publication/calibration" && method === "GET") return json([]);
      if (path === "/api/publication/calibration/stats" && method === "GET") return json({});
      if (path === "/api/publication/calibration/sample" && method === "GET") return json({});
      if (path === "/api/publication/calibration/packets" && method === "GET") return json({ count: 0, packets: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderAt("/projects/math");
    await screen.findByRole("heading", { name: "Math" });
    const tablist = await screen.findByRole("tablist", { name: "Project workspace sections" });
    // Quality badge: 1 missing; Calibration badge: 5 awaiting; Work badge: 2 (1 task + 1 rec)
    const qualityTab = within(tablist).getByRole("tab", { name: /Quality/ });
    const calTab = within(tablist).getByRole("tab", { name: /Calibration/ });
    const workTab = within(tablist).getByRole("tab", { name: /Work/ });
    expect(qualityTab.textContent).toMatch(/1/);
    expect(calTab.textContent).toMatch(/5/);
    expect(workTab.textContent).toMatch(/2/);
  });

  it("supports arrow-key movement between tabs", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    baseMocks(detail);
    const user = userEvent.setup();
    renderAt("/projects/math");
    const overviewTab = await screen.findByRole("tab", { name: /Overview/ });
    overviewTab.focus();
    expect(overviewTab).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    const bookTab = screen.getByRole("tab", { name: /^Book/ });
    expect(bookTab).toHaveFocus();
    expect(await screen.findByRole("heading", { name: "Manuscript and chapter inventory" })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /^Quality/ })).toHaveFocus();
  });

  it("deep-links to a specific calibration packet and preserves drafts across tabs", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const packetA = {
      calibration_case_id: "CAL-A", sampling_arm: "A", sample_reason: "probability-sample",
      run_id: "CAL04A02-20261112", requirement_id: "treq:A", claim_id: "tclaim:A",
      book_id: "book-inference", chapter_id: "43-chapter.md", source_revision: "a".repeat(64),
      live_chapter_revision: "a".repeat(64), claim_type: "FACTUAL", epistemic_role: "OBSERVED",
      claim_text: "Claim A text.", qualifications: [],
      exact_manuscript_excerpt: "Claim A text.",
      surrounding_source_context: { text: "", char_span: [0, 0], excerpt_offset_in_context: [0, 0] },
      requirement_template: "source_or_measurement", requirement_type: "evidence",
      requirement_description: "Desc A.", requirement_acceptance_rule: "Rule A.",
      current_applicability: "APPLICABLE", applicability_reason: "candidate",
      current_satisfaction: "NOT_ASSESSED", satisfaction_detail: "",
      existing_evidence: [], existing_verification_results: [],
      existing_gap: [], current_priority: "[P2]",
      integrity: {}, review_state: "AWAITING_REVIEW",
    };
    const packetB = {
      ...packetA,
      calibration_case_id: "CAL-B",
      requirement_id: "treq:B",
      chapter_id: "01-chapter.md",
      claim_text: "Claim B text.",
      exact_manuscript_excerpt: "Claim B text.",
    };
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/math/evidence-timeline" && method === "GET") return json({ workflows: [], observations: [] });
      if (path === "/api/quality/discovery" && method === "GET") return json([]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET") return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/publication/calibration/runs" && method === "GET") return json([{ run_id: "CAL04A02-20261112", awaiting: 2, reviewed: 0 }]);
      if (path === "/api/publication/calibration/sample" && method === "GET") return json({ run_id: "CAL04A02-20261112", new_distinct: 2, new_model_calls: 0 });
      if (path === "/api/publication/calibration/packets" && method === "GET") return json({ count: 2, packets: [packetA, packetB] });
      if (path === "/api/publication/calibration" && method === "GET") return json([]);
      if (path === "/api/publication/calibration/stats" && method === "GET") return json({});
      if (path === "/api/publication/assessments" && method === "GET") return json([]);
      if (path === "/api/publication/publishing" && method === "GET") return json({ project_id: "math", chapter_count: 0, lifecycle: null, publication_gate: "Unknown", evidence: [], blockers: { failed: [], stale: [], missing: [], identity_conflicts: [] }, refresh_note: "" });
      if (path === "/api/living-book/projects/math" && method === "GET") return apiError(404, "no book");
      if (path === "/api/quality/workspace" && method === "GET") return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET") return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      if (path === "/api/writer/evaluations" && method === "GET") return json([]);
      if (path === "/api/artifact-load/workspace" && method === "GET") return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/publication/calibration" && method === "POST") return json({ id: "x" }, 201);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    localStorage.clear();
    renderAt("/projects/math?tab=calibration&packet=CAL-B");
    // Packet B selected via deep link
    expect(await screen.findByText("Claim B text.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Review summary"), "draft note B");
    expect(screen.getByLabelText("Review summary")).toHaveValue("draft note B");

    // Switch away and back: draft persists via localStorage, packet param preserved
    await user.click(screen.getByRole("tab", { name: /Overview/ }));
    expect(await screen.findByRole("heading", { name: "Project summary" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Calibration/ }));
    expect(await screen.findByText("Claim B text.")).toBeInTheDocument();
    expect(screen.getByLabelText("Review summary")).toHaveValue("draft note B");

    // Previous/Next navigation moves between packets
    await user.click(screen.getByRole("button", { name: "Previous packet" }));
    expect(await screen.findByText("Claim A text.")).toBeInTheDocument();
  }, 15000);
});
