import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CultivationHud } from "../features/cultivation/CultivationHud";
import { CultivationPage } from "../pages/CultivationPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import type { CultivationGoal } from "../types/api";

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
    priority: 10,
    state: "active",
    pinned: true,
    pin_order: 0,
    privacy: "standard",
    completion_criteria: "",
    milestones: [1, 10, 25, 50, 75, 100],
    dependencies: [],
    evidence_source: "manual",
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
    },
    ...overrides,
  };
}

const ranks = [
  { id: "initiate", name: "Initiate", concept: "First work", qualified: true, requires: {} },
];

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
      });
    return apiError(404, `Unhandled ${call.path}`);
  });
}

describe("CultivationPage", () => {
  it("shows seeded goals with labelled estimates, not invented counts", async () => {
    mockCultivation();
    renderRoute(<CultivationPage />, "/cultivation");
    expect(await screen.findByText("Published Books")).toBeInTheDocument();
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

  it("expands to pinned goals without any model call", async () => {
    const calls = mockCultivation();
    const user = userEvent.setup();
    renderRoute(<CultivationHud />, "/");
    await user.click(await screen.findByRole("button", { name: /Path to Published Books/ }));
    expect(await screen.findByText("Open cultivation")).toBeInTheDocument();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
    expect(calls.some((call) => call.path.includes("chat") || call.path.includes("inference"))).toBe(false);
  });
});
