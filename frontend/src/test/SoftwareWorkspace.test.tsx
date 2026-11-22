import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ProjectPage } from "../pages/ProjectPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeProject, makeProjectDetail, makeTask } from "./fixtures";

const softwareInventory = {
  total: 1,
  limit: 50,
  offset: 0,
  items: [
    {
      id: "writer",
      name: "Writer",
      description: "Authoring and evaluation system.",
      kind: "supporting",
      status: "active",
      pinned: false,
      archived: false,
      origin: "auto-discovered",
      priority: 100,
      classification: "library",
      confidence: 0.7,
      path: "C:\\Projects\\writer",
      repository_count: 1,
      repo_uid: "git-155ab6e996f80a04",
      branch: "main",
      commit_hash: "abcdef1234567890",
      last_commit_at: "2026-11-20T10:00:00+00:00",
      last_observed_at: "2026-11-21T10:00:00+00:00",
      accessible: true,
      missing: false,
      stale: false,
      applications: [{ id: "writer", name: "Writer", category: "writing" }],
      open_task_count: 1,
      pending_recommendation_count: 1,
      needs_attention: true,
      quality_state: "unassessed",
      inspect_project_id: null,
      current_milestone: "",
      next_action: "",
      updated_at: "2026-11-21T10:00:00+00:00",
    },
  ],
};

const softwareDetail = () =>
  makeProjectDetail({
    id: "writer",
    name: "Writer",
    kind: "supporting",
    description: "Authoring and evaluation system.",
    book: null,
    repositories: [
      {
        id: "repo-writer",
        name: "writer",
        path: "C:\\Projects\\writer",
        classification: "library",
        confidence: 0.7,
        evidence: [],
        role: "primary",
        source_root: "C:\\Projects",
        is_git: true,
        branch: "main",
        commit_hash: "abcdef1234567890",
        last_commit_at: "2026-11-20T10:00:00+00:00",
        dirty: false,
        accessible: true,
        candidate: false,
        last_observed_at: "2026-11-21T10:00:00+00:00",
        notes: "",
      },
    ],
    applications: [{ id: "writer", name: "Writer", category: "writing" }],
    tasks: [makeTask({ id: "task-w", project_id: "writer", project_name: "Writer", title: "Verify CLI" })],
    recommendations: [],
    decisions: [],
    checkpoints: [],
    activity: [],
    adapters: [],
    inspect_project_id: null,
  });

const gitLinks = [
  {
    repository_id: "repo-writer",
    path: "C:\\Projects\\writer",
    role: "primary",
    classification: "library",
    accessible: true,
    git_repo_id: "gitrepo-1",
    repo_uid: "git-155ab6e996f80a04",
    branch: "main",
    head_sha: "abcdef1234567890abcdef1234567890abcdef12",
    total_commits: 120,
    backfill_complete: true,
    has_agents: true,
    has_description: false,
    context_status: "partial",
    latest_review_status: null,
    latest_review_verdict: null,
  },
];

function renderProjects() {
  return renderRoute(
    <Routes>
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/projects/:projectId" element={<ProjectPage />} />
    </Routes>,
    "/projects",
  );
}

