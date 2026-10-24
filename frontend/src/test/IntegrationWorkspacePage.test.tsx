import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntegrationWorkspacePage } from "../pages/IntegrationWorkspacePage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import {
  makeCoCoderRecord,
  makeIntegration,
  makeIntegrationRecord,
  makeProject,
  makeWorkRecord,
} from "./fixtures";

const execution = {
  id: "exec-1",
  application_id: "cocoder",
  application_name: "CoCoder",
  action_id: "run_review",
  parameters: { repo_path: "C:\\Projects\\mission" },
  status: "succeeded",
  risk: "bounded_local_computation",
  approval_required: true,
  approved_at: "2026-10-24T00:00:00+00:00",
  started_at: "2026-10-24T00:00:01+00:00",
  ended_at: "2026-10-24T00:00:12+00:00",
  exit_code: 0,
  output: "Wrote review.json",
  error: null,
  result: { findings: 2, changed_files: 4 },
  artifact_ref: "C:\\data\\integrations\\cocoder\\review.json",
  created_at: "2026-10-24T00:00:00+00:00",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("IntegrationWorkspacePage", () => {
  it("opens a real Next record and records a local-only decision", async () => {
    let decided = false;
    const record = makeIntegrationRecord();
    const calls = mockFetch(({ path, method, body }) => {
      if (path === "/api/integrations/next") return json(makeIntegration());
      if (path === "/api/projects") return json([makeProject()]);
      if (path === "/api/integrations/next/resources" && method === "GET")
        return json([record]);
      if (path === `/api/integrations/next/resources/${record.id}`)
        return json({
          ...record,
          local_decision: decided
            ? {
                id: "idec-1",
                application_id: "next",
                resource_type: "next_opportunity",
                external_id: record.external_id,
                decision: "shortlist",
                reason: "Worth a bounded review.",
                sync_state: "local_only",
                source_decision_id: null,
                decided_at: "2026-10-24T00:01:00+00:00",
                created_at: "2026-10-24T00:01:00+00:00",
              }
            : null,
        });
      if (path === `/api/integrations/next/resources/${record.id}/decision` && method === "POST") {
        decided = true;
        return json({
          id: "idec-1",
          application_id: "next",
          resource_type: "next_opportunity",
          external_id: record.external_id,
          decision: (body as { decision: string }).decision,
          reason: (body as { reason: string }).reason,
          sync_state: "local_only",
          source_decision_id: null,
          decided_at: "2026-10-24T00:01:00+00:00",
          created_at: "2026-10-24T00:01:00+00:00",
        });
      }
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<IntegrationWorkspacePage appId="next" />, "/next");

    expect(await screen.findByText("Live integration available")).toBeInTheDocument();
    expect(screen.getByText(/130 opportunities/i)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Candidates" }));
    const row = await screen.findByRole("button", { name: /Fixture Next recommendation/i });
    await user.click(row);

    expect(
      await screen.findByRole("heading", { name: "Fixture Next recommendation" }),
    ).toBeInTheDocument();
    expect(screen.getByText("A mechanism worth testing.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Shortlist" }));
    await waitFor(() => {
      const decisionCall = calls.find((call) => call.path.endsWith("/decision"));
      expect(decisionCall?.body).toEqual({ decision: "shortlist", reason: "" });
    });

    const localDecision = await screen.findByText("shortlist");
    expect(localDecision).toBeInTheDocument();
    expect(screen.getByText("Sync: local only")).toBeInTheDocument();
    expect(screen.getByText(/Source application state is not modified/i)).toBeInTheDocument();
  });

  it("renders Work qualification and preserves source-versus-local distinction", async () => {
    const record = makeWorkRecord();
    mockFetch(({ path }) => {
      if (path === "/api/integrations/work")
        return json(
          makeIntegration({
            application_id: "work",
            name: "Work",
            adapter: "work",
            mode: "cli-json",
            detail: "Read 130 opportunities from Work's JSON CLI (63 qualified).",
            resource_counts: { work_opportunity: 130 },
            repository_path: "C:\\Projects\\work",
            config: { arguments: ["opportunities", "--json"], limit: 300 },
          }),
        );
      if (path === "/api/projects") return json([makeProject()]);
      if (path === "/api/integrations/work/resources") return json([record]);
      if (path === `/api/integrations/work/resources/${record.id}`) return json(record);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<IntegrationWorkspacePage appId="work" />, "/work");

    await user.click(await screen.findByRole("tab", { name: "Opportunities" }));
    await user.click(await screen.findByRole("button", { name: /Fixture qualified opportunity/i }));

    expect(await screen.findByRole("heading", { name: "Fixture qualified opportunity" })).toBeInTheDocument();
    expect(screen.getByText("Fixture Buyer")).toBeInTheDocument();
    expect(screen.getByText("Ireland")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Verify eligibility before committing time.")).toBeInTheDocument();
    expect(screen.getByText(/Listed value is not earned income/i)).toBeInTheDocument();

    const decisionBox = screen.getByText("Human decision").closest(".decision-box");
    expect(decisionBox).not.toBeNull();
    expect(
      within(decisionBox as HTMLElement).getByText(/Saved locally in Mission Control/i),
    ).toBeInTheDocument();
  });

  it("runs the registered CoCoder review action for an allowed repository", async () => {
    const record = makeCoCoderRecord();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    let submitted: Record<string, unknown> | null = null;
    const calls = mockFetch(({ path, method, body }) => {
      if (path === "/api/integrations/cocoder")
        return json(
          makeIntegration({
            application_id: "cocoder",
            name: "CoCoder",
            adapter: "cocoder",
            mode: "cli-artifact",
            detail: "Read 1 review artifact and 1 finding.",
            capabilities: ["list_resources", "execute_action"],
            resource_counts: { cocoder_review: 1, cocoder_finding: 1 },
            repository_path: "C:\\Projects\\cocoder",
            repositories: [
              { path: "C:\\Projects\\mission", name: "Mission Control", source: "Mission Control" },
            ],
            actions: [
              {
                id: "run_review",
                title: "Run a bounded CoCoder review",
                description: "Runs the configured CoCoder CLI against a registered repository.",
                risk: "bounded_local_computation",
                capability: "execute_action",
                approval_required: true,
                side_effect: "local_generated_artifacts",
                parameters_schema: { type: "object", required: ["repo_path"] },
                enabled: true,
                unavailable_reason: null,
              },
            ],
          }),
        );
      if (path === "/api/projects") return json([makeProject()]);
      if (path === "/api/integrations/executions") return json([execution]);
      if (path === "/api/integrations/cocoder/resources") return json([record]);
      if (path === "/api/integrations/cocoder/actions/run_review/execute" && method === "POST") {
        submitted = body as Record<string, unknown>;
        return json({ ...execution, status: "queued", ended_at: null, output: "" });
      }
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<IntegrationWorkspacePage appId="cocoder" />, "/cocoder");

    await user.click(await screen.findByRole("tab", { name: "Operations" }));
    expect(await screen.findByText("Run a bounded CoCoder review")).toBeInTheDocument();
    expect(screen.getByText(/Queued is not completed/i)).toBeInTheDocument();

    const executionToggle = await screen.findByRole("button", { name: /run_review/i });
    await user.click(executionToggle);
    expect(await screen.findByText("Wrote review.json")).toBeInTheDocument();
    expect(screen.getByText(/Risk: Bounded Local Computation/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Run bounded review/i }));
    await waitFor(() => {
      expect(submitted).not.toBeNull();
      const parameters = submitted?.parameters as Record<string, unknown>;
      expect(submitted?.confirm).toBe(true);
      expect(parameters.repo_path).toBe("C:\\Projects\\mission");
      expect(parameters.base).toBe("HEAD~1");
      expect(parameters.head).toBe("HEAD");
    });
    expect(confirm).toHaveBeenCalled();
    const actionCall = calls.find((call) => call.path.endsWith("/execute"));
    expect(actionCall?.method).toBe("POST");
    confirm.mockRestore();
  });
});
