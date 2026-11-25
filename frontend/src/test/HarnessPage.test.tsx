import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import { HarnessPage } from "../features/harness/HarnessPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";

const strategyRows = ["direct.v1", "structured.v1", "corrective.v1", "adaptive.v1"].map((key) => ({
  key, id: key.split(".")[0], version: "1", digest: `digest-${key}`, maximum_model_invocations: key.includes("corrective") || key.includes("adaptive") ? 2 : 1,
  internal_validation: key === "direct.v1" ? "none" : "json_schema", correction: key.includes("adaptive") || key.includes("corrective") ? "on_structural_failure_once" : "never",
  availability: "available", qualification: "not_asserted_by_catalogue",
  supported_backends: ["model"], behavior: `Worker behavior for ${key}`, known_limitations: ["Semantic truth is not established."],
}));
const episodes = [{ id: "ep:synthetic:1", title: "Synthetic bounded task", project_key: "synthetic", status: "established" }];
const catalogue = { schema_version: "mission.harness-catalogue.v1", worker: { reachable: true, status: "ok", version: "test", base_url: "http://127.0.0.1:7317" }, strategies: strategyRows, models: [{ id: "local-free", model: "local-model", economic_tier: "free", data_policy: "local_only", health: "unknown" }], policies: { local: { routes: ["local-free"], required_data_policy: "local_only", attempts_per_route: 1 } }, limits: {}, qualification_note: "Catalogue listing is not qualification." };

function mocks({ submit = true, disconnected = false, executionRows = [] }: { submit?: boolean; disconnected?: boolean; executionRows?: Array<Record<string, any>> } = {}) {
  return mockFetch(({ path, method, body }) => {
    if (path === "/api/harness/catalogue") return disconnected ? apiError(503, "Worker unavailable") : json(catalogue);
    if (path === "/api/harness/executions" && method === "GET") return json({ executions: executionRows, coverage: { source: "worker_h3_execution_ledger", read_window: executionRows.length, truncated: false } });
    if (path === "/api/harness/jobs") return json({ jobs: [], cancellation: "unsupported" });
    if (path === "/api/work-episodes") return json({ episodes });
    if (path === "/api/work-intent/objectives") return json({ objectives: [{ id: "obj:synthetic:1", episode_id: episodes[0].id, text: "Return a JSON object with the answer to 19 + 23.", status: "confirmed", version: 1 }] });
    if (path === "/api/harness/executions" && method === "POST") return submit ? json({ worker_result: { request_id: "wrq_abcdef123456", status: "AWAITING_ACCEPTANCE", output: "{\"answer\":42}" } }) : apiError(503, "Worker unavailable");
    return apiError(404, `Unhandled ${method} ${path}`);
  });
}

describe("Mission Harness", () => {
  it("loads the Worker strategy catalogue and shows qualification as unasserted", async () => {
    mocks();
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage />} /></Routes>, "/harness?tab=strategies");
    expect(await screen.findByText("Worker behavior for adaptive.v1")).toBeInTheDocument();
    expect(screen.getAllByText("not_asserted_by_catalogue").length).toBeGreaterThan(0);
  });

  it("previews and submits an explicitly confirmed bounded Work Outcome request", async () => {
    const user = userEvent.setup();
    const calls = mocks();
    vi.stubGlobal("confirm", vi.fn(() => true));
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage />} /></Routes>, "/harness?tab=execute");
    expect(await screen.findByText(/Return a JSON object with the answer/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Human actor"), "Owner");
    await user.type(screen.getByLabelText("Authorization note"), "Authorized synthetic task");
    await user.click(screen.getByRole("button", { name: "Review and authorize execution" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/api/harness/executions" && call.method === "POST")).toBe(true));
    const request = calls.find((call) => call.path === "/api/harness/executions" && call.method === "POST")?.body as Record<string, unknown>;
    expect(request.strategy_id).toBe("adaptive.v1");
    expect(request.normalization_policy).toBe("json-fence.v1");
    expect(request.episode_id).toBe(episodes[0].id);
    expect(request.objective_id).toBe("obj:synthetic:1");
    expect(await screen.findByText("AWAITING_ACCEPTANCE")).toBeInTheDocument();
  });

  it("carries exact project scope from the project Harness into the launch request", async () => {
    const user = userEvent.setup();
    const calls = mocks();
    vi.stubGlobal("confirm", vi.fn(() => true));
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage projectKey="synthetic" />} /></Routes>, "/harness?tab=execute");
    expect(await screen.findByText(/Return a JSON object with the answer/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Human actor"), "Owner");
    await user.type(screen.getByLabelText("Authorization note"), "Authorized project task");
    await user.click(screen.getByRole("button", { name: "Review and authorize execution" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/api/harness/executions" && call.method === "POST")).toBe(true));
    const request = calls.find((call) => call.path === "/api/harness/executions" && call.method === "POST")?.body as Record<string, unknown>;
    expect(request.project_key).toBe("synthetic");
  });

  it("does not label executions comparable when temperature and reasoning conditions are unknown", async () => {
    const executionRows = ["direct.v1", "adaptive.v1"].map((strategy, index) => ({
      request_id: `wrq_compare_${index}`, task_id: "obj:synthetic:1", episode_id: "ep:synthetic:1",
      mission_correlation: { status: "verified", episode_id: "ep:synthetic:1", objective_id: "obj:synthetic:1" },
      strategy_execution: { strategy: { key: strategy } },
      requested: { engine: "model", policy: "local", timeout_ms: 30000, max_output_tokens: 256, data_policy: "local_only", temperature: null, reasoning_effort: null },
      resolved: { selected_executor: "model", resolved_model_route: "local-free" },
    }));
    mocks({ executionRows });
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage />} /></Routes>, "/harness?tab=experiments");
    expect(await screen.findByText("Repeated or unmatched execution; comparison not established")).toBeInTheDocument();
  });

  it("labels Worker episode identity as unverified in the Decisions view", async () => {
    const executionRows = [{ request_id: "wrq_unlinked", task_id: "obj:foreign", episode_id: "ep:foreign",
      episode_link: "caller_supplied_unverified", mission_correlation: { status: "unmatched" },
      strategy_execution: { strategy: { key: "adaptive.v1" }, validation: { decisions: [{ selected_action: "ABSTAIN", outcome: "applied" }] } } }];
    mocks({ executionRows });
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage />} /></Routes>, "/harness?tab=decisions");
    expect(await screen.findByText(/Worker episode unverified/)).toBeInTheDocument();
  });

  it("keeps Worker disconnection visible while leaving navigation usable", async () => {
    mocks({ disconnected: true });
    renderRoute(<Routes><Route path="/harness" element={<HarnessPage />} /></Routes>, "/harness");
    expect(await screen.findByText(/Worker unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Strategies" })).toBeEnabled();
    expect(screen.getByRole("tab", { name: "Execute" })).toBeEnabled();
  });
});
