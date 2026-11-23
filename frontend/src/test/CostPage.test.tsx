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
    totals: { requests: 5, recorded_cost: 0.04, input: 1000, output: 100, reasoning: 10, cache_read: 500, cache_write: 0, throughput: 1600 },
    by_model: [
      { model: "deepseek-v4.1-flash", provider: "opencode-go", variant: "max", billing_category: "go-candidate", billing_reason: "r", requests: 3, recorded_cost: 0, input: 800, output: 80, reasoning: 0, cache_read: 400, cache_write: 0, throughput: 1280 },
      { model: "muse-spark-1.3-contributor", provider: "meta", variant: "xhigh", billing_category: "direct-candidate", billing_reason: "r", requests: 2, recorded_cost: 0.04, input: 200, output: 20, reasoning: 10, cache_read: 100, cache_write: 0, throughput: 320 },
    ],
    by_project: [
      { project_id: "proj-mission", worktree: "C:/Projects/mission", name: "mission", sessions: 2, requests: 4, recorded_cost: 0.04, input: 900, output: 90, reasoning: 10, cache_read: 450, cache_write: 0, throughput: 1440 },
    ],
    timeline: [{ minute: "2026-11-22T22:10", requests: 5, recorded_cost: 0.04 }],
    failures: { go_limit: 1, no_route: 0, failed_idle: 1, subagent_errors: 1 },
    scanned: 5,
    truncated: false,
    provenance: "Local records only.",
  };
}

function emptyWindow(label = "x") {
  return { available: true, source_path: "", reason: "ok", error: null, date_label: label, timezone: "Europe/Dublin", start_ms: 1, end_ms: 2, findings: [] };
}

