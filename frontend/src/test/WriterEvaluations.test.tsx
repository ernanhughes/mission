import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectPage } from "../pages/ProjectPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeProjectDetail } from "./fixtures";

function envelope(overrides: Record<string, any>) {
  return {
    schema_version: "writer.evaluation-envelope.v1",
    evaluation_id: "artifact-eval-test-1",
    observed_at: "2026-11-22T12:00:00+00:00",
    work_object: {
      kind: "chapter",
      target_id: "39-chapter",
      source_path: "C:/books/inference/content/books/inference/39-chapter.md",
      source_hash: "a".repeat(64),
      byte_length: 100,
    },
    producer: {
      runtime_name: "artifact",
      method: "analyze_text",
      method_version: "artifact-adapter.v1",
    },
    rubric: { rubric_id: "artifact-detectors", profile: "fiction" },
    status: "complete",
    dimensions: [],
    findings: [],
    coverage: { unit: "characters", evaluated: 100, total: 100, note: "Full-text." },
    limitations: ["Detector versions vary."],
    provenance: { operation_id: "op-test-1" },
    ...overrides,
  };
}

function item(overrides: Record<string, any> = {}) {
  return {
    record_id: "wreval-test-1",
    evaluation_id: "artifact-eval-test-1",
    project_id: "math",
    current: true,
    observed_at: "2026-11-22T12:00:00+00:00",
    envelope: envelope({}),
    ...overrides,
  };
}

describe("Writer evaluations layer", () => {
  it("shows Writer specialist evidence beside prose measures without merging", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/math/evidence-timeline" && method === "GET")
        return json({ workflows: [], observations: [] });
      if (path === "/api/quality/workspace" && method === "GET")
        return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/quality/discovery" && method === "GET")
        return json([
          {
            chapter_id: "39-chapter.md",
            title: "Inference",
            source_path: "C:/books/39-chapter.md",
            revision: "b".repeat(64),
            has_current: false,
            current_model: null,
            current_id: null,
            compatible: true,
            eligibility: "missing",
          },
        ]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: true, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      if (path === "/api/writer/evaluations" && method === "GET")
        return json([
          item({
            evaluation_id: "artifact-eval-test-1",
            envelope: envelope({
              evaluation_id: "artifact-eval-test-1",
              dimensions: [
                {
                  dimension: "artifact_cleanliness",
                  score: 75.58,
                  verdict: null,
                  confidence: null,
                  scale: { scale_type: "continuous", minimum: 0, maximum: 100, higher_is_better: true, description: "0-100" },
                  rationale: "27 issues",
                  evidence_spans: [],
                },
              ],
              findings: [
                {
                  family: "artifact",
                  code: "EM_DASH",
                  claim: "em dash overuse",
                  severity: "medium",
                  spans: [{ source_id: "39-chapter", snippet: "— example", tag: "em_dash" }],
                },
              ],
            }),
          }),
          item({
            record_id: "wreval-test-2",
            evaluation_id: "qc-doc-test-1",
            envelope: envelope({
              evaluation_id: "qc-doc-test-1",
              producer: { runtime_name: "qc", method: "evaluate_document", method_version: "qc-v3" },
              dimensions: [],
              findings: [],
            }),
          }),
          item({
            record_id: "wreval-test-3",
            evaluation_id: "artifact-eval-test-0",
            current: false,
            envelope: envelope({ evaluation_id: "artifact-eval-test-0" }),
          }),
        ]);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/math",
    );

    expect(await screen.findByRole("heading", { name: "Writer evaluations" })).toBeInTheDocument();
    expect(await screen.findByText("artifact")).toBeInTheDocument();
    expect(screen.getByText("qc")).toBeInTheDocument();
    expect(screen.getByText(/75.58/)).toBeInTheDocument();
    expect(screen.getByText(/earlier \(1\)/)).toBeInTheDocument();
    expect(
      screen.getByText(/never averaged with prose scores/),
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /1 finding/ }));
    expect(await screen.findByText("EM_DASH")).toBeInTheDocument();
    expect(screen.getByText("— example")).toBeInTheDocument();
  });

  it("degrades to an empty state instead of inventing evidence", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET") return json([]);
      if (path === "/api/quality/workspace" && method === "GET")
        return json({ project_id: "math", chapters: [], limitations: [] });
      if (path === "/api/quality/discovery" && method === "GET") return json([]);
      if (path === "/api/quality/campaigns" && method === "GET") return json([]);
      if (path === "/api/technical/overview" && method === "GET")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/artifact-load/workspace" && method === "GET")
        return json({ project_id: "math", book_id: "", chapters_total: 0, chapters_observed: 0, chapters_current: 0, chapters: [], limitations: [] });
      if (path === "/api/writer/books" && method === "GET")
        return json({ available: true, detail: "", error: null, totals: {}, review_queue: [], decision_queue: [], decision_totals: {}, workbench: { url: "", book: null, ready: false, note: "" }, books: [], limitations: [] });
      if (path === "/api/writer/evaluations" && method === "GET") return json([]);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/math",
    );

    expect(await screen.findByRole("heading", { name: "Writer evaluations" })).toBeInTheDocument();
    expect(await screen.findByText("No Writer evaluations yet")).toBeInTheDocument();
  });
});
