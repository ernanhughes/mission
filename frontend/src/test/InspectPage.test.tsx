import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { InspectPage } from "../pages/InspectPage";
import { ProjectPage } from "../pages/ProjectPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeProjectDetail } from "./fixtures";

const manifest = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  contract_version: "1.0.0",
  generated_at: "2026-11-22T09:52:24Z",
  inspect_version: { git_sha: "testsha", prompt_version: "1.0", schema_version: "1.0.0" },
  sources: [
    {
      repository: "writer",
      head_sha: "abc123def456",
      inspection_status: "partial",
      stale: false,
      stale_reason: "",
    },
    {
      repository: "mission",
      head_sha: "def456abc123",
      inspection_status: "complete",
      stale: true,
      stale_reason: "source changed since inspection",
    },
  ],
  counts: { projects: 2, capabilities: 2, usages: 1, opportunities: 2, compositions: 1 },
  validation: { status: "valid", errors: [] },
};

const projects = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  total: 2,
  projects: [
    {
      id: "writer",
      mission_application_id: "writer",
      mapped: true,
      record: {
        id: "writer",
        name: "writer",
        path: "C:\\Projects\\writer",
        branch: "main",
        head_sha: "abc123def456",
        inspection_status: "partial",
        capabilities_count: 1,
        stale: false,
      },
    },
    {
      id: "mission",
      mission_application_id: "mission",
      mapped: false,
      record: {
        id: "mission",
        name: "mission",
        path: "C:\\Projects\\mission",
        branch: "main",
        head_sha: "def456abc123",
        inspection_status: "complete",
        capabilities_count: 1,
        stale: true,
      },
    },
  ],
};

const planCapability = {
  id: "writer-plan",
  name: "Plan chapter",
  description: "Plans a chapter outline deterministically",
  repository: "writer",
  subsystem: "planning",
  maturity: "implemented",
  operational_status: "tested-not-demonstrated",
  accessibility: ["agent-invocable"],
  risk: "read-only",
  functionality: {
    accomplishes: "Produce a chapter outline",
    inputs: ["chapter draft"],
    outputs: ["outline.json"],
    invocation: "writer plan --chapter 01",
    usage_example: "writer plan --chapter 01 --dry-run",
  },
  evidence: [
    { kind: "source", path: "planner.py", symbols: ["plan"], detail: "Implements plan." },
    { kind: "test", path: "tests/test_planner.py", symbols: ["test_plan"], detail: "Covers plan." },
  ],
};

const healthCapability = {
  id: "mission-health",
  name: "Health check",
  description: "Reports service health over HTTP",
  repository: "mission",
  subsystem: "operations",
  maturity: "draft",
  operational_status: "observed",
  accessibility: ["public-cli"],
  risk: "writes-local-files",
  unverified_reason: "no invocation observed",
  functionality: {
    accomplishes: "Report health",
    inputs: [],
    outputs: ["status json"],
    invocation: "mission health --write-state",
  },
  evidence: [],
};

const capabilities = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  total: 2,
  capabilities: [planCapability, healthCapability],
};

const usage = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  capability_id: "writer-plan",
  total: 1,
  usages: [
    {
      capability_id: "writer-plan",
      outcome: "chapter outline",
      description: "Produces an outline file",
      invocations: [
        {
          mechanism: "cli",
          target: "writer",
          arguments: "plan --chapter 01",
          workdir: "C:/Projects/writer",
          side_effects: "writes outline.json",
        },
      ],
      examples: [
        {
          title: "Dry run",
          command: "writer plan --chapter 01 --dry-run",
          expected: "outline printed, nothing written",
          validated: false,
        },
      ],
      limitations: "dry-run flag untested",
      invocation_status: "plausible-unverified",
      verification_status: "unverified",
      documentation_status: "documented",
    },
  ],
};

