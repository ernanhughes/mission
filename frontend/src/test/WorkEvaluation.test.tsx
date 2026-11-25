import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ActivityPage } from "../pages/ActivityPage";
import { apiError, json, mockFetch as baseMockFetch, renderRoute } from "./helpers";
import type { ApiCall } from "./helpers";

function mockFetch(handler: (call: ApiCall) => Response) {
  return baseMockFetch(handler);
}

function safeDecode(path: string): string {
  try {
    return decodeURIComponent(path);
  } catch {
    return path;
  }
}

function base(handler?: (call: ApiCall) => Response) {
  return mockFetch((raw) => {
    const call: ApiCall = { ...raw, path: safeDecode(raw.path) };
    if (call.path === "/api/git-activity/timeline")
      return json({ items: [], total: 0, partial: false, limit: 100, offset: 0 });
    if (call.path === "/api/git-activity/summary")
      return json({ commits_today: 0, projects_today: 0, commits_week: 0, commits_reviewed: 0, commits_indexed: 0, repos_indexed: 0, backfill_pending: 0, complete: true });
    if (call.path === "/api/git-activity/repos") return json([]);
    if (call.path === "/api/git-activity/roots") return json([]);
    if (call.path === "/api/git-activity/scan") return json({ running: false, status: "complete" });
    if (call.path === "/api/activity") return json({ items: [] });
    if (handler) return handler(call);
    return apiError(404, `Unhandled ${call.path}`);
  });
}

const overviewPayload = (episodes: unknown[]) => ({ episodes, total: episodes.length, project_key: null });

const epRow = (overrides: Record<string, unknown> = {}) => ({
  id: "ep:task:AI-CORE-01",
  project_key: "ai",
  title: "AI-CORE-01",
  kind: "task",
  status: "established",
  parent_id: null,
  first_seen_ms: 1,
  last_seen_ms: 2,
  source_digest: "abc",
  version: 1,
  completion: "incomplete",
  execution: "unknown",
  outcome: "unknown",
  evaluated: true,
  stale: false,
  open_findings: 1,
  mandatory_open: 1,
  ...overrides,
});

