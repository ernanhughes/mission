import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { ProjectPage } from "../pages/ProjectPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeAdapter, makeProjectDetail, makeTask, makeWorkRecord } from "./fixtures";

function renderProject() {
  return renderRoute(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectPage />} />
    </Routes>,
    "/projects/math",
  );
}

describe("ProjectPage", () => {
  it("saves a checkpoint and completes a task through the API", async () => {
    const detail = makeProjectDetail({
      id: "math",
      name: "Math",
      tasks: [
        makeTask({
          id: "task-math",
          project_id: "math",
          project_name: "Math",
          title: "Inspect proof obligations",
        }),
      ],
      recommendations: [],
      adapters: [
        makeAdapter({
          available: false,
          detail: "Work has no verified read-only opportunity export configured.",
          capabilities: [],
        }),
      ],
    });
    const linked = makeWorkRecord({ id: "res-work-linked", project_id: "math", project_name: "Math" });
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/projects/math" && method === "GET") return json(detail);
      if (path === "/api/projects/math/integration-context" && method === "GET")
        return json([linked]);
      if (path === "/api/checkpoints" && method === "POST")
        return json({
          id: "cp-new",
          project_id: "math",
          project_name: "Math",
          summary: "Reviewed proof obligations.",
          last_completed: "Read report",
          next_action: "Check composition.",
          blockers: "",
          evidence_refs: ["artifacts/math01/report.json"],
          milestone: "MATH01",
          source: "user",
          created_at: new Date().toISOString(),
        });
      if (path === "/api/tasks/task-math" && method === "PATCH")
        return json({ ...detail.tasks[0], status: "done" });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderProject();

    expect(await screen.findByRole("heading", { name: "Math" })).toBeInTheDocument();
    expect(screen.getByText("Work has no verified read-only opportunity export configured.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Cross-application context" })).toBeInTheDocument();
    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fixture qualified opportunity/i })).toHaveAttribute(
      "href",
      "/work?record=res-work-linked",
    );

    await user.type(screen.getByLabelText("What happened?"), "Reviewed proof obligations.");
    await user.type(screen.getByLabelText("Next intended action"), "Check composition.");
    await user.type(screen.getByLabelText("Milestone (optional)"), "MATH01");
    await user.type(screen.getByLabelText("Evidence references (one per line)"), "artifacts/math01/report.json");
    await user.click(screen.getByRole("button", { name: "Save checkpoint" }));

    await waitFor(() => {
      const checkpoint = calls.find(
        (call) => call.method === "POST" && call.path === "/api/checkpoints",
      );
      expect(checkpoint).toBeTruthy();
      expect(checkpoint?.body).toMatchObject({
        project_id: "math",
        summary: "Reviewed proof obligations.",
        next_action: "Check composition.",
        milestone: "MATH01",
      });
    });

    await user.click(screen.getByRole("button", { name: "Edit Inspect proof obligations" }));
    const titleInput = screen.getByLabelText("Edit title for Inspect proof obligations");
    await user.clear(titleInput);
    await user.type(titleInput, "Inspect all proof obligations");
    await user.click(screen.getByRole("button", { name: "Save task title" }));
    await waitFor(() => {
      const patches = calls.filter(
        (call) => call.method === "PATCH" && call.path === "/api/tasks/task-math",
      );
      expect(patches.some((call) => (call.body as { title?: string }).title === "Inspect all proof obligations")).toBe(true);
    });

    await user.click(screen.getByRole("button", { name: "Complete Inspect proof obligations" }));
    await waitFor(() => {
      const patches = calls.filter(
        (call) => call.method === "PATCH" && call.path === "/api/tasks/task-math",
      );
      expect(patches.some((call) => (call.body as { status?: string }).status === "done")).toBe(true);
    });
  });
});