describe("Projects software inventory", () => {
  it("lists software workspaces by default and opens reconciliation", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/software" && method === "GET") return json(softwareInventory);
      if (path === "/api/projects/identity/preview" && method === "GET")
        return json({
          root: "C:\\Projects",
          policy: { auto_register: false, approved_at: null, approved_root: null },
          counts: { eligible: 1, needs_review: 0, skipped: 40, repositories: 41, book_legacy_preserved: 3 },
          eligible: [],
          needs_review: [],
          skipped: [],
          notes: [],
        });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProjects();

    expect(await screen.findByText("Writer")).toBeInTheDocument();
    expect(screen.getByText("Unassessed")).toBeInTheDocument();
    expect(screen.getByText(/1 software project/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Discovery & reconciliation" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByText(/Automatic registration is not approved/)).toBeInTheDocument();
    expect(calls.some((call) => call.path === "/api/projects/identity/preview")).toBe(true);
  });

  it("registers eligible workspaces only with explicit confirmation", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/software" && method === "GET") return json(softwareInventory);
      if (path === "/api/projects/identity/preview" && method === "GET")
        return json({
          root: "C:\\Projects",
          policy: { auto_register: false, approved_at: null, approved_root: null },
          counts: { eligible: 1, needs_review: 0, skipped: 0, repositories: 1, book_legacy_preserved: 3 },
          eligible: [
            {
              path: "C:\\Projects\\writer",
              name: "writer",
              classification: "library",
              confidence: 0.7,
              evidence: [],
              repo_uid: "git-1",
              is_git: true,
              kind: "supporting",
              project_id: "writer",
              links: [{ path: "C:\\Projects\\writer", role: "primary" }],
              application_id: "writer",
            },
          ],
          needs_review: [],
          skipped: [],
          notes: [],
        });
      if (path === "/api/projects/identity/apply" && method === "POST")
        return json({ root: "C:\\Projects", created: [], skipped: [], counts: { created: 1, skipped: 0 }, policy: { auto_register: true, approved_at: "now", approved_root: "C:\\Projects" }, backup: null });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProjects();

    await user.click(await screen.findByRole("button", { name: "Discovery & reconciliation" }));
    const dialog = await screen.findByRole("dialog");
    const applyButton = within(dialog).getByRole("button", { name: "Approve & register eligible" });
    expect(applyButton).toBeDisabled();

    await user.click(within(dialog).getByText(/I confirm this cutover/));
    expect(applyButton).not.toBeDisabled();
    await user.click(applyButton);

    await waitFor(() => {
      const apply = calls.find((call) => call.path === "/api/projects/identity/apply");
      expect(apply?.body).toMatchObject({ all_eligible: true, confirm: true, approve_policy: true });
    });
  });

  it("keeps the legacy book list behind the All scope", async () => {
    mockFetch(({ path, method }) => {
      if (path === "/api/projects/software" && method === "GET") return json({ total: 0, limit: 50, offset: 0, items: [] });
      if (path === "/api/projects" && method === "GET") return json([makeProject()]);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProjects();

    expect(await screen.findByText("No software projects yet")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "All incl. book legacy" }));
    expect(await screen.findByText("Language")).toBeInTheDocument();
  });
});

