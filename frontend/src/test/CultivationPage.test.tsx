import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CultivationHud } from "../features/cultivation/CultivationHud";
import { CultivationPage } from "../pages/CultivationPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import type { CultivationGoal, CultivationSkill } from "../types/api";

function makeGoal(overrides: Partial<CultivationGoal> = {}): CultivationGoal {
  return {
    id: "published_books",
    name: "Published Books",
    description: "",
    category: "books",
    unit: "books",
    target_value: 100,
    measurement_type: "count",
    baseline_value: 30,
    baseline_note: "Owner estimate",
    baseline_provenance: "estimate",
    qualifying_stage: "published",
    window_days: null,
    recurring_mode: "daily",
    priority: 10,
    state: "active",
    pinned: true,
    pin_order: 0,
    privacy: "standard",
    completion_criteria: "",
    milestones: [1, 10, 25, 50, 75, 100],
    dependencies: [],
    evidence_source: "manual",
    skill_id: "blog-posts",
    skill_name: "Blog Posts",
    created_at: "2026-11-09T00:00:00Z",
    updated_at: "2026-11-09T00:00:00Z",
    progress: {
      current: 30,
      target: 100,
      unit: "books",
      percent: 30,
      unknown_reason: null,
      achieved: false,
      estimate_label: "≈30 (30 estimate + 0 tracked)",
      item_count: 0,
      pipeline: {},
      milestones_reached: [1, 10, 25],
      next_milestone: 50,
      live_observed: null,
      live_sync_at: null,
      live_stale: false,
      disagreement: null,
    },
    ...overrides,
  };
}

const ranks = [
  { id: "initiate", name: "Initiate", concept: "First work", qualified: true, requires: {} },
];

export function makeSkill(overrides: Partial<CultivationSkill> = {}): CultivationSkill {
  return {
    id: "software-development",
    name: "Software Development",
    icon: "git-branch",
    category: "software",
    description: "",
    pinned: false,
    pin_order: 100,
    state: "active",
    created_at: "2026-11-09T00:00:00Z",
    updated_at: "2026-11-09T00:00:00Z",
    goals_total: 0,
    goals_achieved: 0,
    item_completions: 0,
    goals: [],
    ...overrides,
  };
}

const config = {
  stages: [
    { id: "idea", label: "Idea", color: "grey" },
    { id: "published", label: "Published / completed", color: "green" },
  ],
  ranks: [],
};