describe("Work Evaluation tab", () => {
  it("adds a Work Evaluation tab without breaking existing tabs", async () => {
    const user = userEvent.setup();
    base(() => json(overviewPayload([])));
    renderRoute(<ActivityPage />, "/activity");
    expect(await screen.findByRole("tab", { name: "Work Evaluation" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Commits" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /events/i })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect(await screen.findByText("No work episodes reconstructed")).toBeInTheDocument();
  });

  it("loads overview read-only: no POST on tab open", async () => {
    const user = userEvent.setup();
    const calls = base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([epRow()]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect(await screen.findByText("AI-CORE-01")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    expect(calls.some((c) => c.path === "/api/work-evaluation/overview")).toBe(true);
  });

  it("shows needs-attention first with honest labels", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview")
        return json(overviewPayload([epRow(), epRow({ id: "ep:x", title: "Done", completion: "complete", open_findings: 0, mandatory_open: 0 })]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect((await screen.findAllByText("Needs attention")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Incomplete").length).toBeGreaterThanOrEqual(1);
  });

  it("filters episodes by completion state", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview")
        return json(overviewPayload([
          epRow(),
          epRow({ id: "ep:y", title: "Evaluated unknown", completion: null }),
        ]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Work Episodes" }));
    expect(await screen.findByText("AI-CORE-01")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Filter by completion"), "incomplete");
    expect(screen.queryByText("Evaluated unknown")).toBeNull();
  });

  it("shows empty states honestly", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect(await screen.findByText("No work episodes reconstructed")).toBeInTheDocument();
  });

  it("shows backend failures honestly", async () => {
    const user = userEvent.setup();
    base(() => apiError(503, "Evaluation service is not available"));
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect(await screen.findByText(/unavailable/i)).toBeInTheDocument();
  });

  it("episode detail separates claims from verified outcomes", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([epRow()]));
      if (call.path === "/api/work-episodes/ep:task:AI-CORE-01")
        return json({ id: "ep:task:AI-CORE-01", title: "AI-CORE-01", kind: "task", status: "established", associations: [], children: [], first_seen_ms: 1, last_seen_ms: 2 });
      if (call.path === "/api/work-evaluation/episodes/ep:task:AI-CORE-01")
        return json({
          assessment: {
            id: "a1", episode_id: "ep:task:AI-CORE-01",
            execution: { verdict: "unknown", rationale: "" },
            outcome: { verdict: "unknown", rationale: "" },
            completion: { verdict: "incomplete", rationale: "mandatory unsatisfied" },
            evaluator: "deterministic", rubric_version: "w4-v1",
          },
          requirements: [],
          claims: [{ id: "c1", episode_id: "ep:task:AI-CORE-01", claimant: "assistant", text: "All tests passed", scope: "s", source_ref: "opencode:s1:5", qualified: false, evidence_available: false }],
          findings: [{ id: "f1", episode_id: "ep:task:AI-CORE-01", requirement_id: null, kind: "unsupported_claim", severity: "major", status: "suspected", title: "Unsupported", rationale: "r", evidence_refs: [], next_action: "verify" }],
        });
      if (call.path === "/api/work-intent/requirements") return json({ requirements: [] });
      if (call.path === "/api/work-intent/claims")
        return json({ claims: [{ id: "c1", episode_id: "ep:task:AI-CORE-01", claimant: "assistant", text: "All tests passed", scope: "s", source_ref: "opencode:s1:5", qualified: false, evidence_available: false }] });
      if (call.path === "/api/work-evaluation/findings")
        return json({ findings: [{ id: "f1", episode_id: "ep:task:AI-CORE-01", requirement_id: null, kind: "unsupported_claim", severity: "major", status: "suspected", title: "Unsupported", rationale: "r", evidence_refs: [], next_action: "verify" }] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Work Episodes" }));
    await user.click(await screen.findByRole("button", { name: "Inspect episode" }));
    await user.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(await screen.findByText(/assertions from the work record/)).toBeInTheDocument();
    expect(await screen.findByText("All tests passed")).toBeInTheDocument();
  });

  it("episode envelope tab is read-only: shows empty state without POST", async () => {
    const user = userEvent.setup();
    const calls = base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([epRow()]));
      if (call.path === "/api/work-episodes/ep:task:AI-CORE-01")
        return json({ id: "ep:task:AI-CORE-01", title: "AI-CORE-01", kind: "task", status: "established", associations: [], children: [], first_seen_ms: 1, last_seen_ms: 2 });
      if (call.path === "/api/work-evaluation/episodes/ep:task:AI-CORE-01")
        return json({ assessment: null, requirements: [], claims: [], findings: [] });
      if (call.path === "/api/work-intent/requirements") return json({ requirements: [] });
      if (call.path === "/api/work-intent/claims") return json({ claims: [] });
      if (call.path === "/api/work-intent/confirmations") return json({ confirmations: [] });
      if (call.path === "/api/work-envelopes") return json({ envelopes: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Work Episodes" }));
    await user.click(await screen.findByRole("button", { name: "Inspect episode" }));
    await user.click(screen.getByRole("tab", { name: "Envelope" }));
    expect(await screen.findByText("No prospective envelope")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("coverage view uses the read contract without invented numbers", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([epRow()]));
      if (call.path === "/api/work-intent/triage")
        return json({ triage: [{ session_id: "s1", classification: "TRIVIAL_INTERACTION", method: "deterministic", reason: "probe", queued_for_model: false, run_id: null }] });
      if (call.path === "/api/work-evaluation/coverage")
        return json({ episode_assessments: 1, completion_mix: { unknown: 1 }, requirements_assessed: 2, claims_verified: 3, findings: 1, project_key: "all", model_calls: 0 });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Coverage" }));
    expect(await screen.findByText("Requirements assessed")).toBeInTheDocument();
    expect(screen.getByText("TRIVIAL_INTERACTION")).toBeInTheDocument();
  });

  it("outstanding view prioritizes mandatory work", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      if (call.path === "/api/work-evaluation/findings")
        return json({
          findings: [
            { id: "f1", episode_id: "ep:a", requirement_id: "r1", kind: "missing_requirement", severity: "major", status: "suspected", title: "Missing", rationale: "r", evidence_refs: [], next_action: "implement" },
            { id: "f2", episode_id: "ep:a", requirement_id: null, kind: "verification_gap", severity: "minor", status: "suspected", title: "Unverified", rationale: "r", evidence_refs: [], next_action: "supply evidence" },
          ],
        });
      if (call.path === "/api/work-evaluation/findings/groups") return json({ groups: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Outstanding Work" }));
    // Groups mode is the default: empty groups show the aggregate empty state.
    expect(await screen.findByText("No open finding groups")).toBeInTheDocument();
    // Drill into individual findings without losing the grouped default.
    await user.click(screen.getByRole("tab", { name: "Individual findings" }));
    expect(await screen.findByText("Missing")).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("groups identical assertions and keeps member counts visible", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      if (call.path === "/api/work-evaluation/findings/groups")
        return json({
          groups: [
            { id: "wg:1", project_key: "ai", subject: "abc", gap_class: "missing_test_evidence", title: "Unverified test report × 25", sample_title: "Unverified test report: 214 passed", severity: "minor", status: "open", member_count: 25, member_ids: [], episode_ids: ["ep:task:AI-CORE-05"], members: [{ id: "f1", episode_id: "ep:task:AI-CORE-05" }] },
          ],
        });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Outstanding Work" }));
    expect(await screen.findByText(/Missing test evidence × 25/)).toBeInTheDocument();
    expect(screen.getByText("1 group(s) · 25 underlying finding(s) · nothing hidden")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /underlying finding/ }));
    expect(await screen.findByText(/ep:task:AI-CORE-05/)).toBeInTheDocument();
  });

  it("controls panel is read-only until clicked: no POST on open", async () => {
    const user = userEvent.setup();
    const calls = base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      if (call.path === "/api/work-evaluation/eval-queue") return json({ queue: [] });
      if (call.path === "/api/work-evaluation/eval-state") return json({ state: [] });
      if (call.path === "/api/work-evaluation/auto") return json({ auto_enabled: false, last_run: null, paid_budget_usd: 0 });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Controls" }));
    expect(await screen.findByText(/Scheduled evaluation:/)).toBeInTheDocument();
    expect(screen.getByText("Queue empty")).toBeInTheDocument();
    const posts = calls.filter((c) => c.method === "POST");
    expect(posts).toEqual([]);
  });

  it("overview surfaces stale evaluations", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview")
        return json(overviewPayload([epRow({ stale: true, stale_reason: "new_commit", queue_status: "stale" })]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      if (call.path === "/api/work-evaluation/findings/groups") return json({ groups: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    expect(await screen.findByText(/Stale: new_commit/)).toBeInTheDocument();
  });

  it("proposals tab is read-only until clicked: no POST on open", async () => {
    const user = userEvent.setup();
    const calls = base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      if (call.path === "/api/work-corrective/proposals") return json({ proposals: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Proposals" }));
    expect(await screen.findByText("No corrective proposals")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("generates a corrective commission from a group and previews it", async () => {
    const user = userEvent.setup();
    base((call) => {
      if (call.path === "/api/work-evaluation/overview") return json(overviewPayload([]));
      if (call.path === "/api/work-evaluation/findings") return json({ findings: [] });
      if (call.path === "/api/work-evaluation/findings/groups")
        return json({
          groups: [
            { id: "wg:9", project_key: "ai", subject: "s", gap_class: "missing_merge_provenance", title: "Missing merge provenance × 2", sample_title: "Unverified completion claim: merge to main", severity: "minor", status: "open", member_count: 2, member_ids: ["f1", "f2"], episode_ids: ["ep:task:AI-CORE-05"], members: [{ id: "f1", episode_id: "ep:task:AI-CORE-05" }, { id: "f2", episode_id: "ep:task:AI-CORE-05" }] },
          ],
        });
      if (call.path === "/api/work-corrective/proposals" && call.method === "POST")
        return json({ status: "completed", proposal_id: "wp:test1", action_category: "RECOVER_EXISTING_EVIDENCE" });
      if (call.path === "/api/work-corrective/proposals") return json({ proposals: [] });
      return apiError(404, `Unhandled ${call.path}`);
    });
    renderRoute(<ActivityPage />, "/activity");
    await user.click(screen.getByRole("tab", { name: "Work Evaluation" }));
    await user.click(screen.getByRole("tab", { name: "Outstanding Work" }));
    expect(await screen.findByText(/Missing merge provenance × 2/)).toBeInTheDocument();
    expect(screen.getByText(/RECOVER_EXISTING_EVIDENCE/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate corrective commission" }));
    expect(await screen.findByText(/Commission draft ready/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open proposals/ }));
    expect(await screen.findByText("No corrective proposals")).toBeInTheDocument();
  });
});