describe("Software project workspace", () => {
  function mockSoftware() {
    return mockFetch(({ path, method }) => {
      if (path === "/api/projects/writer" && method === "GET") return json(softwareDetail());
      if (path === "/api/projects/writer/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/writer/evidence-timeline" && method === "GET")
        return json({ workflows: [], observations: [] });
      if (path === "/api/projects/writer/git-links" && method === "GET") return json(gitLinks);
      if (path === "/api/git-activity/timeline" && method === "GET")
        return json({ items: [], total: 0, partial: false });
      if (path === "/api/git-activity/models" && method === "GET") return json({ models: [] });
      if (path === "/api/git-activity/context/gitrepo-1" && method === "GET")
        return json({ repo_id: "gitrepo-1", has_agents: true, has_description: false, context_status: "partial", nested_agents: [] });
      if (path === "/api/inspect/opportunities" && method === "GET")
        return json({ available: true, stale_refresh: false, total: 0, opportunities: [] });
      if (path === "/api/software-quality/charters" && method === "GET") return json([]);
      if (path === "/api/software-quality/evaluations" && method === "GET") return json([]);
      if (path === "/api/software-quality/findings" && method === "GET") return json([]);
      if (path === "/api/software-quality/prompts" && method === "GET") return json([]);
      if (path === "/api/cultivation/goals" && method === "GET") return json([]);
      if (path === "/api/applications" && method === "GET") return json([]);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
  }

  function renderWriter() {
    return renderRoute(
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>,
      "/projects/writer",
    );
  }

  it("renders engineering tabs with honest unassessed quality", async () => {
    mockSoftware();
    const user = userEvent.setup();
    renderWriter();

    for (const tab of ["Overview", "Activity", "Inspect", "Quality", "Improvements", "Context"]) {
      expect(await screen.findByRole("tab", { name: tab })).toBeInTheDocument();
    }
    expect(screen.queryByText("Manuscript quality")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Quality" }));
    expect(await screen.findByText("Unassessed")).toBeInTheDocument();
    expect(screen.getByText(/No quality evaluation has been recorded/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Project charter" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evaluate project" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Improvements" }));
    expect(await screen.findByText("Verify CLI")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Improvement prompts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
  });

  it("proposes a charter from evidence and starts an evaluation with prompt preview", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/writer" && method === "GET") return json(softwareDetail());
      if (path === "/api/projects/writer/integration-context" && method === "GET") return json([]);
      if (path === "/api/projects/writer/evidence-timeline" && method === "GET")
        return json({ workflows: [], observations: [] });
      if (path === "/api/software-quality/charters" && method === "GET") return json([]);
      if (path === "/api/software-quality/charters/propose" && method === "POST")
        return json({
          project_id: "writer", status: "draft",
          purpose: { value: "Authoring tools", source: "README.md head" },
          users: { value: "authors", source: "inferred" },
          capabilities: [], interfaces: [], acceptance: [], non_goals: [], constraints: [],
          lifecycle: { value: "active", source: "git" },
          dependencies: [], verification_expectations: { value: "", source: "" },
          note: "UNCONFIRMED",
        });
      if (path === "/api/software-quality/charters" && method === "POST")
        return json({ id: "sqcharter:1", project_id: "writer", revision: 1, status: "draft", purpose: "Authoring tools", users: "", capabilities: [], interfaces: [], acceptance: [], non_goals: [], constraints: [], lifecycle: "", dependencies: [], verification_expectations: "", evidence_refs: [], provenance: {}, supersedes: null, created_by: "owner", created_at: new Date().toISOString(), updated_at: new Date().toISOString() }, 201);
      if (path === "/api/software-quality/evaluations" && method === "GET") return json([]);
      if (path === "/api/software-quality/evidence" && method === "GET")
        return json({ fingerprint: "abc123", file_count: 10, evidence: [], truncated_total: false });
      if (path === "/api/software-quality/models" && method === "GET") return json({ models: [], detail: "" });
      if (path === "/api/software-quality/evaluations/preview" && method === "POST")
        return json({ prompt: "# eval prompt", prompt_hash: "abc", prompt_chars: 12, model: "m", route: "local", evidence_id_count: 3, evidence_fingerprint: "abc123", charter: null, rubric: { id: "software-quality-v1", version: 1 } });
      if (path === "/api/software-quality/evaluations" && method === "POST")
        return json({ id: "sqeval:1", project_id: "writer", status: "queued" }, 201);
      if (path === "/api/software-quality/findings" && method === "GET") return json([]);
      if (path === "/api/software-quality/prompts" && method === "GET") return json([]);
      if (path === "/api/cultivation/goals" && method === "GET") return json([]);
      if (path === "/api/applications" && method === "GET") return json([]);
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderWriter();

    await user.click(await screen.findByRole("tab", { name: "Quality" }));
    await user.click(await screen.findByRole("button", { name: "Propose from evidence" }));
    await user.click(screen.getByRole("button", { name: "Generate evidence-based draft" }));
    expect(await screen.findByText(/UNCONFIRMED/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.path === "/api/software-quality/charters")).toBe(true);
    });

    await user.click(screen.getByRole("button", { name: "Evaluate project" }));
    await user.click(await screen.findByRole("button", { name: "Preview prompt" }));
    expect(await screen.findByText("# eval prompt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Execute evaluation" }));
    await waitFor(() => {
      const started = calls.find((call) => call.method === "POST" && call.path === "/api/software-quality/evaluations");
      expect(started?.body).toMatchObject({ project_id: "writer" });
    });
  });

  it("shows commit activity and context readiness per repository", async () => {
    mockSoftware();
    const user = userEvent.setup();
    renderWriter();

    await user.click(await screen.findByRole("tab", { name: "Activity" }));
    expect(await screen.findByText(/No commits indexed in the last 30 days/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prepare evidence package" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Context" }));
    expect(await screen.findByText("no DESCRIPTION.md")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /propose update/ })).toBeInTheDocument();
  });
});
