import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CostPage } from "../pages/CostPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";

afterEach(() => {
  vi.restoreAllMocks();
});

function summaryPayload() {
  return {
    available: true,
    source_path: "C:/fake/opencode.db",
    reason: "ok",
    error: null,
    date_label: "2026-11-22",
    timezone: "Europe/Dublin",
    start_ms: 1,
    end_ms: 2,
    totals: { requests: 5, recorded_cost: 0.04, input: 1000, output: 100, reasoning: 10, cache_read: 500, cache_write: 0 },
    by_model: [
      { model: "deepseek-v4.1-flash", provider: "opencode-go", variant: "max", requests: 3, recorded_cost: 0, input: 800, output: 80, reasoning: 0, cache_read: 400, cache_write: 0 },
      { model: "muse-spark-1.3-contributor", provider: "meta", variant: "xhigh", requests: 2, recorded_cost: 0.04, input: 200, output: 20, reasoning: 10, cache_read: 100, cache_write: 0 },
    ],
    by_project: [
      { project_id: "proj-mission", worktree: "C:/Projects/mission", name: "mission", sessions: 2, requests: 4, recorded_cost: 0.04, input: 900, output: 90, cache_read: 450 },
    ],
    timeline: [{ minute: "2026-11-22T22:10", requests: 5, recorded_cost: 0.04 }],
    failures: { go_limit: 1, no_route: 0, failed_idle: 1, subagent_errors: 1 },
    scanned: 5,
    truncated: false,
    provenance: "Local records only.",
  };
}

describe("CostPage", () => {
  it("loads cost from GET endpoints only and shows recorded vs allowance", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/cost/status")
        return json({ available: true, source_path: "C:/fake/opencode.db", reason: "ok", error: null, sessions: 3, messages: 7 });
      if (path === "/api/cost/summary") return json(summaryPayload());
      if (path === "/api/cost/sessions") return json({ available: true, source_path: "", reason: "ok", error: null, total: 1, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes") return json({ available: true, source_path: "", reason: "ok", error: null, date_label: "x", timezone: "Europe/Dublin", start_ms: 1, end_ms: 2, findings: [] });
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");

    expect(await screen.findByRole("heading", { name: "Cost" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("C:/Projects/mission")).toBeInTheDocument());
    expect(screen.getByText(/Go allowance use itself is not retained locally/)).toBeInTheDocument();

    // Zero AI calls on load: every fetch is GET.
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((c) => c.method === "GET")).toBe(true);
  });

  it("shows unavailable source explicitly instead of zeros", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/cost/status")
        return json({ available: false, source_path: "C:/fake/opencode.db", reason: "missing", error: "missing", sessions: 0, messages: 0 });
      if (path === "/api/cost/summary")
        return json({ available: false, source_path: "C:/fake/opencode.db", reason: "missing", error: "missing", date_label: "x", timezone: "Europe/Dublin", start_ms: 0, end_ms: 0, totals: { requests: 0, recorded_cost: 0, input: 0, output: 0, reasoning: 0, cache_read: 0, cache_write: 0 }, by_model: [], by_project: [], timeline: [], failures: {}, scanned: 0, truncated: false, provenance: "" });
      if (path === "/api/cost/sessions")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", total: 0, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", date_label: "x", timezone: "Europe/Dublin", start_ms: 0, end_ms: 0, findings: [] });
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");
    const matches = await screen.findAllByText(/Cost source unavailable/);
    expect(matches.length).toBeGreaterThan(0);
  });
});
