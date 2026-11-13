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
      if (path === "/api/technical/overview" && method === "GET")
        return json({
          project_id: "math",
          chapters_with_claims: 1,
          claims_total: 2,
          by_status: { VERIFIED_DETERMINISTICALLY: 1, UNRESOLVED: 1 },
          by_method: { deterministic: 1 },
          claims_unresolved: 1,
        });
      if (path === "/api/technical/chapters/01-chapter.md" && method === "GET") return json(null);
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
    expect(await screen.findByRole("heading", { name: "Book Quality Map" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Technical Confidence" })).toBeInTheDocument();
    expect(await screen.findByText("1 chapters · 2 claims")).toBeInTheDocument();
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

  it("drives evidence-completeness coverage, gaps and author decisions", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/quality/workspace" && method === "GET")
        return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/quality/discovery" && method === "GET")
        return json([{ chapter_id: "01-chapter.md", title: "Alpha" }]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 1, claims_total: 2, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/technical/completeness/01-chapter.md" && method === "GET")
        return json({
          chapter_id: "01-chapter.md",
          live_revision: "a".repeat(64),
          regions_total: 4,
          regions_processed: 2,
          regions_capped: 1,
          regions_failed: 0,
          regions_not_started: 1,
          regions_stale: 0,
          claims_total: 2,
          claims_source_verified: 1,
          claims_stale: 0,
          requirements_total: 5,
          by_satisfaction: { UNRESOLVED: 2, NOT_ASSESSED: 3 },
          by_applicability: { APPLICABLE: 5 },
          open_gaps: 2,
          gap_types: ["NOT_SEARCHED", "MISSING_BASELINE"],
          assessment: "PARTIAL",
        });
      if (path === "/api/technical/gaps" && method === "GET")
        return json([
          {
            id: "tgap:1", chapter_id: "01-chapter.md", claim_id: "tclaim:1", requirement_id: "treq:1",
            gap_type: "NOT_SEARCHED", title: "Unexamined appendix", detail: "Not yet searched",
            searched_scope: "chapter text only", status: "OPEN", priority_rationale: "[P2] workflow gap",
            created_at: new Date().toISOString(),
          },
        ]);
      if (path === "/api/technical/objectives" && method === "GET")
        return json([
          {
            id: "tobj:1", chapter_id: "01-chapter.md",
            statement: "Establish the vocabulary.", source: "explicit", status: "proposed",
            created_at: new Date().toISOString(),
          },
        ]);
      if (path === "/api/technical/gaps/tgap:1/status" && method === "POST") return json({ id: "tgap:1", status: "RESOLVED" });
      if (path === "/api/technical/reviews" && method === "POST") return json({ id: "mqrev:1", decision: "INVESTIGATE" });
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProject();

    expect(await screen.findByRole("heading", { name: "Evidence Completeness" })).toBeInTheDocument();
    const chapterSelect = screen.getByLabelText("Completeness chapter");
    await waitFor(() => {
      expect(chapterSelect.querySelector('option[value="01-chapter.md"]')).toBeTruthy();
    });
    await user.selectOptions(chapterSelect, "01-chapter.md");

    expect(await screen.findByText(/Claim recall: UNKNOWN/)).toBeInTheDocument();
    expect(await screen.findByText("Unexamined appendix")).toBeInTheDocument();
    expect(await screen.findByText("Establish the vocabulary.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Obtain Evidence" }));
    await waitFor(() => {
      const review = calls.find((call) => call.method === "POST" && call.path === "/api/technical/reviews");
      expect(review?.body).toMatchObject({ decision: "INVESTIGATE", finding_id: "tgap:1" });
    });
  });

  it("drives publication readiness gates, issues and author approval", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const assessment = {
      id: "pubass:1", project_id: "math", book_id: "book-math", book_root: "/books/math",
      policy_version: "publication-readiness-v1", technical_scope: "pilot",
      manuscript_fingerprint: "a".repeat(64), input_manifest_fingerprint: "b".repeat(64),
      chapter_count: 45, assessment_status: "NOT_YET_ASSESSED", freshness: "CURRENT",
      readiness_detail: "mandatory evidence missing: technical_verification",
      preflight_id: "pubpre:1", created_at: new Date().toISOString(),
      gates: [
        {
          id: "pubgate:1", gate_id: "technical_verification", gate_version: 1,
          gate_group: "technical", result: "NOT_RUN", blocking: true, waivable: false,
          detail: "pilot covers 3 of 45 chapters", evidence_refs: ["technical:overview"],
          limitations: "pilot scope only", created_at: new Date().toISOString(),
        },
      ],
      issues: [
        {
          id: "pubissue:1", gate_id: "technical_verification",
          issue_type: "incomplete_mandatory_assessment", severity: "unknown",
          verification_method: "deterministic", status: "OPEN",
          waiver_eligibility: "nonwaivable", author_review_status: "pending",
          source_refs: [], evidence_refs: ["technical:overview"],
          rationale: "pilot covers 3 of 45 chapters", created_at: new Date().toISOString(),
        },
      ],
      approvals: [],
    };
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/quality/workspace" && method === "GET")
        return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/quality/discovery" && method === "GET") return json([]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/publication/assessments" && method === "GET") return json([assessment]);
      if (path === "/api/publication/assessments" && method === "POST") return json(assessment, 201);
      if (path === "/api/publication/calibration/summary" && method === "GET")
        return json({ reviewed: 34, applicable: 32, false_positive_obligations: 1, would_block: 0, advisory_only: true });
      if (path === "/api/publication/issues/pubissue:1/review" && method === "POST")
        return json({ id: "pubissue:1" });
      if (path === "/api/publication/approvals" && method === "POST")
        return json({ id: "pubappr:1", decision: "APPROVE_RELEASE_CANDIDATE" }, 201);
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProject();

    expect(await screen.findByRole("heading", { name: "Publication Readiness" })).toBeInTheDocument();
    const pilotNotes = await screen.findAllByText(/pilot covers 3 of 45 chapters/);
    expect(pilotNotes.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText(/mandatory check\(s\) still unknown/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Release gates" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Confirmed blockers and unknowns" })).toBeInTheDocument();

    const dossier = await screen.findByRole("link", { name: /Download dossier/ });
    expect(dossier).toHaveAttribute("href", "/api/publication/assessments/pubass:1/dossier.zip");

    await user.click(screen.getByRole("button", { name: "Accept Finding" }));
    await waitFor(() => {
      const review = calls.find((call) => call.method === "POST" && call.path === "/api/publication/issues/pubissue:1/review");
      expect(review?.body).toMatchObject({ decision: "ACCEPT FINDING" });
    });

    await user.type(screen.getByLabelText("Approval rationale"), "Pilot snapshot reviewed.");
    await user.click(screen.getByRole("button", { name: "Approve release candidate" }));
    await waitFor(() => {
      const approval = calls.find((call) => call.method === "POST" && call.path === "/api/publication/approvals");
      expect(approval?.body).toMatchObject({ decision: "APPROVE_RELEASE_CANDIDATE", assessment_id: "pubass:1" });
    });
  });

  it("drives calibration review with rubric, provenance and states", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const packet = {
      calibration_case_id: "CAL04A02-001", sampling_arm: "A", sample_reason: "probability-sample",
      run_id: "CAL04A02-20261112", requirement_id: "treq:1", claim_id: "tclaim:1",
      book_id: "book-math", chapter_id: "01-chapter.md", source_revision: "a".repeat(64),
      live_chapter_revision: "a".repeat(64), claim_type: "FACTUAL", epistemic_role: "OBSERVED",
      claim_text: "The engine releases the sequence.", qualifications: [],
      exact_manuscript_excerpt: "The engine releases the sequence.",
      surrounding_source_context: { text: "Context. The engine releases the sequence. More.", char_span: [0, 10], excerpt_offset_in_context: [0, 5] },
      requirement_template: "source_or_measurement", requirement_type: "evidence",
      requirement_description: "A cited source backs the claim.", requirement_acceptance_rule: "Source present.",
      current_applicability: "APPLICABLE", applicability_reason: "candidate",
      current_satisfaction: "NOT_ASSESSED", satisfaction_detail: "",
      existing_evidence: [], existing_verification_results: [],
      existing_gap: [{ id: "tgap:1", gap_type: "NOT_SEARCHED", status: "OPEN", title: "Unexamined", searched_scope: "chapter", priority_rationale: "[P2]" }],
      current_priority: "[P2]", integrity: { chapter_fingerprint_match: true, excerpt_anchored: true, stale_or_missing: null },
      review_state: "AWAITING_REVIEW",
    };
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/quality/workspace" && method === "GET")
        return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/quality/discovery" && method === "GET") return json([]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/publication/assessments" && method === "GET") return json([]);
      if (path === "/api/publication/calibration/runs" && method === "GET")
        return json([{ run_id: "CAL04A02-20261112", contract: "evidence-requirements-v1", sample_version: 2, kind: "probability_plus_diagnostic", arm_A_target: 110, arm_B_target: 30, reviewed: 1, awaiting: 139, disagreements: 0, seed: 20261112 }]);
      if (path === "/api/publication/calibration/sample" && method === "GET")
        return json({ run_id: "CAL04A02-20261112", new_distinct: 140, new_model_calls: 0 });
      if (path === "/api/publication/calibration/packets" && method === "GET")
        return json({ count: 1, packets: [packet] });
      if (path === "/api/publication/calibration" && method === "GET") return json([]);
      if (path === "/api/publication/calibration/stats" && method === "GET")
        return json({ human_completed: 0, ai_assisted_completed: 0, deterministic_completed: 0 });
      if (path === "/api/publication/calibration" && method === "POST") return json({ id: "pubcal:1" }, 201);
      if (path === "/api/publication/calibration/summary" && method === "GET")
        return json({ reviewed: 0 });
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProject();

    expect(await screen.findByRole("heading", { name: "Calibration" })).toBeInTheDocument();
    expect(await screen.findByText(/CAL04A02-20261112/)).toBeInTheDocument();
    const claimCopies = await screen.findAllByText(/The engine releases the sequence\./);
    expect(claimCopies.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByRole("heading", { name: "Calibration review queue" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("R2 applicable"), "NOT_APPLICABLE");
    await user.type(screen.getByLabelText("Review summary"), "No measurement asserted.");
    await user.click(screen.getByRole("button", { name: "Submit completed review" }));
    await waitFor(() => {
      const created = calls.find((call) => call.method === "POST" && call.path === "/api/publication/calibration");
      const body = created?.body as Record<string, unknown>;
      expect(body).toMatchObject({
        requirement_id: "treq:1", sample_version: 2,
        requirement_applicable: "NOT_APPLICABLE",
        reviewer: "human:author",
      });
      expect(String(body.verdict)).toMatch(/R2:NOT_APPLICABLE/);
    });

    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const drafts = calls.filter((call) => call.method === "POST" && call.path === "/api/publication/calibration");
      expect(drafts.some((call) => String((call.body as Record<string, unknown>).verdict).startsWith("DRAFT:"))).toBe(true);
    });
  });

  it("surfaces quotation and numbers verification on quality findings", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    const flaggedFinding = {
      finding_id: "Q-flagged",
      family: "claim_status",
      dimension: "evidence",
      claim: 'The chapter says "the product is exact".',
      evidence_ids: ["e1"],
      verification: "EXACT_MATCH",
      evidence: [{ evidence_id: "e1", file: "01-chapter.md", start_line: 10, end_line: 10, excerpt: "The product rule is exact." }],
      quotation_check: { status: "unsupported", quotes: [{ quote: "the product is exact", status: "unsupported" }] },
      numbers_check: { status: "needs_semantic_review", numbers: [{ number: "0.0111", status: "derived_or_unverified" }] },
    };
    const cleanFinding = {
      finding_id: "Q-clean",
      family: "clarity",
      dimension: "evidence",
      claim: "The intro is vague.",
      evidence_ids: ["e2"],
      verification: "EXACT_MATCH",
      evidence: [{ evidence_id: "e2", file: "01-chapter.md", start_line: 3, end_line: 3, excerpt: "Intro text." }],
    };
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/quality/workspace" && method === "GET")
        return json({
          project_id: "math",
          chapters: [
            {
              chapter_id: "01-chapter.md",
              chapter_title: null,
              evaluations: [
                {
                  id: "mqeval:verify",
                  project_id: "math",
                  book_id: "jev",
                  chapter_id: "01-chapter.md",
                  source_path: "content/books/jev/01-chapter.md",
                  chapter_revision: "a".repeat(64),
                  status: "CURRENT",
                  derived_state: "findings",
                  overall: null,
                  dimensions: {},
                  findings: [flaggedFinding, cleanFinding],
                  uncertainty: "",
                  limitations: [],
                  execution: {},
                  previous_evaluation_id: null,
                  supersedes: null,
                  workbench_url: null,
                  workbench_link: null,
                  section_id: null,
                  section_title: null,
                  char_span: [],
                  section_sha: null,
                  created_at: new Date().toISOString(),
                },
              ],
              sections: [],
              current: null,
            },
          ],
          limitations: [],
        });
      if (path === "/api/quality/discovery" && method === "GET") return json([]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/technical/chapters/01-chapter.md" && method === "GET") return json(null);
      if (path === "/api/quality/evaluations/mqeval:verify/reviews" && method === "GET") return json([]);
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: false, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderProject();

    expect(await screen.findByText(/The chapter says/)).toBeInTheDocument();
    expect(await screen.findByText("quote unverified")).toBeInTheDocument();
    expect(await screen.findByText("numbers need review")).toBeInTheDocument();
    expect(screen.queryByText("quote outside cited spans")).not.toBeInTheDocument();
  });
});