function mockCultivation(extra?: (call: { path: string; method: string; body: unknown }) => Response | undefined) {
  return mockFetch((call) => {
    if (extra) {
      const response = extra(call);
      if (response) return response;
    }
    if (call.path === "/api/cultivation/goals") return json([makeGoal()]);
    if (call.path === "/api/cultivation/ranks") return json(ranks);
    if (call.path === "/api/cultivation/config") return json(config);
    if (call.path === "/api/cultivation/skills")
      return json([
        {
          id: "blog-posts", name: "Blog Posts", icon: "rss", category: "writing",
          description: "", pinned: true, pin_order: 0, state: "active",
          created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          goals_total: 1, goals_achieved: 0, item_completions: 0,
          goals: [
            { id: "published_books", name: "Published Books", unit: "books", state: "active", progress: makeGoal().progress },
          ],
        },
      ]);
    if (call.path === "/api/cultivation/cycles")
      return json([
        {
          id: "cyc-1", number: 5, name: "Cycle V", length_days: 100, start_date: null,
          snapshot_day: 50, snapshot_note: "Reported position", state: "active", notes: "",
          created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          day: { day: 50, mode: "snapshot", length_days: 100, past_length: false, label: "Cycle V — Day 50 / 100" },
          focus_goal_ids: ["published_books"],
          progress: { window: null, focus: [{ goal_id: "published_books", goal_name: "Published Books", completions_in_window: null, current: 30 }] },
        },
      ]);
    if (call.path === "/api/cultivation/sources")
      return json([
        {
          id: "src-software",
          name: "Activity projects",
          kind: "activity_projects",
          skill_id: "software-development",
          goal_id: "repositories",
          path: "",
          config: {},
          last_sync_at: "2026-11-09T00:00:00Z",
          last_status: "ok",
          last_error: null,
          fingerprint: "abc",
          observed: { repos_total: 1, by_qualification: { eligible: 1 }, by_lifecycle: {}, projects_linked: 0, roots: ["C:\\Projects"], fingerprint: "abc" },
          created_at: "2026-11-09T00:00:00Z",
          updated_at: "2026-11-09T00:00:00Z",
        },
      ]);
    if (call.path === "/api/cultivation/hud")
      return json({
        primary: {
          id: "published_books",
          name: "Published Books",
          unit: "books",
          state: "active",
          privacy: "standard",
          progress: makeGoal().progress,
        },
        pinned: [],
        rank: ranks[0],
        recent_completions: [],
        generated_at: "2026-11-09T00:00:00Z",
        cycle: {
          id: "cyc-1", number: 5, name: "Cycle V", length_days: 100, start_date: null,
          snapshot_day: 50, snapshot_note: "Reported position", state: "active", notes: "",
          created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          day: { day: 50, mode: "snapshot", length_days: 100, past_length: false, label: "Cycle V — Day 50 / 100" },
          focus_goal_ids: [],
          progress: { window: null, focus: [] },
        },
        pinned_skills: [
          {
            id: "blog-posts", name: "Blog Posts", icon: "rss", category: "writing",
            description: "", pinned: true, pin_order: 0, state: "active",
            created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
            goals_total: 1, goals_achieved: 0, item_completions: 0,
            goals: [
              { id: "published_books", name: "Published Books", unit: "books", state: "active", progress: makeGoal().progress },
            ],
          },
        ],
      });
    return apiError(404, `Unhandled ${call.path}`);
  });
}

