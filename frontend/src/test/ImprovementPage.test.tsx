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
      throw new Error(`Unhandled request ${path}`);
    });
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("Reachable")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Opportunities" }));
    expect(await screen.findByText("No Work Episodes available")).toBeInTheDocument();
  });
});

function renderPage() {
  renderRoute(<Routes><Route path="/improvement" element={<ImprovementPage />} /><Route path="/activity" element={<div>Work Evaluation link target</div>} /></Routes>, "/improvement");
}
