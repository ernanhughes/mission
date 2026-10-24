import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WorkflowDetailPage } from "../pages/WorkflowDetailPage";
import { WorkflowsPage } from "../pages/WorkflowsPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeWorkflow } from "./fixtures";

function renderDetail() {
  return renderRoute(
    <Routes>
      <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
    </Routes>,
    "/workflows/wf-fixture-1",
  );
}

describe("WorkflowsPage", () => {
  it("lists real workflow traces and links to their detail", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/workflows") return json([makeWorkflow()]);
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<WorkflowsPage />, "/workflows");
    expect(await screen.findByRole("heading", { name: "Experiments" })).toBeInTheDocument();
    expect(await screen.findByText(/TraceLite proxy: Fixture research candidate/)).toBeInTheDocument();
    expect(screen.getByText(/Tests passed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /TraceLite proxy/i })).toHaveAttribute(
      "href",
      "/workflows/wf-fixture-1",
    );
  });
});

describe("WorkflowDetailPage", () => {
  it("shows the full trace and records a human accept decision", async () => {
    let decided = false;
    const calls = mockFetch(({ path, method, body }) => {
      if (path === "/api/workflows/wf-fixture-1" && method === "GET")
        return json(
          decided
            ? makeWorkflow({ status: "decided", final_decision: "accept", final_reason: "Proxy passed." })
            : makeWorkflow(),
        );
      if (path === "/api/workflows/wf-fixture-1/decision" && method === "POST") {
        decided = true;
        return json(makeWorkflow({ status: "decided", final_decision: "accept", final_reason: "Proxy passed." }));
      }
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderDetail();

    expect(await screen.findByRole("heading", { name: /TraceLite proxy: Fixture research candidate/ })).toBeInTheDocument();
    expect(screen.getByText(/Repeated trace events can be compacted/)).toBeInTheDocument();
    expect(screen.getByText("tracelite/reduce.py")).toBeInTheDocument();
    expect(screen.getAllByText("21")).toHaveLength(3);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("86%")).toBeInTheDocument();
    expect(screen.getByText(/No high\/medium findings/)).toBeInTheDocument();
    expect(screen.getByText("Research Imported")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Decision reason"), "Proxy passed.");
    await user.click(screen.getByRole("button", { name: /Accept outcome/ }));

    await waitFor(() => {
      const decision = calls.find((call) => call.path.endsWith("/decision"));
      expect(decision?.body).toEqual({
        decision: "accept",
        reason: "Proxy passed.",
        override_adverse: false,
      });
    });
    expect(await screen.findByText("Final decision")).toBeInTheDocument();
    expect(screen.getAllByText("Proxy passed.").length).toBeGreaterThan(0);
  });

  it("requires an explicit override when CoCoder reports an adverse review", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/workflows/wf-fixture-1")
        return json(
          makeWorkflow({
            adverse_review: true,
            review_summary: { available: true, findings: 1, high: 1, medium: 0, changed_files: 1, sample: [] },
          }),
        );
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderDetail();

    const accept = await screen.findByRole("button", { name: /Accept outcome/ });
    expect(accept).toBeDisabled();
    expect(screen.getByText(/explicit human override/i)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/explicitly override/i));
    expect(accept).toBeEnabled();
  });
});
