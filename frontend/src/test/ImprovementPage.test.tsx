import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ImprovementPage } from "../features/improvement/ImprovementPage";
import { json, mockFetch, renderRoute } from "./helpers";

describe("Improvement page", () => {
  it("creates an inert Work Outcome proposal from a selected Mission finding", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/health") return json({ status: "ok", version: "test", ai_enabled: true });
      if (path === "/api/work-episodes") return json({ episodes: [{ id: "ep:ai:42", title: "AI shared inference", project_key: "ai", status: "established" }] });
      if (path === "/api/work-evaluation/findings") return json({ findings: [{ id: "finding-1", episode_id: "ep:ai:42", title: "Execution evidence needs review", kind: "verification_gap", status: "open", severity: "minor" }] });
      if (path === "/api/work-corrective/proposals" && method === "GET") return json({ proposals: [] });
      if (path === "/api/work-envelopes") return json({ envelopes: [] });
      if (path === "/api/harness/catalogue") return json({ worker: { reachable: true, status: "ok", version: "test" }, strategies: [] });
      if (path === "/api/praxis/proposals") return json([]);
      if (path === "/api/improvement/records") return json({ status: "unavailable", source: "isolated_sc3_artifacts" });
      if (path === "/api/improvement/integration") return json({ mission_to_stephanie: { status: "unavailable", reason: "test not configured" } });
      if (path === "/api/improvement/investigations") return json({ status: "unavailable", investigations: [] });
      if (path === "/api/work-corrective/proposals" && method === "POST") return json({ status: "completed", proposal_id: "wp:bounded-1" });
      throw new Error(`Unhandled request ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Opportunities" }));
    await user.selectOptions(await screen.findByLabelText("Work Episode"), "ep:ai:42");
    await user.click(await screen.findByLabelText(/Execution evidence needs review/));
    await user.click(screen.getByRole("button", { name: "Create governed investigation request" }));

    expect(await screen.findByRole("link", { name: "Review proposal wp:bounded-1" })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((call) => call.path === "/api/work-corrective/proposals" && call.method === "POST")).toBe(true));
    const body = calls.find((call) => call.path === "/api/work-corrective/proposals" && call.method === "POST")?.body as Record<string, any>;
    expect(body.episode_id).toBe("ep:ai:42");
    expect(body.finding_ids).toEqual(["finding-1"]);
    expect(body.action_category).toBe("REQUEST_USER_DECISION");
    expect(body.exclusions).toContain("No production changes");
    expect(calls.some((call) => call.path.includes("sc3-run"))).toBe(false);
  });

  it("reports connected Worker state from the current catalogue", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/health") return json({ status: "ok" });
      if (path === "/api/work-episodes") return json({ episodes: [] });
      if (path === "/api/work-corrective/proposals") return json({ proposals: [] });
      if (path === "/api/work-envelopes") return json({ envelopes: [] });
      if (path === "/api/harness/catalogue") return json({ worker: { reachable: true, status: "ok" }, strategies: [] });
      if (path === "/api/praxis/proposals") return json([]);
      if (path === "/api/improvement/records") return json({ status: "unavailable", source: "isolated_sc3_artifacts" });
      if (path === "/api/improvement/integration") return json({ mission_to_stephanie: { status: "unavailable", reason: "test not configured" } });
      if (path === "/api/improvement/investigations") return json({ status: "unavailable", investigations: [] });
      throw new Error(`Unhandled request ${path}`);
    });
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("Reachable")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Opportunities" }));
    expect(await screen.findByText("No Work Episodes available")).toBeInTheDocument();
  });

  it("requests a source-bound investigation only through an approved Mission proposal", async () => {
    let savedInvestigation: Record<string, any> | null = null;
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/health") return json({ status: "ok" });
      if (path === "/api/work-episodes") return json({ episodes: [{ id: "ep:worker:1", title: "Worker", project_key: "worker" }] });
      if (path === "/api/work-evaluation/findings") return json({ findings: [{ id: "finding-1", episode_id: "ep:worker:1", title: "Empty response classification", kind: "defect", status: "open", severity: "moderate" }] });
      if (path === "/api/work-corrective/proposals" && method === "GET") return json({ proposals: [{ id: "wp:approved-1", episode_id: "ep:worker:1", finding_ids: ["finding-1"], action_category: "REQUEST_USER_DECISION", status: "approved", objective: "Investigate the finding" }] });
      if (path === "/api/work-envelopes") return json({ envelopes: [] });
      if (path === "/api/harness/catalogue") return json({ worker: { reachable: true, status: "ok" }, strategies: [] });
      if (path === "/api/praxis/proposals") return json([]);
      if (path === "/api/improvement/records") return json({ status: "unavailable" });
      if (path === "/api/improvement/integration") return json({ mission_to_stephanie: { status: "available" } });
      if (path === "/api/improvement/investigations" && method === "GET") return json({ status: "available", investigations: savedInvestigation ? [savedInvestigation] : [] });
      if (path === "/api/improvement/investigations" && method === "POST") {
        savedInvestigation = {
        investigation_id: "mission-1234567890abcdef12345678", source_identity: "mission:episode/ep:worker:1/finding/finding-1", source_digest: "abc",
        status: "completed", result: "REQUEST_ADDITIONAL_EVIDENCE", hypothesis: { statement: "The observed finding may warrant a bounded investigation.", rationale: "Deterministic restatement.", uncertainty: "Cause remains unknown." }, candidate: null, proposed_experiments: [], retrieved_experience: [], authority: "investigation only" };
        return json({ status: "completed", investigation: savedInvestigation });
      }
      throw new Error(`Unhandled request ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: "Opportunities" }));
    await user.selectOptions(await screen.findByLabelText("Work Episode"), "ep:worker:1");
    await user.click(await screen.findByLabelText(/Empty response classification/));
    await user.selectOptions(await screen.findByLabelText("Approved Mission decision request"), "wp:approved-1");
    await user.click(screen.getByRole("button", { name: "Request Stephanie investigation" }));
    expect(await screen.findByText("The observed finding may warrant a bounded investigation.")).toBeInTheDocument();
    const call = calls.find((item) => item.path === "/api/improvement/investigations" && item.method === "POST");
    expect(call?.body).toEqual({ proposal_id: "wp:approved-1", episode_id: "ep:worker:1", finding_id: "finding-1" });
  });

  it("requires a separate reviewed decision and matching envelope before dispatch", async () => {
    const investigationId = "mission-1234567890abcdef12345678";
    const investigation = {
      investigation_id: investigationId, source_identity: "mission:episode/ep:worker:2/finding/f1", source_digest: "src-digest",
      source_snapshot: { episode_id: "ep:worker:2", finding_id: "f1" }, status: "completed", result: "PROPOSE_DETERMINISTIC_FIXTURE_EXPERIMENT",
      hypothesis: { statement: "Hypothesis" }, candidate: { candidate_id: "candidate-1" },
      proposed_experiments: [{ experiment_id: "experiment-1", candidate_id: "candidate-1", candidate_digest: "candidate-digest", protocol_digest: "protocol-digest", resource_limits: { requests: 8 } }],
    };
    const scope = JSON.stringify({ investigation_id: investigationId });
    let authorized = false;
    let envelopes: Array<Record<string, any>> = [];
    let resultReady = false;
    let humanDecision: Record<string, any> | null = null;
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/health") return json({ status: "ok" });
      if (path === "/api/work-episodes") return json({ episodes: [] });
      if (path === "/api/work-corrective/proposals") return json({ proposals: authorized ? [{ id: "wp:experiment", episode_id: "ep:worker:2", finding_ids: ["f1"], action_category: "REQUEST_USER_DECISION", status: "approved", scope, version: 1, scope_hash: "scope-hash", acceptance_criteria: "Preserve all experiment outcomes" }] : [] });
      if (path === "/api/work-envelopes" && method === "GET") return json({ envelopes });
      if (path === "/api/work-intent/objectives") return json({ objectives: [{ id: "ob:worker:2", episode_id: "ep:worker:2", text: "Bounded fixture", status: "current" }] });
      if (path === "/api/harness/catalogue") return json({ worker: { reachable: true, status: "ok" }, strategies: [] });
      if (path === "/api/praxis/proposals") return json([]);
      if (path === "/api/improvement/records") return json({ status: "unavailable" });
      if (path === "/api/improvement/integration") return json({ mission_to_stephanie: { status: "available" } });
      if (path === "/api/improvement/investigations" && method === "GET") return json({ status: "available", investigations: [investigation] });
      if (path === `/api/improvement/investigations/${investigationId}`) return json({ experiment_state: resultReady ? "completed" : "not_dispatched", human_decisions: humanDecision ? [humanDecision] : [], retained_experience: { status: "available", records: [{ name: "prior experiment", outcome: "reject", scenario: "C3", reuse_eligible: false, promotion_status: "NOT_PROMOTED", matched_terms: 2 }] }, experiment_result: resultReady ? { experiment_id: "experiment-1", formal_acceptance: "UNKNOWN", actual_model_invocations: 0, praxis_comparisons: [] } : null });
      if (path === "/api/improvement/experiment-authorizations" && method === "POST") return json({ status: "decision_requested", proposal_id: "wp:experiment" });
      if (path === "/api/work-envelopes" && method === "POST") {
        envelopes = [{ id: "we:1", envelope_id: "we:1", episode_id: "ep:worker:2", objective_ref: "ob:worker:2", authorization_ref: "proposal:wp:experiment@v1:scope-hash", originating_findings: ["f1"], status: "active" }];
        return json({ status: "completed", envelope_id: "we:1" });
      }
      if (path === "/api/improvement/experiments/dispatch" && method === "POST") { resultReady = true; return json({ status: "completed" }); }
      if (path === `/api/improvement/investigations/${investigationId}/decision` && method === "POST") { humanDecision = { decision: (calls.at(-1)?.body as any)?.decision, actor: "Reviewer", evidence: { experiment_id: "experiment-1", result_digest: "digest-1" } }; return json({ status: "completed" }); }
      throw new Error(`Unhandled request ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: "Investigations" }));
    await user.click(await screen.findByRole("button", { name: /mission-1234567890abcdef12345678/ }));
    await user.selectOptions(await screen.findByLabelText("Mission Work Objective"), "ob:worker:2");
    await user.click(screen.getByRole("button", { name: "Request separate experiment decision" }));
    expect(await screen.findByRole("link", { name: "Review experiment decision wp:experiment" })).toBeInTheDocument();
    expect(calls.some((call) => call.path === "/api/improvement/experiments/dispatch")).toBe(false);

    authorized = true;
    await user.click(screen.getByRole("button", { name: "Refresh approval state" }));
    await user.click(await screen.findByRole("button", { name: "Register matching Work Envelope" }));
    await user.selectOptions(await screen.findByLabelText("Authorized active Work Envelope"), "we:1");
    await user.click(screen.getByRole("button", { name: "Execute frozen experiment once" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/api/improvement/experiments/dispatch" && call.method === "POST")).toBe(true));
    expect(await screen.findByText(/formal acceptance UNKNOWN/)).toBeInTheDocument();
    expect(await screen.findByText(/prior experiment · C3/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Human decision maker"), "Reviewer");
    await user.click(screen.getByRole("button", { name: "Accept candidate result" }));
    expect(await screen.findByText(/Human candidate decision: accepted/)).toBeInTheDocument();
    expect(calls.find((call) => call.path === `/api/improvement/investigations/${investigationId}/decision`)?.body).toEqual({ proposal_id: "wp:experiment", decision: "accepted", actor: "Reviewer", rationale: "" });
    expect(calls.find((call) => call.path === "/api/improvement/experiments/dispatch")?.body).toEqual({ proposal_id: "wp:experiment", envelope_id: "we:1", investigation_id: investigationId });
  });
});

function renderPage() {
  renderRoute(<Routes><Route path="/improvement" element={<ImprovementPage />} /><Route path="/activity" element={<div>Work Evaluation link target</div>} /></Routes>, "/improvement");
}
