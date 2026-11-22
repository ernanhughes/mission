import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CultivationPage } from "../pages/CultivationPage";
import { json, mockFetch, renderRoute } from "./helpers";

const observed = {
  published: 137,
  drafts: 4,
  unknown: 1,
  excluded: 12,
  candidates: 154,
  scheduled: 1,
  tech_published: 40,
  finance_published: 5,
  latest_published_at: "2026-11-20T10:00:00+00:00",
  latest_published_title: "Second Post",
  week_start: "2026-11-16T00:00:00+01:00",
  week_end: "2026-11-22T23:59:59+01:00",
  week_start_date: "2026-11-16",
  week_end_date: "2026-11-22",
  timezone: "Europe/Dublin",
  this_week: 3,
  last_week: 1,
  weekly_award: { level: "gold", label: "Gold", colour: "gold", this_week: 3 },
  recent_posts: [
    { identity: "second.md", title: "Second Post", relpath: "second.md", date: "2026-11-20T10:00:00+00:00" },
    { identity: "first.md", title: "First Post", relpath: "first.md", date: "2026-11-18T10:00:00+00:00" },
    { identity: "older.md", title: "Older Post", relpath: "older.md", date: "2026-11-10T10:00:00+00:00" },
  ],
};

function makeGoal(id: string, name: string) {
  return {
    id,
    name,
    description: "",
    category: "writing",
    unit: "posts",
    target_value: 100,
    measurement_type: "count",
    baseline_value: 100,
    baseline_note: "User-attested",
    baseline_provenance: "user_assertion",
    qualifying_stage: "published",
    window_days: null,
    recurring_mode: "daily",
    priority: 20,
    state: "active",
    pinned: true,
    pin_order: 10,
    privacy: "standard",
    completion_criteria: "",
    milestones: [1, 10, 25, 50, 75, 100],
    dependencies: [],
    evidence_source: "hugo_blog",
    skill_id: "blog-posts",
    skill_name: "Blog Posts",
    created_at: "2026-11-09T00:00:00Z",
    updated_at: "2026-11-09T00:00:00Z",
    progress: {
      current: 137,
      target: 100,
      unit: "posts",
      percent: 100,
      unknown_reason: null,
      achieved: true,
      estimate_label: "137 / 100 posts observed 2026-11-20",
      item_count: 137,
      pipeline: { published: 137, draft: 4 },
      milestones_reached: [1, 10, 25, 50, 75, 100],
      next_milestone: null,
      live_observed: 137,
      live_sync_at: "2026-11-20T12:00:00Z",
      live_stale: false,
      disagreement: null,
    },
  };
}

function mockBlog() {
  return mockFetch(({ path }) => {
    if (path === "/api/cultivation/goals")
      return json([
        makeGoal("blog_posts", "Blog Posts"),
        {
          ...makeGoal("weekly_blog", "Weekly Blog Post"),
          measurement_type: "recurring",
          recurring_mode: "period",
          window_days: 7,
          target_value: 1,
        },
      ]);
    if (path === "/api/cultivation/goals/blog_posts/items") return json([]);
    if (path === "/api/cultivation/goals/blog_posts/events") return json([]);
    if (path === "/api/cultivation/goals/blog_posts/evidence") return json([]);
    if (path === "/api/cultivation/goals/weekly_blog/items") return json([]);
    if (path === "/api/cultivation/goals/weekly_blog/events") return json([]);
    if (path === "/api/cultivation/goals/weekly_blog/evidence") return json([]);
    if (path === "/api/cultivation/skills") return json([]);
    if (path === "/api/cultivation/ranks") return json([]);
    if (path === "/api/cultivation/config")
      return json({ stages: [{ id: "idea", label: "Idea", color: "grey" }, { id: "published", label: "Published", color: "green" }], ranks: [] });
    if (path === "/api/cultivation/cycles") return json([]);
    if (path === "/api/cultivation/sources")
      return json([
        {
          id: "src-blog-posts",
          name: "programmer.ie posts",
          kind: "hugo_blog",
          skill_id: "blog-posts",
          goal_id: "blog_posts",
          path: "C:\\websites\\programmer.ie\\content\\post",
          config: { period_goal_id: "weekly_blog" },
          last_sync_at: "2026-11-20T12:00:00Z",
          last_status: "ok",
          last_error: null,
          fingerprint: "abc",
          observed,
          created_at: "2026-11-09T00:00:00Z",
          updated_at: "2026-11-20T12:00:00Z",
        },
      ]);
    return json([]);
  });
}

describe("Blog publishing awards (MC-WEBSITES-CULTIVATION-01)", () => {
  it("shows lifetime count, weekly award ladder and the latest two posts", async () => {
    mockBlog();
    renderRoute(<CultivationPage />, "/cultivation?goal=blog_posts");
    expect(await screen.findByText("Publishing awards")).toBeInTheDocument();
    expect(await screen.findByText(/Lifetime published:/)).toBeInTheDocument();
    expect(await screen.findByText("Gold", { exact: true })).toBeInTheDocument();
    const ladder = await screen.findByLabelText(/Publishing award progress: 3 this week/);
    expect(ladder).toBeInTheDocument();
    // Latest two posts come from the scan, newest first.
    const latestHeading = await screen.findByText("Latest published posts");
    const latestBlock = latestHeading.parentElement as HTMLElement;
    expect(latestBlock.textContent).toContain("Second Post");
    expect(latestBlock.textContent).toContain("First Post");
    expect(latestBlock.textContent).not.toContain("Older Post");
  });

  it("weekly goal shares the same authoritative observation via the period link", async () => {
    mockBlog();
    renderRoute(<CultivationPage />, "/cultivation?goal=weekly_blog");
    // The weekly panel renders from the linked blog source observation.
    expect(await screen.findByText("Weekly publication")).toBeInTheDocument();
    expect((await screen.findAllByText("Second Post")).length).toBeGreaterThan(0);
  });
});
