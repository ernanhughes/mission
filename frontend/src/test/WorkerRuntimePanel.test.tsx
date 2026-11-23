import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectPage } from "../pages/ProjectPage";
import { json, mockFetch, renderRoute } from "./helpers";
import { makeProjectDetail, makeTask } from "./fixtures";

function detail() {
  return makeProjectDetail({
    id: "writer",
    name: "Writer",
    kind: "supporting",
    book: null,
    repositories: [],
    applications: [],
    tasks: [makeTask({ id: "t1", project_id: "writer", project_name: "Writer", title: "T" })],
    recommendations: [],
    decisions: [],
    checkpoints: [],
    activity: [],
    adapters: [],
    inspect_project_id: null,
  });
}

function mocks(runtime: unknown) {
  return mockFetch(({ path, method }) => {
    if (path === "/api/projects/writer" && method === "GET") return json(detail());
    if (path === "/api/projects/writer/integration-context" && method === "GET") return json([]);
    if (path === "/api/projects/writer/evidence-timeline" && method === "GET")
      return json({ workflows: [], observations: [] });
    if (path === "/api/projects/writer/git-links" && method === "GET") return json([]);
    if (path === "/api/worker/runtime" && method === "GET") return json(runtime);
    if (path === "/api/inspect/opportunities" && method === "GET")
      return json({ available: true, stale_refresh: false, total: 0, opportunities: [] });
    if (path === "/api/software-quality/charters" && method === "GET") return json([]);
    if (path === "/api/software-quality/evaluations" && method === "GET") return json([]);
    if (path === "/api/software-quality/findings" && method === "GET") return json([]);
    if (path === "/api/software-quality/prompts" && method === "GET") return json([]);
    if (path === "/api/cultivation/goals" && method === "GET") return json([]);
    if (path === "/api/applications" && method === "GET") return json([]);
    return json({}, 404);
  });
}

describe("Worker runtime panel", () => {
  it("shows honest unavailable without breaking workspace", async () => {
    mocks({
      available: false,
      base_url: "http://127.0.0.1:7317",
      checked_at: new Date().toISOString(),
      connection: { reachable: false, status: "unknown", version: "unknown", listener: "not stated", error: "ConnectError" },
      availability: { available: false, error: "ConnectError", models: [], warnings: [], freshness_note: "cached" },
      usage: { available: false, error: "ConnectError", warnings: [], unknown_note: "unknown" },
      preflight: { available: false, error: "ConnectError" },
      notes: ["Cached availability does not guarantee a future inference call will succeed."],
    });
    renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/writer",
    );
    expect(await screen.findByText("AI runtime")).toBeInTheDocument();
    expect(await screen.findByText(/Worker is unavailable/)).toBeInTheDocument();
  });

  it("shows cached availability and unknown costs explicitly", async () => {
    mocks({
      available: true,
      base_url: "http://127.0.0.1:7317",
      checked_at: new Date().toISOString(),
      connection: { reachable: true, status: "ok", version: "v1", listener: "127.0.0.1:7317", error: null },
      availability: {
        available: true, error: null, schema_version: "worker.model-availability.v1",
        discovered_at: null, probing: false, models: [], warnings: [], freshness_note: "Cached availability does not guarantee a future inference call will succeed.",
      },
      usage: {
        available: true, error: null, schema_version: "worker.model-usage.v1", scope: "worker-process-jobs",
        outcomes: { accepted: 1 }, billed: { unknown_calls: 2 }, estimated: {}, billed_unknown_calls: 2,
        models_count: 0, warnings: [], unknown_note: "Unknown billed cost remains unknown",
      },
      preflight: { available: true, error: null, document: {} },
      notes: [],
    });
    renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/writer",
    );
    expect((await screen.findAllByText(/Cached availability/)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/unknown remains unknown/)).toBeInTheDocument();
  });
});