const opportunities = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  total: 2,
  opportunities: [
    {
      opportunity_id: "opp-docs-drift",
      title: "Docs drift",
      category: "docs-drift",
      confidence: "high",
      status: "proposed",
      human_decision: null,
      desired_outcome: "docs match behaviour",
      gap: "flag undocumented",
      suggested_action: "document the flag",
      unknowns: "which pages mention it",
      evidence_refs: ["writer/cli.py:plan"],
      repository: "writer",
      project_ids: ["writer"],
    },
    {
      opportunity_id: "opp-done",
      title: "Done item",
      category: "hygiene",
      confidence: "low",
      status: "resolved",
      human_decision: "accepted",
      desired_outcome: "done",
      gap: "none",
      suggested_action: "none",
      unknowns: "",
      evidence_refs: [],
      repository: "mission",
      project_ids: ["mission"],
    },
  ],
};

const coverageWriter = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  project_id: "writer",
  mission_application_id: "writer",
  mapped: true,
  record: {
    repository_id: "writer",
    inspection_status: "partial",
    head_sha: "abc123def456",
    generated_at: "2026-11-22T09:52:24Z",
    stale: false,
    stale_reason: "",
    inspected_subsystems: ["planning"],
    discovered_subsystems: ["planning", "rendering"],
    deferred_subsystems: ["rendering"],
    discovered_entrypoints: ["writer plan"],
    inspected_entrypoints: ["writer plan"],
    unresolved_areas: ["rendering pipeline unexamined"],
    denominator_notes: "subsystems discovered from top-level modules",
    coverage_limits: "static inspection only",
  },
};

const compositions = {
  available: true,
  stale_refresh: false,
  snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
  total: 1,
  compositions: [
    {
      composition_id: "comp-outline",
      desired_outcome: "drafted book",
      description: "plan then render",
      steps: ["plan chapter", "render chapter"],
      required_capabilities: ["writer-plan"],
      gaps: ["no render capability inspected"],
      status: "hypothesized",
      repository: "writer",
    },
  ],
};

function mockInspect() {
  return mockFetch(({ path, method }) => {
    if (method !== "GET") return apiError(404, `Unhandled ${method} ${path}`);
    if (path === "/api/inspect/manifest") return json(manifest);
    if (path === "/api/inspect/projects") return json(projects);
    if (path === "/api/inspect/capabilities") return json(capabilities);
    if (path === "/api/inspect/usage/writer-plan") return json(usage);
    if (path.startsWith("/api/inspect/usage/"))
      return json({ ...usage, capability_id: path.split("/").pop(), total: 0, usages: [] });
    if (path === "/api/inspect/opportunities") return json(opportunities);
    if (path === "/api/inspect/coverage/writer") return json(coverageWriter);
    if (path.startsWith("/api/inspect/coverage/")) return apiError(404, "not found", "not_found");
    if (path === "/api/inspect/compositions") return json(compositions);
    return apiError(404, `Unhandled ${method} ${path}`);
  });
}

function renderInspect() {
  return renderRoute(
    <Routes>
      <Route path="/inspect" element={<InspectPage />} />
    </Routes>,
    "/inspect",
  );
}

