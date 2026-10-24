import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette } from "../components/CommandPalette";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeIntegration, makeSearchResult } from "./fixtures";

describe("CommandPalette", () => {
  it("searches integrated sources and keeps the source visible", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/integrations") return json([]);
      if (path === "/api/search")
        return json([
          makeSearchResult(),
          makeSearchResult({
            id: "res-work-1",
            source: "Work",
            source_id: "work-fixture-1",
            title: "Fixture qualified opportunity",
            subtitle: "Ireland · DIRECT_CONTRACT",
            target_path: "/work?record=res-work-1",
          }),
        ]);
      return apiError(404, `Unhandled ${path}`);
    });
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderRoute(<CommandPalette open onClose={onClose} />);

    expect(screen.getByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
    expect(screen.getByText("Unified inbox")).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: /Search or run a command/i }), "fixture");

    expect(await screen.findByText("Fixture Next recommendation")).toBeInTheDocument();
    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.getByText(/Next · A grounded research candidate/i)).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("runs a registered refresh command rather than a browser-supplied shell command", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/integrations") return json([makeIntegration({ name: "Work", application_id: "work", adapter: "work" })]);
      if (path === "/api/integrations/work/refresh" && method === "POST")
        return json({ available: true });
      return apiError(404, `Unhandled ${path}`);
    });
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderRoute(<CommandPalette open onClose={onClose} />);

    await user.type(screen.getByRole("textbox", { name: /Search or run a command/i }), "refresh work");
    await user.click(await screen.findByRole("button", { name: /Refresh Work opportunities/i }));

    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/integrations/work/refresh")).toBe(true);
    });
    expect(onClose).toHaveBeenCalled();
  });
});
