import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ScriptsPage } from "../pages/ScriptsPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";

const STATUS = {
  root: "C:\\script",
  library_key: "C:\\script",
  configured: true,
  exists: true,
  is_dir: true,
  readable: true,
  writable: true,
  status: "ok",
  last_sync_at: "2026-11-11T10:00:00+00:00",
  last_error: null,
  fingerprint: "abc",
  observed: {},
  counts: { total: 67, by_status: { discovered: 65, completed: 2 }, completed: 2, ready: 1, needs_review: 3, present: 67, archived: 0, missing: 0 },
  duplicate_numbers: { "52": ["a", "b"] },
  duplicate_content: { deadbeefdeadbeef: ["a", "b"] },
  extensions: [".md"],
  week: { week_start: "2026-11-09T00:00:00+00:00", week_end: "2026-11-15T23:59:59+00:00", week_start_date: "2026-11-09", week_end_date: "2026-11-15", label: "Week of 2026-11-09 (Mon–Sun, Europe/Dublin)", timezone: "Europe/Dublin" },
  libraries: ["C:\\script"],
};

const ROWS = [
  {
    id: "scr-2", library_key: "C:\\script", current_relpath: "Script002.md", original_relpath: "Script002.md",
    script_number: 2, title: "Script002", content_sha256: "x".repeat(64), file_size: 100, mtime_ns: 1,
    status: "draft", archived: false, missing: false, discovered_at: "2026-01-01T00:00:00+00:00",
    last_seen_at: "2026-11-11T00:00:00+00:00", completed_at: null, review_status: "none",
    last_review_at: null, legacy_item_id: null, created_at: "2026-01-01T00:00:00+00:00",
    updated_at: "2026-01-01T00:00:00+00:00", duplicate_number_group: null, duplicate_content_group: null,
    usage_count: 0, personal_rating: null, personal_target: "", personal_effect: "", last_used_at: null,
    latest_review: null,
    events: [], links: [],
  },
  {
    id: "scr-10", library_key: "C:\\script", current_relpath: "Script010.md", original_relpath: "Script010.md",
    script_number: 10, title: "Script010", content_sha256: "y".repeat(64), file_size: 100, mtime_ns: 2,
    status: "completed", archived: false, missing: false, discovered_at: "2026-01-01T00:00:00+00:00",
    last_seen_at: "2026-11-11T00:00:00+00:00", completed_at: "2026-11-10T00:00:00+00:00", review_status: "none",
    last_review_at: null, legacy_item_id: null, created_at: "2026-01-01T00:00:00+00:00",
    updated_at: "2026-01-01T00:00:00+00:00", duplicate_number_group: ["scr-10", "scr-10b"], duplicate_content_group: null,
    usage_count: 0, personal_rating: null, personal_target: "", personal_effect: "", last_used_at: null,
    latest_review: null,
    events: [{ id: "e1", event_type: "completed", from_value: "ready", to_value: "completed", note: "ok", created_at: "2026-11-10T00:00:00+00:00" }], links: [],
  },
];

function baseMocks() {
  return mockFetch(({ path, method }) => {
    if (path === "/api/scripts/status") return json(STATUS);
    if (path === "/api/scripts" && method === "GET") return json(ROWS);
    if (path === "/api/cultivation/goals") return json([{ id: "weekly_script", progress: { current: 1, target: 1 } }]);
    if (path.startsWith("/api/scripts/scr-") && path.endsWith("/content"))
      return json({ id: "scr-10", relpath: "Script010.md", title: "Script010", content: "# hello", truncated: false, content_sha256: "y".repeat(64), stored_sha256: "y".repeat(64), matches_stored: true });
    if (path.startsWith("/api/scripts/scr-")) return json(ROWS.find((row) => path.includes(row.id)) ?? ROWS[0]);
    if (path === "/api/scripts/sync") return json({ status: "ok" });
    if (path === "/api/scripts/bulk/status") return json({ count: 2, skipped: [] });
    if (path === "/api/scripts/relationships") return json({ relationships: [] });
    if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 1, completed_works: 1 });
    if (path === "/api/scripts/migrations") return json({ migrations: [] });
    return apiError(404, `Unhandled ${path}`);
  });
}