describe("CultivationPage", () => {
  it("shows seeded goals with labelled estimates, not invented counts", async () => {
    mockCultivation();
    renderRoute(<CultivationPage />, "/cultivation");
    expect(await screen.findAllByText("Published Books")).not.toHaveLength(0);
    expect(await screen.findByText(/estimate \+ 0 tracked/)).toBeInTheDocument();
  });

  it("loads goal detail and advances an item stage", async () => {
    const calls = mockCultivation((call) => {
      if (call.path === "/api/cultivation/goals/published_books/items")
        return json([
          {
            id: "item-1",
            title: "Techno-Prophet",
            item_type: "book",
            notes: "",
            tags: [],
            provenance: "human",
            source_application: null,
            source_project_id: null,
            source_project_name: null,
            source_ref: null,
            created_at: "2026-11-09T00:00:00Z",
            updated_at: "2026-11-09T00:00:00Z",
            memberships: [
              {
                item_id: "item-1",
                goal_id: "published_books",
                goal_name: "Published Books",
                stage: "idea",
                evidence_status: "none",
                quality_evidence: {},
                qualified: false,
                qualified_at: null,
                completed_at: null,
                created_at: "2026-11-09T00:00:00Z",
                updated_at: "2026-11-09T00:00:00Z",
              },
            ],
          },
        ]);
      if (call.path === "/api/cultivation/goals/published_books/events") return json([]);
      if (call.path === "/api/cultivation/goals/published_books/evidence") return json([]);
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation?goal=published_books");
    await user.click(await screen.findByRole("button", { name: "→ Published / completed" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "PATCH" && call.path.endsWith("/stage"))).toBe(true);
    });
  });

  it("creates a goal through the modal", async () => {
    const calls = mockCultivation((call) => {
      if (call.path === "/api/cultivation/goals" && call.method === "POST")
        return json(makeGoal({ id: "goal-new", name: "New Venture" }), 201);
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation");
    await user.click(await screen.findByRole("button", { name: "New goal" }));
    await user.type(screen.getByLabelText("Name"), "New Venture");
    await user.click(screen.getByRole("button", { name: "Create goal" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.path === "/api/cultivation/goals")).toBe(true);
    });
  });
});

describe("CultivationHud", () => {
  it("renders pinned progress with GET requests only", async () => {
    const calls = mockCultivation();
    renderRoute(<CultivationHud />, "/");
    expect(await screen.findByText("Published Books")).toBeInTheDocument();
    expect(screen.getByText(/estimate \+ 0 tracked/)).toBeInTheDocument();
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("expands to pinned skills without any model call", async () => {
    const calls = mockCultivation();
    const user = userEvent.setup();
    renderRoute(<CultivationHud />, "/");
    await user.click(await screen.findByRole("button", { name: /Path to Published Books/ }));
    expect(await screen.findByText("Open cultivation")).toBeInTheDocument();
    expect(await screen.findByText("Blog Posts")).toBeInTheDocument();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
    expect(calls.some((call) => call.path.includes("chat") || call.path.includes("inference"))).toBe(false);
  });

  it("shows the cycle indicator without advancing a reported snapshot", async () => {
    mockCultivation();
    renderRoute(<CultivationHud />, "/");
    expect(await screen.findByText(/Cycle V — Day 50 \/ 100/)).toBeInTheDocument();
  });
});

describe("Cultivation blue theme", () => {
  it("clamps over-target progress to a full bar with an achieved state", async () => {
    mockCultivation((call) => {
      if (call.path === "/api/cultivation/goals") {
        const over = makeGoal({
          name: "Blog Posts",
          target_value: 100,
          progress: {
            ...makeGoal().progress,
            current: 137,
            percent: 100,
            achieved: true,
            estimate_label: "137 / 100 books observed",
          },
        });
        return json([over]);
      }
      return undefined;
    });
    renderRoute(<CultivationPage />, "/cultivation");
    const bar = await screen.findByRole("progressbar", { name: "137 / 100 books observed" });
    expect(bar).toHaveAttribute("data-state", "over");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
    expect(await screen.findByText(/137 \/ 100 books/)).toBeInTheDocument();
  });

  it("renders unknown progress as unknown, never as zero", async () => {
    mockCultivation((call) => {
      if (call.path === "/api/cultivation/goals") {
        const unknown = makeGoal({
          name: "Body Weight",
          unit: "lb",
          progress: {
            ...makeGoal().progress,
            current: null,
            percent: null,
            achieved: false,
            estimate_label: null,
            unknown_reason: "Needs a starting baseline",
          },
        });
        return json([unknown]);
      }
      return undefined;
    });
    renderRoute(<CultivationPage />, "/cultivation");
    const bar = await screen.findByRole("progressbar", { name: "Needs a starting baseline" });
    expect(bar).toHaveAttribute("data-state", "unknown");
  });

  it("groups goals under skills and filters by search", async () => {
    mockCultivation();
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation");
    expect(await screen.findByText("Blog Posts")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Search goals…"), "zzz-no-match");
    await waitFor(() => {
      expect(screen.getByText("No goals in this skill yet.")).toBeInTheDocument();
    });
  });

  it("opens a skill with its repository inventory using GET requests only", async () => {
    const calls = mockCultivation((call) => {
      if (call.path === "/api/cultivation/skills/software-development")
        return json({
          id: "software-development",
          name: "Software Development",
          icon: "git-branch",
          category: "software",
          description: "",
          pinned: false,
          pin_order: 100,
          state: "active",
          created_at: "2026-11-09T00:00:00Z",
          updated_at: "2026-11-09T00:00:00Z",
          goals_total: 0,
          goals_achieved: 0,
          item_completions: 0,
          goals: [],
        });
      if (call.path === "/api/cultivation/goals" && call.method === "GET") return json([]);
      if (call.path === "/api/cultivation/repo-states")
        return json({
          items: [
            {
              repo_id: "gitrepo-1",
              repo_uid: "git-1",
              name: "demo",
              path: "C:\\Projects\\demo",
              root_path: "C:\\Projects",
              branch: "main",
              head_sha: "abc123",
              accessible: true,
              indexed: true,
              total_commits: 12,
              first_commit_ts: 1700000000,
              last_commit_ts: 1790000000,
              backfill_complete: true,
              last_indexed_at: "2026-11-09T00:00:00Z",
              has_agents: true,
              has_description: false,
              context_status: "partial",
              projects: [],
              qualification: "eligible",
              lifecycle_stage: null,
              classification: "unclassified",
              rationale: "12 commits indexed; eligible but requires explicit owner confirmation.",
              evidence: {},
              decided_by: "source",
              decided_at: null,
              last_seen_at: "2026-11-09T00:00:00Z",
              created_at: "2026-11-09T00:00:00Z",
              updated_at: "2026-11-09T00:00:00Z",
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        });
      if (call.path === "/api/cultivation/applications") return json([]);
      return undefined;
    });
    renderRoute(<CultivationPage />, "/cultivation?skill=software-development");
    expect(await screen.findByText("Repository inventory")).toBeInTheDocument();
    expect(await screen.findByText("demo")).toBeInTheDocument();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("pins a skill and creates a new one without touching goals", async () => {
    const calls = mockCultivation();
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation");
    await screen.findByText("Blog Posts");
    await user.click(screen.getByRole("button", { name: "Unpin" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "PATCH" && call.path.endsWith("/skills/blog-posts"))).toBe(true);
    });
    await user.type(screen.getByLabelText("New skill name"), "Poetry");
    await user.click(screen.getByRole("button", { name: "Add skill" }));
    await waitFor(() => {
      expect(
        calls.some((call) => call.method === "POST" && call.path === "/api/cultivation/skills"),
      ).toBe(true);
    });
  });

  it("shows the reconciliation notice when the source disagrees with the baseline", async () => {
    mockCultivation((call) => {
      if (call.path === "/api/cultivation/goals" && call.method === "GET")
        return json([
          makeGoal({
            name: "Published Books",
            progress: {
              ...makeGoal().progress,
              current: 3,
              estimate_label: "3 / 100 books observed",
              disagreement: "Source observes 3 but 100 user-attested prior achievements are recorded.",
            },
          }),
        ]);
      return undefined;
    });
    renderRoute(<CultivationPage />, "/cultivation?goal=published_books");
    expect(await screen.findByText(/Reconciliation required/)).toBeInTheDocument();
  });

  it("submits qualification with a required rationale", async () => {
    const calls = mockCultivation((call) => {
      if (call.path === "/api/cultivation/skills/software-development")
        return json({
          id: "software-development", name: "Software Development", icon: "git-branch",
          category: "software", description: "", pinned: false, pin_order: 100, state: "active",
          created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          goals_total: 0, goals_achieved: 0, item_completions: 0, goals: [],
        });
      if (call.path === "/api/cultivation/goals" && call.method === "GET")
        return json([
          makeGoal({ id: "repositories", name: "Repositories", unit: "repos", target_value: 1000 }),
          makeGoal(),
        ]);
      if (call.path === "/api/cultivation/repo-states")
        return json({
          items: [
            {
              repo_id: "gitrepo-1", repo_uid: "git-1", name: "demo",
              path: "C:\\Projects\\demo", root_path: "C:\\Projects", branch: "main",
              head_sha: "abc123", accessible: true, indexed: true, total_commits: 12,
              first_commit_ts: 1700000000, last_commit_ts: 1790000000, backfill_complete: true,
              last_indexed_at: "2026-11-09T00:00:00Z", has_agents: false, has_description: false,
              context_status: "missing", projects: [], qualification: "eligible",
              lifecycle_stage: null, classification: "unclassified", rationale: "",
              evidence: {}, decided_by: "source", decided_at: null,
              last_seen_at: "2026-11-09T00:00:00Z", created_at: "2026-11-09T00:00:00Z",
              updated_at: "2026-11-09T00:00:00Z", recent_commits: 3, review_count: 0,
            },
          ],
          total: 1, limit: 50, offset: 0,
        });
      if (call.path === "/api/cultivation/applications") return json([]);
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation?skill=software-development");
    await user.click(await screen.findByRole("button", { name: "Classify" }));
    await user.selectOptions(screen.getByLabelText("Qualification"), "qualified");
    await user.type(screen.getByLabelText(/Rationale/), "Real tool");
    await user.selectOptions(screen.getByLabelText("Count toward goal"), "published_books");
    await user.click(screen.getByRole("button", { name: "Save judgement" }));
    await waitFor(() => {
      expect(
        calls.some((call) => call.method === "PATCH" && call.path === "/api/cultivation/repo-states/gitrepo-1"),
      ).toBe(true);
    });
  });

  it("shows the GitHub-backed applications inventory with summary, not an empty state", async () => {
    const calls = mockCultivation((call) => {
      if (call.path === "/api/cultivation/skills/software-development")
        return json({
          id: "software-development", name: "Software Development", icon: "git-branch",
          category: "software", description: "", pinned: false, pin_order: 100, state: "active",
          created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          goals_total: 0, goals_achieved: 0, item_completions: 0, goals: [],
        });
      if (call.path === "/api/cultivation/goals" && call.method === "GET") return json([]);
      if (call.path === "/api/cultivation/sources")
        return json([
          {
            id: "src-github-repos", name: "GitHub repositories", kind: "github_repos",
            skill_id: "software-development", goal_id: "repositories", path: "",
            config: { account: "ernanhughes" },
            last_sync_at: "2026-11-09T00:00:00Z", last_status: "ok", last_error: null,
            fingerprint: "gh-abc",
            observed: { repos_total: 306, public: 183, private: 123, by_classification: { application: 120 } },
            created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z",
          },
        ]);
      if (call.path === "/api/cultivation/github/summary")
        return json({
          discovered: 306, private: 123, applications_identified: 120, books_identified: 17,
          completed_applications: 0, published_applications: 0,
          goals: { applications: { current: 0, target: 100, unit: "apps", percent: 0 } },
        });
      if (call.path === "/api/cultivation/repo-states")
        return json({
          items: [
            {
              repo_id: "gh-R_writer", repo_uid: "github:R_writer", name: "writer",
              path: null, root_path: "github", branch: "main", head_sha: null,
              accessible: true, indexed: false, total_commits: 0,
              first_commit_ts: null, last_commit_ts: null, backfill_complete: false,
              last_indexed_at: "2026-11-09T00:00:00Z", has_agents: false, has_description: true,
              context_status: "missing", projects: [], qualification: "discovered",
              lifecycle_stage: "unreviewed", classification: "application",
              rationale: "Inferred application", evidence: {}, decided_by: "undecided", decided_at: null,
              last_seen_at: "2026-11-09T00:00:00Z", created_at: "2026-11-09T00:00:00Z",
              updated_at: "2026-11-09T00:00:00Z", recent_commits: 0, review_count: 0,
              origin: "github", url: "https://github.com/ernanhughes/writer",
              description: "AI authoring", visibility: "PRIVATE", language: "Python",
              private: true, fork: false, pushed_at: "2026-11-09T00:00:00Z", missing: false,
            },
          ],
          total: 306, limit: 50, offset: 0,
        });
      if (call.path === "/api/cultivation/applications") return json([]);
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CultivationPage />, "/cultivation?skill=software-development");
    expect(await screen.findByText(/GitHub inventory/)).toBeInTheDocument();
    expect(await screen.findByText("writer")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Refresh GitHub" })).toBeInTheDocument();
    expect(screen.queryByText("No applications registered yet.")).toBeInTheDocument();
    expect(screen.queryByText("No applications match")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh GitHub" }));
    await waitFor(() => {
      expect(
        calls.some((call) => call.method === "POST" && call.path === "/api/cultivation/sources/src-github-repos/sync"),
      ).toBe(true);
    });
  });
});
