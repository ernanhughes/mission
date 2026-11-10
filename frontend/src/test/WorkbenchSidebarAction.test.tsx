import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkbenchSidebarAction } from "../features/applications/WorkbenchSidebarAction";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeApplication } from "./fixtures";

const BROWSER_URL = "http://127.0.0.1:7420/";

function makeWorkbench(state = "stopped") {
  return makeApplication({
    id: "workbench",
    name: "Workbench",
    launch_definitions: [
      {
        ...makeApplication().launch_definitions[0],
        id: "workbench-server",
        application_id: "workbench",
        name: "Workbench server",
        launch_type: "server",
        browser_url: BROWSER_URL,
        health_type: "http",
        health_url: BROWSER_URL,
        expected_port: 7420,
      },
    ],
    status: {
      ...makeApplication().status,
      state,
      label: state === "running" ? "Running" : "Stopped",
      detail: state === "running" ? "PID 42 is owned by Mission Control." : "Stopped.",
      ownership: state === "running" ? "managed" : "none",
      process_id: state === "running" ? "proc-1" : null,
    },
    actions: {
      ...makeApplication().actions,
      open_url: { enabled: true, reason: null },
    },
  });
}

function handler(appState = "stopped", ensureImpl?: () => Response) {
  return ({ path, method }: { path: string; method: string }) => {
    if (path === "/api/applications/workbench" && method === "GET") {
      return json(makeWorkbench(appState));
    }
    if (path === "/api/applications/workbench/ensure-open" && method === "POST") {
      if (ensureImpl) return ensureImpl();
      return json({
        url: BROWSER_URL,
        application_id: "workbench",
        state: "started",
        ownership: "managed",
        process_id: "proc-9",
        detail: "ready",
      });
    }
    return apiError(404, `Unhandled ${method} ${path}`);
  };
}

describe("WorkbenchSidebarAction", () => {
  it("renders a prominent Open Workbench action with a stopped status", async () => {
    mockFetch(handler());
    renderRoute(<WorkbenchSidebarAction />, "/");

    const button = await screen.findByRole("button", { name: /Open Workbench \(Stopped\)/ });
    expect(button).toBeInTheDocument();
    expect(screen.getByText("Start if needed · Open browser")).toBeInTheDocument();
  });

  it("opens the existing service without a second launch when running", async () => {
    const calls = mockFetch(handler("running"));
    const popup = { location: { replace: vi.fn() }, close: vi.fn(), opener: null };
    vi.spyOn(window, "open").mockReturnValue(popup as unknown as Window);
    const user = userEvent.setup();
    renderRoute(<WorkbenchSidebarAction />, "/");

    await screen.findByRole("button", { name: /Open Workbench \(Running\)/ });
    await user.click(screen.getByRole("button", { name: /Open Workbench/ }));

    await waitFor(() => {
      expect(
        calls.some(
          (call) => call.method === "POST" && call.path === "/api/applications/workbench/ensure-open",
        ),
      ).toBe(true);
    });
    expect(popup.location.replace).toHaveBeenCalledWith(BROWSER_URL);
    expect(await screen.findByText("Workbench ready")).toBeInTheDocument();
  });

  it("starts a stopped Workbench, shows Starting, then opens it", async () => {
    const delayed = ({ path, method }: { path: string; method: string }) => {
      if (path === "/api/applications/workbench" && method === "GET") {
        return json(makeWorkbench("stopped"));
      }
      if (path === "/api/applications/workbench/ensure-open" && method === "POST") {
        return new Promise<Response>((resolve) => {
          window.setTimeout(
            () =>
              resolve(
                json({
                  url: BROWSER_URL,
                  application_id: "workbench",
                  state: "started",
                  ownership: "managed",
                  process_id: "proc-9",
                  detail: "ready",
                }),
              ),
            50,
          );
        });
      }
      return apiError(404, `Unhandled ${method} ${path}`);
    };
    mockFetch(delayed);
    const popup = { location: { replace: vi.fn() }, close: vi.fn(), opener: null };
    vi.spyOn(window, "open").mockReturnValue(popup as unknown as Window);
    const user = userEvent.setup();
    renderRoute(<WorkbenchSidebarAction />, "/");

    await screen.findByRole("button", { name: /Open Workbench \(Stopped\)/ });
    await user.click(screen.getByRole("button", { name: /Open Workbench/ }));

    expect(await screen.findByRole("button", { name: /Open Workbench \(Starting\)/ })).toBeDisabled();
    await waitFor(() => {
      expect(popup.location.replace).toHaveBeenCalledWith(BROWSER_URL);
    });
  });

  it("shows an actionable failure with a logs link when startup fails", async () => {
    mockFetch(
      handler("stopped", () =>
        apiError(422, "Executable not found: C:\\missing\\python.exe", "launch_failed"),
      ),
    );
    vi.spyOn(window, "open").mockReturnValue({
      location: { replace: vi.fn() },
      close: vi.fn(),
    } as unknown as Window);
    const user = userEvent.setup();
    renderRoute(<WorkbenchSidebarAction />, "/");

    await screen.findByRole("button", { name: /Open Workbench \(Stopped\)/ });
    await user.click(screen.getByRole("button", { name: /Open Workbench/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Workbench could not start/);
    expect(alert).toHaveTextContent(/Executable not found/);
    expect(screen.getByRole("link", { name: "View logs" })).toHaveAttribute("href", "/applications");
    expect(await screen.findByText("Workbench could not start")).toBeInTheDocument();
  });

  it("falls back to the current tab when the popup is blocked", async () => {
    mockFetch(handler("running"));
    vi.spyOn(window, "open").mockReturnValue(null);
    const assign = vi.fn();
    Object.defineProperty(window, "location", {
      value: { assign },
      writable: true,
      configurable: true,
    });
    const user = userEvent.setup();
    renderRoute(<WorkbenchSidebarAction />, "/");

    await screen.findByRole("button", { name: /Open Workbench \(Running\)/ });
    await user.click(screen.getByRole("button", { name: /Open Workbench/ }));

    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith(BROWSER_URL);
    });
  });
});