describe("Scripts library", () => {
  it("renders discovered/completed metrics and numeric sorting", async () => {
    baseMocks();
    renderRoute(<ScriptsPage />, "/scripts");
    expect(await screen.findByText("Scripts")).toBeInTheDocument();
    expect(await screen.findByText(/Discovered/)).toBeInTheDocument();
    const rows = await screen.findAllByRole("row");
    const text = rows.map((row) => row.textContent ?? "").join("\n");
    expect(text.indexOf("Script002")).toBeLessThan(text.indexOf("Script010"));
  });

  it("filters, selects and bulk-classifies", async () => {
    const calls = baseMocks();
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await screen.findByText("Script010");
    await user.type(screen.getByLabelText("Search scripts"), "010");
    await waitFor(() => {
      expect(calls.some((call) => call.path.startsWith("/api/scripts") && call.method === "GET")).toBe(true);
    });
    await user.clear(screen.getByLabelText("Search scripts"));
    const boxes = await screen.findAllByLabelText(/Select Script/);
    await user.click(boxes[0]);
    await user.click(screen.getByRole("button", { name: /Apply to 1/ }));
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/scripts/bulk/status")).toBe(true);
    });
  });

  it("opens detail with preview, history and duplicate warning", async () => {
    baseMocks();
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[1]);
    expect(await screen.findByText("Preview")).toBeInTheDocument();
    expect(await screen.findByText(/# hello/)).toBeInTheDocument();
    expect(await screen.findByText(/duplicate candidate/i)).toBeInTheDocument();
  });

  it("shows stale state distinctly from empty", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/scripts/status") return json({ ...STATUS, status: "stale", last_error: "unavailable" });
      if (path === "/api/scripts") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 1, completed_works: 1 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      return apiError(404, path);
    });
    renderRoute(<ScriptsPage />, "/scripts");
    expect(await screen.findByText(/Stale/)).toBeInTheDocument();
  });

  it("loads organisation data with works and relationships", async () => {
    baseMocks();
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Load organisation data" }));
    expect(await screen.findByText(/files in 1 work/)).toBeInTheDocument();
  });

  it("previews renumbering without changing files", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 2, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path === "/api/scripts/relationships/discover") return json({ proposed: 1 });
      if (path === "/api/scripts/migrations/preview")
        return json({
          migration_id: "mig-1",
          manifest_hash: "ab".repeat(32),
          manifest: {
            items: [
              { id: "scr-2", current: "Script002.md", proposed: "Script001.md", current_number: 2, proposed_number: 1, sha256: "x".repeat(64), status: "draft" },
              { id: "scr-10", current: "Script010.md", proposed: "Script002.md", current_number: 10, proposed_number: 2, sha256: "y".repeat(64), status: "completed" },
            ],
            references: [],
            collisions: [],
          },
        });
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Preview renumbering" }));
    expect(await screen.findByText("Migration preview (read-only)")).toBeInTheDocument();
    expect(await screen.findByText("Script001.md")).toBeInTheDocument();
    expect(calls.some((call) => call.path === "/api/scripts/migrations/preview")).toBe(true);
  });

  it("requests reviews and records effectiveness without touching the script", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path.endsWith("/content"))
        return json({ id: "scr-2", relpath: "Script002.md", title: "Script002", content: "# Two", truncated: false, content_sha256: "x".repeat(64), stored_sha256: "x".repeat(64), matches_stored: true });
      if (path.endsWith("/reviews") && method === "GET") return json({ reviews: [] });
      if (path.endsWith("/reviews") && method === "POST")
        return json({ id: "rev-1", script_id: "scr-2", content_sha256: "x".repeat(64), model: "m", route: "pi-default", provider: "p", assessment: { purpose: "Calm focus.", strengths: ["Rhythm."], weaknesses: ["Drift."], suggested_changes: ["Anchor."], estimated_spoken_seconds: 60, suitability: "Walking.", readiness: "needs_work" }, review_schema: "script-review-v1", freshness: "CURRENT", latency_ms: 1, created_at: "2026-11-11T00:00:00+00:00" }, 201);
      if (path.startsWith("/api/scripts/scr-")) return json(ROWS[0]);
      return apiError(404, path);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[0]);
    expect(await screen.findByText(/no scores assigned/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Request AI review" }));
    await waitFor(() => {
      expect(calls.some((call) => call.path.endsWith("/reviews") && call.method === "POST")).toBe(true);
    });
    await user.type(screen.getByLabelText("Personal target"), "focus");
    await user.click(screen.getByRole("button", { name: "Record effectiveness" }));
    await waitFor(() => {
      expect(calls.some((call) => call.path.endsWith("/effectiveness") && call.method === "PATCH")).toBe(true);
    });
  });

  it("loads intelligence coverage and starts a batch", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path === "/api/scripts/intelligence/coverage")
        return json({ coverage: { total: 2, current: 1, stale: 0, never: 1, by_script: {}, durations: { samples: 1, median_seconds: 300, min_seconds: 300, max_seconds: 300 }, completed: 0 }, purposes: { tags: { awareness: { ai: 1, user: 0 } } } });
      if (path === "/api/scripts/batches" && method === "GET") return json({ batches: [] });
      if (path === "/api/scripts/batches" && method === "POST")
        return json({ id: "bat-1", status: "open", counts: { total: 1, pending: 1, reviewed: 0, failed: 0, skipped: 0, reused: 0 }, items: [], model: "" });
      if (path === "/api/scripts/syntheses" && method === "GET") return json({ syntheses: [] });
      if (path.startsWith("/api/scripts/scr-")) return json(ROWS[0]);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Load intelligence" }));
    expect(await screen.findByText("Current reviews")).toBeInTheDocument();
    expect(await screen.findByText(/awareness \(1 AI\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start batch" }));
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/scripts/batches" && call.method === "POST")).toBe(true);
    });
  });

  it("generates and opens a synthesis with freshness", async () => {
    const syntheses = [{ id: "syn-1", library_key: "C:\\script", kind: "full", status: "complete", manifest: { review_refs: [{ script_id: "scr-2" }], unique_contents: 2 }, manifest_hash: "ab".repeat(32), report: { strengths: ["Steady rhythm."], weaknesses: ["Thin middle."], walking_suitable: ["scr-2"], review_priorities: [], themes: [{ name: "Breath", description: "Counting.", confidence: "medium" }] }, error: null, freshness: "CURRENT", created_at: "2026-11-11T00:00:00+00:00" }];
    mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path === "/api/scripts/intelligence/coverage")
        return json({ coverage: { total: 2, current: 2, stale: 0, never: 0, by_script: {}, durations: { samples: 0, median_seconds: null, min_seconds: null, max_seconds: null }, completed: 0 }, purposes: { tags: {} } });
      if (path === "/api/scripts/batches") return json({ batches: [] });
      if (path === "/api/scripts/syntheses" && method === "GET") return json({ syntheses });
      if (path === "/api/scripts/syntheses" && method === "POST") return json(syntheses[0]);
      if (path.endsWith("/content"))
        return json({ id: "scr-2", relpath: "Script002.md", title: "Script002", content: "# Two", truncated: false, content_sha256: "x".repeat(64), stored_sha256: "x".repeat(64), matches_stored: true });
      if (path.startsWith("/api/scripts/scr-")) return json(ROWS[0]);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Load intelligence" }));
    await user.click(screen.getByRole("button", { name: "Generate synthesis" }));
    await waitFor(() => {
      expect(screen.getByText("Library synthesis")).toBeInTheDocument();
    });
    const opens = screen.getAllByRole("button", { name: "Open" });
    await user.click(opens[opens.length - 1]);
    expect(await screen.findByText("Breath")).toBeInTheDocument();
  });

  it("loads candidates and promotes an accepted one", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const cand = { id: "cand-1", library_key: "C:\\script", title: "Ascendance — Awareness and Direction", version: "v2", kind: "ascendance", status: "accepted", content: "Step behind your eyes. Become aware.", word_count: 8, est_seconds: 5, validation: { within_five_minutes: true, cues_missing: [], safety_hits: [] }, critique: { deterministic: { findings: [], strengths: ["Cues."] }, pi: { skipped: true, reason: "no consent" } }, source_manifest: {}, provenance: { generator: "human-editorial" }, parent_candidate_id: "cand-0", promoted_script_id: null, promoted_relpath: null, created_at: "2026-11-11T00:00:00+00:00", updated_at: "2026-11-11T00:00:00+00:00" };
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 1, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path === "/api/scripts/batches") return json({ batches: [] });
      if (path === "/api/scripts/syntheses") return json({ syntheses: [] });
      if (path === "/api/scripts/intelligence/coverage") return json({ coverage: { total: 2, current: 0, stale: 0, never: 2, by_script: {}, durations: { samples: 0, median_seconds: null, min_seconds: null, max_seconds: null }, completed: 0 }, purposes: { tags: {} } });
      if (path === "/api/scripts/candidates" && method === "GET") return json({ candidates: [cand] });
      if (path === "/api/scripts/candidates/cand-1/promote") return json({ ...cand, status: "promoted", promoted_relpath: "Script068.md" });
      if (path.startsWith("/api/scripts/scr-")) return json(ROWS[0]);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Load candidates" }));
    expect(await screen.findByText(/Ascendance — Awareness and Direction/)).toBeInTheDocument();
    expect(screen.getByText("Validation passed: cues present, no safety hits, within duration.")).toBeInTheDocument();
    const opens = screen.getAllByRole("button", { name: "Open" });
    await user.click(opens[opens.length - 1]);
    await user.click(await screen.findByRole("button", { name: "Promote to library" }));
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/scripts/candidates/cand-1/promote")).toBe(true);
    });
    confirm.mockRestore();
  });

  it("requires approval binding before apply", async () => {
    const hash = "cd".repeat(32);
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/scripts/status") return json(STATUS);
      if (path === "/api/scripts" && method === "GET") return json(ROWS);
      if (path === "/api/cultivation/goals") return json([]);
      if (path === "/api/scripts/relationships") return json({ relationships: [] });
      if (path === "/api/scripts/works") return json({ works: [], work_count: 2, file_count: 2, completed_files: 0, completed_works: 0 });
      if (path === "/api/scripts/migrations") return json({ migrations: [] });
      if (path === "/api/scripts/migrations/preview")
        return json({
          migration_id: "mig-9",
          manifest_hash: hash,
          manifest: { items: [{ id: "scr-2", current: "Script002.md", proposed: "Script001.md", current_number: 2, proposed_number: 1, sha256: "x".repeat(64), status: "draft" }], references: [], collisions: [] },
        });
      if (path === "/api/scripts/migrations/mig-9/approve") {
        if (method === "POST") return json({ id: "mig-9", status: "approved" });
      }
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<ScriptsPage />, "/scripts");
    await user.click(screen.getByRole("button", { name: "Preview renumbering" }));
    await user.click(await screen.findByRole("button", { name: "Confirm migration" }));
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/scripts/migrations/mig-9/approve")).toBe(true);
    });
  });
});