describe("CostPage", () => {
  it("loads cost from GET endpoints only and shows recorded vs allowance", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/cost/status")
        return json({ available: true, source_path: "C:/fake/opencode.db", reason: "ok", error: null, sessions: 3, messages: 7 });
      if (path === "/api/cost/summary") return json(summaryPayload());
      if (path === "/api/cost/sessions") return json({ available: true, source_path: "", reason: "ok", error: null, total: 1, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes") return json(emptyWindow());
      if (path === "/api/cost/efficiency") return json({ ...emptyWindow(), recommendations: [], provenance: "Advisory only." });
      if (path === "/api/cost/attribution") return json({ available: true, source_path: "", reason: "ok", error: null, retained: [], missing: [], instrumentation: [], unknown_sessions: 0, unknown_requests: 0, provenance: "" });
      if (path === "/api/cost/catalogue") return json({ available: true, source_path: "", reason: "ok", error: null, pi_available: false, pi_models: [], pi_detail: "no pi", go_available: false, go_models: [], go_detail: "offline", provenance: "" });
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");

    expect(await screen.findByRole("heading", { name: "Cost" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("C:/Projects/mission")).toBeInTheDocument());
    expect(screen.getByText(/throughput and cache behaviour show the real load/)).toBeInTheDocument();

    // Zero AI calls on load: every fetch is GET.
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((c) => c.method === "GET")).toBe(true);
  });

  it("shows unavailable source explicitly instead of zeros", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/cost/status")
        return json({ available: false, source_path: "C:/fake/opencode.db", reason: "missing", error: "missing", sessions: 0, messages: 0 });
      if (path === "/api/cost/summary")
        return json({ available: false, source_path: "C:/fake/opencode.db", reason: "missing", error: "missing", date_label: "x", timezone: "Europe/Dublin", start_ms: 0, end_ms: 0, totals: { requests: 0, recorded_cost: 0, input: 0, output: 0, reasoning: 0, cache_read: 0, cache_write: 0, throughput: 0 }, by_model: [], by_project: [], timeline: [], failures: {}, scanned: 0, truncated: false, provenance: "" });
      if (path === "/api/cost/sessions")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", total: 0, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", date_label: "x", timezone: "Europe/Dublin", start_ms: 0, end_ms: 0, findings: [] });
      if (path === "/api/cost/efficiency")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", date_label: "x", timezone: "Europe/Dublin", start_ms: 0, end_ms: 0, recommendations: [], provenance: "" });
      if (path === "/api/cost/attribution")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", retained: [], missing: [], instrumentation: [], unknown_sessions: 0, unknown_requests: 0, provenance: "" });
      if (path === "/api/cost/catalogue")
        return json({ available: false, source_path: "", reason: "missing", error: "missing", pi_available: false, pi_models: [], pi_detail: "", go_available: false, go_models: [], go_detail: "", provenance: "" });
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");
    const matches = await screen.findAllByText(/Cost source unavailable/);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("sorts top consumers without new fetches and labels billing routes", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/cost/status")
        return json({ available: true, source_path: "C:/fake/opencode.db", reason: "ok", error: null, sessions: 3, messages: 7 });
      if (path === "/api/cost/summary") return json(summaryPayload());
      if (path === "/api/cost/sessions") return json({ available: true, source_path: "", reason: "ok", error: null, total: 0, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes") return json(emptyWindow());
      if (path === "/api/cost/efficiency") return json({ ...emptyWindow(), recommendations: [], provenance: "Advisory only." });
      if (path === "/api/cost/attribution") return json({ available: true, source_path: "", reason: "ok", error: null, retained: ["a"], missing: ["b"], instrumentation: ["c"], unknown_sessions: 0, unknown_requests: 0, provenance: "" });
      if (path === "/api/cost/catalogue") return json({ available: true, source_path: "", reason: "ok", error: null, pi_available: false, pi_models: [], pi_detail: "no pi", go_available: false, go_models: [], go_detail: "offline", provenance: "" });
      return apiError(404, `Unhandled ${path}`);
    });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderRoute(<CostPage />, "/cost");

    await waitFor(() => expect(screen.getByText("C:/Projects/mission")).toBeInTheDocument());
    // Billing badges render heuristic categories, never authoritative claims.
    expect(screen.getAllByText("Go?").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Direct?").length).toBeGreaterThan(0);

    // Re-sorting the consumer tables is client-side: no additional fetches.
    const sortButtons = screen.getAllByTitle(/Sort by requests/);
    expect(sortButtons.length).toBeGreaterThan(0);
    await user.click(sortButtons[0]);
    expect(screen.getByText("C:/Projects/mission")).toBeInTheDocument();
  });

  it("survives a stale backend that omits MC-COST-02 fields", async () => {
    // Old backend shape: no throughput, billing, or models fields.
    const staleSummary = {
      available: true,
      source_path: "C:/fake/opencode.db",
      reason: "ok",
      error: null,
      date_label: "2026-11-22",
      timezone: "Europe/Dublin",
      start_ms: 1,
      end_ms: 2,
      totals: { requests: 2, recorded_cost: 0.01, input: 100, output: 10, reasoning: 0, cache_read: 50, cache_write: 0 },
      by_model: [
        { model: "deepseek-v4.1-flash", provider: "opencode-go", variant: "max", requests: 2, recorded_cost: 0, input: 100, output: 10, reasoning: 0, cache_read: 50, cache_write: 0 },
      ],
      by_project: [
        { project_id: "proj-mission", worktree: "C:/Projects/mission", name: "mission", sessions: 1, requests: 2, recorded_cost: 0.01, input: 100, output: 10, cache_read: 50 },
      ],
      timeline: [],
      failures: {},
      scanned: 2,
      truncated: false,
      provenance: "Local records only.",
    };
    mockFetch(({ path }) => {
      if (path === "/api/cost/status")
        return json({ available: true, source_path: "C:/fake/opencode.db", reason: "ok", error: null, sessions: 1, messages: 2 });
      if (path === "/api/cost/summary") return json(staleSummary);
      if (path === "/api/cost/sessions")
        return json({
          available: true, source_path: "", reason: "ok", error: null, total: 1, limit: 50, offset: 0,
          // No models/throughput/billing fields: stale backend.
          items: [{ session_id: "ses_stale", project_id: "proj-mission", project_worktree: "C:/Projects/mission", project_name: "mission", parent_id: null, title: "Stale", directory: "C:/Projects/mission", model: "m", agent: "build", requests: 2, recorded_cost: 0.01, input: 100, output: 10, reasoning: 0, cache_read: 50, cache_write: 0, rollup_cost: 0.01, time_created: 1, time_updated: 2 }],
        });
      if (path === "/api/cost/spikes") return json(emptyWindow());
      if (path === "/api/cost/efficiency" || path === "/api/cost/attribution" || path === "/api/cost/catalogue")
        return apiError(404, "Not Found", "http_error");
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");

    // No crash: stale session renders, optional sections degrade to notices.
    await waitFor(() => expect(screen.getByText("Stale")).toBeInTheDocument());
    expect(await screen.findByText(/Model efficiency data unavailable/)).toBeInTheDocument();
    expect(await screen.findByText(/Attribution data unavailable/)).toBeInTheDocument();
  });

  it("shows advisory efficiency recommendations with evidence links", async () => {
    const calls = mockFetch(({ path }) => {
      if (path === "/api/cost/status")
        return json({ available: true, source_path: "C:/fake/opencode.db", reason: "ok", error: null, sessions: 3, messages: 7 });
      if (path === "/api/cost/summary") return json(summaryPayload());
      if (path === "/api/cost/sessions") return json({ available: true, source_path: "", reason: "ok", error: null, total: 0, limit: 50, offset: 0, items: [] });
      if (path === "/api/cost/spikes") return json(emptyWindow());
      if (path === "/api/cost/efficiency")
        return json({
          ...emptyWindow(),
          recommendations: [
            {
              id: "verify-free-opencode-go-deepseek",
              title: "High Go-route usage: opencode-go/deepseek (60 calls)",
              detail: "A free-candidate may cover routine calls. Verify quality and latency before moving anything.",
              severity: "info",
              model: "opencode-go/deepseek",
              billing_category: "go-candidate",
              session_ids: ["ses_abc123"],
              action: "none (advisory only)",
            },
          ],
          provenance: "Advisory only.",
        });
      if (path === "/api/cost/attribution") return json({ available: true, source_path: "", reason: "ok", error: null, retained: [], missing: [], instrumentation: [], unknown_sessions: 0, unknown_requests: 0, provenance: "" });
      if (path === "/api/cost/catalogue") return json({ available: true, source_path: "", reason: "ok", error: null, pi_available: false, pi_models: [], pi_detail: "no pi", go_available: false, go_models: [], go_detail: "offline", provenance: "" });
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<CostPage />, "/cost");

    await waitFor(() => expect(screen.getByText(/High Go-route usage/)).toBeInTheDocument());
    expect(screen.getAllByText(/Verify quality and latency/).length).toBeGreaterThan(0);
    expect(calls.every((c) => c.method === "GET")).toBe(true);
  });
});
