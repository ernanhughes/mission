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
  delete (window.navigator as unknown as { clipboard?: unknown }).clipboard;
});

function researchSession(overrides: Record<string, unknown> = {}) {
  return {
    id: "rcs-1",
    application_id: "next",
    resource_type: "next_opportunity",
    external_id: "next-fixture-1",
    record_id: "res-next-1",
    opportunity_title: "Fixture Next recommendation",
    context_schema: "mc.research-context.v1",
    context_fingerprint: "fingerprint-1",
    context_observed_at: "2026-10-23T12:00:00+00:00",
    model_route: "configured-local-openai",
    model_id: "qwen2.5:latest",
    model_local: true,
    provider: "openai-compatible",
    endpoint: "127.0.0.1",
    created_at: "2026-10-23T12:00:00+00:00",
    updated_at: "2026-10-23T12:00:00+00:00",
    message_count: 0,
    messages: [],
    context_stale: false,
    current_fingerprint: "fingerprint-1",
    freshness_notice: null,
    ...overrides,
  };
}

function chatMessage(
  id: string,
  sequence: number,
  role: "user" | "assistant",
  content: string,
) {
  return {
    id,
    session_id: "rcs-1",
    sequence,
    role,
    content,
    status: "completed",
    error: null,
    provider: role === "assistant" ? "openai-compatible" : null,
    model: role === "assistant" ? "qwen2.5:latest" : null,
    route: role === "assistant" ? "configured-local-openai" : null,
    metadata: role === "assistant" ? { local: true, latency_ms: 42 } : { local_only: true },
    created_at: "2026-10-23T12:00:00+00:00",
  };
}

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

  it("copies a structured review package without invoking a model", async () => {
    const record = makeIntegrationRecord();
    const writeText = vi.fn().mockResolvedValue(undefined);
    const markdown = "# Research review package\n\n## A. Review instructions\n\nDo not assume the opportunity is valid.";
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/integrations/next") return json(makeIntegration());
      if (path === "/api/projects") return json([makeProject()]);
      if (path === "/api/integrations/next/resources") return json([record]);
      if (path === `/api/integrations/next/resources/${record.id}`) return json(record);
      if (path === `/api/research/opportunities/${record.id}/export` && method === "GET")
        return json({
          schema: "mc.research-export.v1",
          fingerprint: "fingerprint-1",
          markdown,
          context: {},
        });
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    Object.defineProperty(window.navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    renderRoute(<IntegrationWorkspacePage appId="next" />, "/next");

    await user.click(await screen.findByRole("tab", { name: "Candidates" }));
    await user.click(await screen.findByRole("button", { name: /Fixture Next recommendation/i }));
    await user.click(await screen.findByRole("button", { name: /Copy for ChatGPT/i }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(markdown));
    expect(await screen.findByText("Research review package copied")).toBeInTheDocument();
    expect(calls.some((call) => call.path.includes("/messages"))).toBe(false);
    expect(calls.some((call) => call.path.endsWith("/sessions"))).toBe(false);
    expect(calls.some((call) => call.method === "POST" && call.path.includes("/research/"))).toBe(
      false,
    );
  });

  it("opens a contextual chat, sends, and preserves model attribution", async () => {
    const record = makeIntegrationRecord();
    const firstAnswer =
      "The combination is a proposal, not a demonstrated improvement. Compare both components independently.";
    const secondAnswer =
      "A controlled comparison with a held-out task would falsify the claimed gain.";
    const calls = mockFetch(({ path, method, body }) => {
      if (path === "/api/integrations/next") return json(makeIntegration());
      if (path === "/api/projects") return json([makeProject()]);
      if (path === "/api/integrations/next/resources") return json([record]);
      if (path === `/api/integrations/next/resources/${record.id}`) return json(record);
      if (path === "/api/research/models" && method === "GET")
        return json({
          provider: "openai-compatible",
          route: "configured-local-openai",
          configured: true,
          local: true,
          available: true,
          endpoint: "127.0.0.1",
          selected: "qwen2.5:latest",
          models: [
            {
              id: "qwen2.5:latest",
              label: "qwen2.5:latest",
              local: true,
              configured: true,
              available: true,
            },
          ],
          detail: "Configured local model is available.",
          error: null,
        });
      if (path === `/api/research/opportunities/${record.id}/sessions` && method === "GET")
        return json([]);
      if (path === `/api/research/opportunities/${record.id}/sessions` && method === "POST")
        return json(researchSession());
      if (path === "/api/research/sessions/rcs-1/messages" && method === "POST") {
        const content = String((body as { content?: string }).content || "");
        if (content.includes("falsify")) {
          return json(
            researchSession({
              message_count: 4,
              messages: [
                chatMessage("m1", 1, "user", "What is genuinely new here?"),
                chatMessage("m2", 2, "assistant", firstAnswer),
                chatMessage("m3", 3, "user", content),
                chatMessage("m4", 4, "assistant", secondAnswer),
              ],
            }),
          );
        }
        return json(
          researchSession({
            message_count: 2,
            messages: [
              chatMessage("m1", 1, "user", content),
              chatMessage("m2", 2, "assistant", firstAnswer),
            ],
          }),
        );
      }
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<IntegrationWorkspacePage appId="next" />, "/next");

    await user.click(await screen.findByRole("tab", { name: "Candidates" }));
    await user.click(await screen.findByRole("button", { name: /Fixture Next recommendation/i }));
    await user.click(await screen.findByRole("button", { name: /Discuss with AI/i }));

    expect(
      await screen.findByRole("dialog", { name: "Research conversation" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Local inference")).toBeInTheDocument();
    expect(screen.getByText(/Nothing is sent to a model until you submit/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Explain the core research mechanism." }));
    const send = screen.getByRole("button", { name: /^Send$/i });
    await waitFor(() => expect(send).not.toBeDisabled());
    await user.click(send);

    expect(await screen.findByText(firstAnswer)).toBeInTheDocument();
    expect(screen.getByText("qwen2.5:latest")).toBeInTheDocument();
    expect(screen.getByText("local route")).toBeInTheDocument();
    const postSession = calls.find(
      (call) => call.path.endsWith("/sessions") && call.method === "POST",
    );
    expect(postSession?.body).toEqual({
      model_id: "qwen2.5:latest",
      model_route: "configured-local-openai",
    });
    const firstMessage = calls.find((call) => call.path.endsWith("/messages"));
    expect(firstMessage?.body).toMatchObject({ content: "Explain the core research mechanism." });

    await user.type(
      screen.getByLabelText("Message the research model"),
      "What would falsify it?",
    );
    await user.click(screen.getByRole("button", { name: /^Send$/i }));
    expect(await screen.findByText(secondAnswer)).toBeInTheDocument();
    expect(screen.getByText("What is genuinely new here?")).toBeInTheDocument();
  });
});