describe("InspectPage", () => {
  it("answers the five usability questions from the snapshot", async () => {
    mockInspect();
    const user = userEvent.setup();
    renderInspect();

    expect(await screen.findByRole("heading", { name: "Inspect" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect((await screen.findAllByText(/source changed since inspection/)).length).toBeGreaterThan(0);

    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByText("→ writer")).toBeInTheDocument();
    expect(screen.getByText("unmapped")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Capabilities" })).toBeInTheDocument();
    expect(screen.getByText("Plan chapter")).toBeInTheDocument();
    expect(screen.getByText("Health check")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search capabilities"), "outline");
    expect(screen.queryByText("Health check")).not.toBeInTheDocument();
    expect(screen.getByText("Plan chapter")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search capabilities"));

    await user.click(screen.getByRole("button", { name: /Plan chapter/ }));
    expect(await screen.findByText("Produce a chapter outline")).toBeInTheDocument();
    expect(screen.getByText("writer plan --chapter 01")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /How to use it/ }));
    expect(await screen.findByText("chapter outline")).toBeInTheDocument();
    expect(screen.getByText(/writes outline\.json/)).toBeInTheDocument();
    expect(screen.getByText(/unvalidated/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Health check/ }));
    const detail = await screen.findByLabelText("Capability mission-health");
    expect(within(detail).getByText(/no invocation observed/)).toBeInTheDocument();
    expect(within(detail).getByText(/Side-effectful/)).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Opportunities" })).toBeInTheDocument();
    expect(screen.getByText("Docs drift")).toBeInTheDocument();
    expect(screen.getByText("awaiting human decision")).toBeInTheDocument();
    expect(screen.queryByText("Done item")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Filter opportunities by status"), "ALL");
    expect(await screen.findByText("Done item")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Coverage" })).toBeInTheDocument();
    expect(screen.getByText("rendering pipeline unexamined")).toBeInTheDocument();
    expect(screen.getByText(/No coverage record published for/)).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Compositions" })).toBeInTheDocument();
    expect(screen.getByText("drafted book")).toBeInTheDocument();
    expect(screen.getByText(/no render capability inspected/)).toBeInTheDocument();
  });

  it("shows honest empty states when no snapshot is published", async () => {    const empty = { available: false, stale_refresh: false, snapshot_dir: null };
    mockFetch(({ path, method }) => {
      if (method !== "GET") return apiError(404, `Unhandled ${method} ${path}`);
      if (path === "/api/inspect/manifest") return json(empty);
      if (path === "/api/inspect/projects") return json({ ...empty, total: 0, projects: [] });
      if (path === "/api/inspect/capabilities") return json({ ...empty, total: 0, capabilities: [] });
      if (path === "/api/inspect/opportunities") return json({ ...empty, total: 0, opportunities: [] });
      if (path === "/api/inspect/compositions") return json({ ...empty, total: 0, compositions: [] });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderInspect();

    expect(await screen.findByText("No Inspect snapshot published")).toBeInTheDocument();
    expect(await screen.findByText("No projects published")).toBeInTheDocument();
    expect(await screen.findByText("No capabilities published")).toBeInTheDocument();
    expect(screen.getByText("No opportunities published")).toBeInTheDocument();
    expect(screen.getByText("No compositions published")).toBeInTheDocument();
  });

  it("renders real export composition steps as text, never [object Object]", async () => {
    // Regression test: the live export carries object steps
    // ({order, capability_id, description, inputs, outputs}). String(step)
    // rendered them as "[object Object]". This fixture mirrors the real
    // comp-book-quality-assessment record shape from output/consumers/mission.
    const realShape = {
      available: true,
      stale_refresh: false,
      snapshot_dir: "C:/Projects/inspect/output/consumers/mission",
      total: 1,
      compositions: [
        {
          composition_id: "comp-book-quality-assessment-a0f406",
          desired_outcome:
            "Evaluate an entire book across quality dimensions and produce an evidence-backed overall assessment.",
          description: "Candidate book-evaluation workflow.",
          steps: [
            {
              order: 1,
              capability_id: "chapter-quality-evaluation",
              description: "Run a bounded deterministic chapter loop over the frozen inventory.",
              inputs: ["--book-root <dir>", "--strategy deterministic"],
              outputs: ["per-chapter JSON envelope"],
            },
            {
              order: 2,
              capability_id: "editorial-diagnosis",
              description: "Diagnose the whole book dir for ranked findings.",
              inputs: ["<book-dir>"],
              outputs: ["EditorialReportDTO"],
            },
          ],
          required_capabilities: ["chapter-quality-evaluation", "editorial-diagnosis"],
          gaps: ["No single `evaluate-book` command exists."],
          status: "source-supported",
          repository: "writer",
        },
      ],
    };
    mockFetch(({ path, method }) => {
      if (method !== "GET") return apiError(404, `Unhandled ${method} ${path}`);
      if (path === "/api/inspect/manifest") return json(manifest);
      if (path === "/api/inspect/projects") return json(projects);
      if (path === "/api/inspect/capabilities") return json(capabilities);
      if (path.startsWith("/api/inspect/usage/"))
        return json({ ...usage, capability_id: path.split("/").pop(), total: 0, usages: [] });
      if (path === "/api/inspect/opportunities") return json(opportunities);
      if (path.startsWith("/api/inspect/coverage/")) return apiError(404, "not found", "not_found");
      if (path === "/api/inspect/compositions") return json(realShape);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderInspect();

    expect(await screen.findByText(/Evaluate an entire book/)).toBeInTheDocument();
    expect(screen.getAllByText(/chapter-quality-evaluation/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/bounded deterministic chapter loop/)).toBeInTheDocument();
    expect(screen.getByText(/Diagnose the whole book dir for ranked findings/)).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
});

describe("InspectPanel on ProjectPage", () => {
  it("scopes the Inspect section to the mapped inspect project", async () => {
    const detail = makeProjectDetail({ id: "math", name: "Math" });
    mockFetch(({ path, method }) => {
      if (method !== "GET") return apiError(404, `Unhandled ${method} ${path}`);
      if (path === "/api/projects/math") return json(detail);
      if (path === "/api/projects/math/integration-context") return json([]);
      if (path === "/api/projects/math/evidence-timeline") return json({ workflows: [], observations: [] });
      if (path === "/api/quality/discovery") return json([]);
      if (path === "/api/quality/campaigns") return json([]);
      if (path === "/api/technical/overview")
        return json({ project_id: "math", chapters_with_claims: 0, claims_total: 0, by_status: {}, by_method: {}, claims_unresolved: 0 });
      if (path === "/api/publication/calibration/runs") return json([]);
      if (path === "/api/publication/publishing")
        return json({ project_id: "math", chapter_count: 0, lifecycle: null, publication_gate: "Unknown", evidence: [], blockers: { failed: [], stale: [], missing: [], identity_conflicts: [] }, refresh_note: "" });
      if (path === "/api/living-book/projects/math") return apiError(404, "no book");
      if (path === "/api/inspect/manifest") return json(manifest);
      if (path === "/api/inspect/projects") return json(projects);
      if (path === "/api/inspect/capabilities") return json(capabilities);
      if (path === "/api/inspect/usage/writer-plan") return json(usage);
      if (path.startsWith("/api/inspect/usage/"))
        return json({ ...usage, capability_id: path.split("/").pop(), total: 0, usages: [] });
      if (path === "/api/inspect/opportunities") return json(opportunities);
      if (path === "/api/inspect/coverage/writer") return json(coverageWriter);
      if (path.startsWith("/api/inspect/coverage/")) return apiError(404, "not found", "not_found");
      if (path === "/api/inspect/compositions") return json(compositions);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/math?tab=work",
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: /Connected capabilities/ }));

    const section = await screen.findByRole("heading", { name: "Inspect" });
    expect(section).toBeInTheDocument();
    const region = section.closest("section")!;
    expect(await within(region).findByText("Plan chapter")).toBeInTheDocument();
    expect(within(region).queryByText("Health check")).not.toBeInTheDocument();
    expect(within(region).getByText("Docs drift")).toBeInTheDocument();
    expect(within(region).getByText("rendering pipeline unexamined")).toBeInTheDocument();
    await waitFor(() => {
      expect(within(region).getByText("drafted book")).toBeInTheDocument();
    });
  });
});

const opsInventory = {
  available: true,
  stale_refresh: false,
  total: 2,
  counts: { total: 2, never_inspected: 1, stale: 1, running: 0, current: 1, needs_enrichment: 1, unmapped: 0 },
  projects: [
    {
      inspect_id: "writer",
      name: "Writer",
      mission_application_id: "writer",
      mapped: true,
      repository_path: "C:\\Projects\\writer",
      reachable: true,
      execution: "complete",
      freshness: "current",
      enrichment: "missing",
      evidence: "tested-not-demonstrated",
      capabilities: 58,
      usages: 0,
      last_run_id: "inspect-abc",
      last_run_status: "completed",
      last_run_at: "2026-11-25T00:00:00Z",
      inspected_head_sha: "abc123",
      stale_reason: "",
      primary_action: "enrich",
      available_actions: ["inspect", "full", "enrich", "stamp", "view"],
    },
    {
      inspect_id: "verity",
      name: "Verity",
      mission_application_id: "verity",
      mapped: true,
      repository_path: "C:\\Projects\\verity",
      reachable: true,
      execution: "never-inspected",
      freshness: "unknown",
      enrichment: "unknown",
      evidence: "unknown",
      capabilities: 0,
      usages: 0,
      last_run_id: null,
      last_run_status: null,
      last_run_at: null,
      inspected_head_sha: null,
      stale_reason: "",
      primary_action: "inspect",
      available_actions: ["inspect", "full", "enrich", "stamp", "view"],
    },
  ],
  unmapped: [],
};

const opsJobs = {
  total: 1,
  runs: [
    {
      run_id: "inspect-live",
      repository_id: "worker",
      mission_application_id: "worker",
      operation: "inspect",
      scope: "full",
      status: "running",
      pid: 1234,
      requested_at: "2026-11-25T00:00:00Z",
      started_at: "2026-11-25T00:00:01Z",
      finished_at: "",
      exit_code: null,
      validation_status: "",
      result_summary: {},
      error: "",
      cancellable: true,
    },
  ],
};

function mockInspectOps() {
  return mockFetch(({ path, method }) => {
    if (method !== "GET" && method !== "POST") return apiError(404, `Unhandled ${method} ${path}`);
    if (path === "/api/inspect/manifest") return json(manifest);
    if (path === "/api/inspect/projects") return json(projects);
    if (path === "/api/inspect/capabilities") return json(capabilities);
    if (path.startsWith("/api/inspect/usage/"))
      return json({ ...usage, capability_id: path.split("/").pop(), total: 0, usages: [] });
    if (path === "/api/inspect/opportunities") return json(opportunities);
    if (path.startsWith("/api/inspect/coverage/")) return apiError(404, "not found", "not_found");
    if (path === "/api/inspect/compositions") return json(compositions);
    if (path === "/api/inspect/ops/inventory") return json(opsInventory);
    if (path === "/api/inspect/ops/runs") {
      if (method === "POST") return json({ run: opsJobs.runs[0], duplicate: false });
      return json(opsJobs);
    }
    if (path === "/api/inspect/ops/runs/inspect-live/cancel" && method === "POST")
      return json({ run: { ...opsJobs.runs[0], status: "cancelled", cancellable: false }, cancelled: true });
    return apiError(404, `Unhandled ${method} ${path}`);
  });
}

describe("InspectPage operational panel", () => {
  it("lists every inventory project with filters and starts the primary action", async () => {
    const calls = mockInspectOps();
    const user = userEvent.setup();
    renderInspect();

    expect(await screen.findByRole("heading", { name: "Projects — operational control" })).toBeInTheDocument();
    expect(await screen.findByText("Writer")).toBeInTheDocument();
    expect(screen.getByText("Verity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Never inspected" }));
    expect(screen.queryByText("Writer")).not.toBeInTheDocument();
    expect(screen.getByText("Verity")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "All" }));

    const inspectButtons = screen.getAllByRole("button", { name: "Inspect" });
    expect(inspectButtons.length).toBeGreaterThanOrEqual(1);
    await user.click(inspectButtons[0]);
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/api/inspect/ops/runs" && c.method === "POST")).toBe(true);
    });
    const started = calls.find((c) => c.path === "/api/inspect/ops/runs" && c.method === "POST");
    expect(started?.body).toMatchObject({ operation: "inspect" });
  });

  it("shows running jobs with cancel", async () => {
    mockInspectOps();
    renderInspect();

    expect(await screen.findByText("inspect-live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });
});
