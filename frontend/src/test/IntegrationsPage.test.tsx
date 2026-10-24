import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { IntegrationsPage } from "../pages/IntegrationsPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeIntegration } from "./fixtures";

function integrationFixtures() {
  return [
    makeIntegration(),
    makeIntegration({
      application_id: "work",
      name: "Work",
      adapter: "work",
      mode: "cli-json",
      detail: "Read 130 opportunities from Work's JSON CLI (63 qualified).",
      resource_counts: { work_opportunity: 130 },
      repository_path: "C:\\Projects\\work",
      config: { arguments: ["opportunities", "--json"], env_names: ["WORK_DATABASE_URL"] },
    }),
    makeIntegration({
      application_id: "cocoder",
      name: "CoCoder",
      adapter: "cocoder",
      mode: "cli-artifact",
      detail: "Read 2 review artifacts and 478 finding records.",
      capabilities: ["health", "list_resources", "execute_action"],
      resource_counts: { cocoder_review: 1, cocoder_finding: 400 },
      repository_path: "C:\\Projects\\cocoder",
      config: { artifact_dir: "integrations/cocoder", timeout_seconds: 180 },
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
  ];
}

describe("IntegrationsPage", () => {
  it("shows real diagnostics, modes and registered actions", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/integrations") return json(integrationFixtures());
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<IntegrationsPage />, "/integrations");

    expect(await screen.findByRole("heading", { name: "Integrations" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Next" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Work" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "CoCoder" })).toBeInTheDocument();
    expect(screen.getByText("postgres-readonly")).toBeInTheDocument();
    expect(screen.getByText("cli-json")).toBeInTheDocument();
    expect(screen.getByText("cli-artifact")).toBeInTheDocument();
    expect(screen.getAllByText("mc09.1")).toHaveLength(3);
    expect(screen.getAllByText(/No reviewed Next operation contract/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Run a bounded CoCoder review")).toBeInTheDocument();
    expect(screen.getByText(/does not write source databases/i)).toBeInTheDocument();

    const cocoderCard = screen.getByRole("heading", { name: "CoCoder" }).closest("article");
    expect(cocoderCard).not.toBeNull();
    expect(within(cocoderCard as HTMLElement).getByRole("link", { name: "Open workspace" })).toHaveAttribute(
      "href",
      "/cocoder",
    );
  });

  it("tests a connection and refreshes the read model through the API", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/integrations" && method === "GET") return json(integrationFixtures());
      if (path === "/api/integrations/next/refresh" && method === "POST")
        return json(makeIntegration({ detail: "Refreshed 130 live Next opportunities." }));
      if (path === "/api/integrations/next/test" && method === "POST")
        return json(makeIntegration());
      return apiError(404, `Unhandled ${method} ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<IntegrationsPage />, "/integrations");

    const nextCard = (await screen.findByRole("heading", { name: "Next" })).closest("article");
    expect(nextCard).not.toBeNull();
    await user.click(within(nextCard as HTMLElement).getByRole("button", { name: /Refresh read model/i }));

    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/integrations/next/refresh")).toBe(true);
    });
    await waitFor(() => {
      expect(
        calls.filter((call) => call.path === "/api/integrations" && call.method === "GET").length,
      ).toBeGreaterThan(1);
    });

    await user.click(within(nextCard as HTMLElement).getByRole("button", { name: /Test connection/i }));
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/integrations/next/test")).toBe(true);
    });
  });

  it("does not expose secret-like configuration fields", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/integrations")
        return json([
          makeIntegration({
            config: { dsn_env: "NEXT_DSN", api_key_env: "NEXT_TOKEN", limit: 200 },
          }),
        ]);
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<IntegrationsPage />, "/integrations");
    await screen.findByRole("heading", { name: "Next" });
    expect(screen.queryByText(/api_key_env/)).not.toBeInTheDocument();
    expect(screen.queryByText("NEXT_TOKEN")).not.toBeInTheDocument();
    expect(screen.getByText("NEXT_DSN")).toBeInTheDocument();
  });
});
