import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationsPage } from "../pages/ApplicationsPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeApplication, makeProcess } from "./fixtures";

function baseHandler(overrides: Record<string, Response> = {}) {
  return ({ path, method }: { path: string; method: string }) => {
    const key = `${method} ${path}`;
    if (overrides[key]) return overrides[key];
    if (path === "/api/applications" && method === "GET") return json([makeApplication()]);
    if (path === "/api/processes" && method === "GET") return json([]);
    if (path === "/api/projects") return json([]);
    if (path === "/api/outcomes") return json([]);
    return apiError(404, `Unhandled ${method} ${path}`);
  };
}

describe("ApplicationsPage", () => {
  it("reports a failed launch without breaking the page", async () => {
    mockFetch(
      baseHandler({
        "POST /api/applications/next/launch": apiError(
          422,
          "Executable not found: missing.exe",
          "launch_failed",
          "Check the executable name.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderRoute(<ApplicationsPage />, "/applications");

    await screen.findByRole("heading", { name: "Next" });
    await user.click(screen.getByRole("button", { name: "Launch" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Executable not found: missing.exe/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Next" })).toBeInTheDocument();
  });

  it("shows reasons for disabled actions rather than silent disabled buttons", async () => {
    mockFetch(baseHandler());
    renderRoute(<ApplicationsPage />, "/applications");
    await screen.findByRole("heading", { name: "Next" });
    expect(screen.getByText("Why some actions are unavailable")).toBeInTheDocument();
    expect(screen.getByText(/No Mission Control-owned process is running/)).toBeInTheDocument();
  });

  it("offers Open for a running application in the card and the process list", async () => {
    const running = makeApplication({
      launch_definitions: [
        {
          ...makeApplication().launch_definitions[0],
          browser_url: "http://127.0.0.1:8000/",
        },
      ],
      status: {
        ...makeApplication().status,
        state: "running",
        label: "Running",
        detail: "PID 1234 is owned by Mission Control.",
        ownership: "managed",
        process_id: "proc-1",
      },
      actions: {
        ...makeApplication().actions,
        launch: { enabled: false, reason: "A managed process is already running." },
        stop: { enabled: true, reason: null },
        open_url: { enabled: true, reason: null },
      },
    });
    const calls = mockFetch(
      baseHandler({
        "GET /api/applications": json([running]),
        "GET /api/processes": json([makeProcess()]),
        "POST /api/applications/next/open-url": json({
          url: "http://127.0.0.1:8000/",
          application_id: "next",
          opened_externally: false,
        }),
      }),
    );
    const popup = {
      location: { replace: vi.fn() },
      close: vi.fn(),
    };
    vi.spyOn(window, "open").mockReturnValue(popup as unknown as Window);
    const user = userEvent.setup();
    renderRoute(<ApplicationsPage />, "/applications");

    await screen.findByRole("heading", { name: "Next" });
    expect(screen.getByRole("link", { name: "http://127.0.0.1:8000/" })).toBeInTheDocument();
    const table = screen.getByRole("table");
    await user.click(within(table).getByRole("button", { name: /Open/ }));

    await waitFor(() => {
      expect(
        calls.some(
          (call) => call.method === "POST" && call.path === "/api/applications/next/open-url",
        ),
      ).toBe(true);
    });
    expect(popup.location.replace).toHaveBeenCalledWith("http://127.0.0.1:8000/");
  });

  it("edits an application's registry configuration", async () => {
    const calls = mockFetch(
      baseHandler({
        "PATCH /api/applications/next": json(makeApplication({ name: "Next Updated" })),
      }),
    );
    const user = userEvent.setup();
    renderRoute(<ApplicationsPage />, "/applications");

    await screen.findByRole("heading", { name: "Next" });
    await user.click(screen.getByRole("button", { name: /Configure/ }));
    const dialog = await screen.findByRole("dialog", { name: /Configure Next/ });
    const nameInputs = within(dialog).getAllByLabelText("Name");
    await user.clear(nameInputs[0]);
    await user.type(nameInputs[0], "Next Updated");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      const patch = calls.find(
        (call) => call.method === "PATCH" && call.path === "/api/applications/next",
      );
      expect(patch).toBeTruthy();
      expect((patch?.body as { name?: string }).name).toBe("Next Updated");
    });
  });
});
