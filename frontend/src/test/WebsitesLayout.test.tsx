import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Layout } from "../components/Layout";
import { ThemeProvider } from "../components/Theme";
import { ToastProvider } from "../components/Toast";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { WebsitesPage } from "../pages/WebsitesPage";

function makeSite(overrides = {}) {
  return {
    id: "website-programmer-ie",
    name: "Programmer Ie",
    path: "C:\\websites\\programmer.ie",
    is_hugo: true,
    site_type: "hugo",
    evidence: ["Hugo configuration observed: hugo.toml"],
    hugo_config: "hugo.toml",
    content_section: "post",
    title: "Programmer.ie",
    available: true,
    launch_supported: true,
    hugo_available: true,
    running: false,
    preview_url: null,
    port: null,
    process_id: null,
    ...overrides,
  };
}

function mockWebsites(extra?: (call: { path: string; method: string; body: unknown }) => Response | undefined) {
  return mockFetch((call) => {
    if (extra) {
      const response = extra(call);
      if (response) return response;
    }
    if (call.path === "/api/health")
      return json({ status: "ok", version: "0.1.0", database: "sqlite", schema_version: 1, ai_enabled: false, monitor_enabled: true });
    if (call.path === "/api/websites")
      return json([
        makeSite(),
        makeSite({ id: "website-notebooks", name: "Notebooks", path: "C:\\websites\\notebooks", is_hugo: false, site_type: "static", launch_supported: false, hugo_config: null, content_section: null }),
      ]);
    if (call.path === "/api/websites/diagnostics") return json({ root: "C:\\websites", diagnostics: [] });
    return apiError(404, `Unhandled ${call.path}`);
  });
}

function renderLayout(route = "/websites") {
  return render(
    <ThemeProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="websites" element={<WebsitesPage />} />
              <Route path="cultivation" element={<div>Cultivation page</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </ThemeProvider>,
  );
}

describe("Layout HUD + navigation (MC-WEBSITES-CULTIVATION-01)", () => {
  it("renders no floating Cultivation widget but keeps sidebar navigation", async () => {
    mockWebsites();
    renderLayout("/websites");
    await screen.findByRole("heading", { name: "Websites" });
    // The floating HUD root carries an explicit aria label; it must be gone.
    expect(screen.queryByLabelText("Cultivation progress")).not.toBeInTheDocument();
    // Sidebar navigation is retained.
    expect(screen.getByRole("link", { name: "Websites" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cultivation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Books" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fiction Books" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toBeInTheDocument();
  });
});

describe("WebsitesPage", () => {
  it("lists discovered websites with type, path and launch availability", async () => {
    mockWebsites();
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    expect(await screen.findByRole("heading", { name: "Websites" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Programmer Ie — Hugo/ })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Notebooks — Non-Hugo/ })).toBeInTheDocument();
    expect(await screen.findByText("C:\\websites\\programmer.ie")).toBeInTheDocument();
    expect(await screen.findByText(/Hugo configuration observed/)).toBeInTheDocument();
  });

  it("shows an empty state when no websites are discovered", async () => {
    mockWebsites((call) => {
      if (call.path === "/api/websites") return json([]);
      return undefined;
    });
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    expect(await screen.findByText("No website workspaces")).toBeInTheDocument();
  });

  it("launches Hugo, reuses the preview and stops it", async () => {
    const calls = mockWebsites((call) => {
      if (call.path === "/api/websites/website-programmer-ie/launch" && call.method === "POST")
        return json({ id: "website-programmer-ie", url: "http://127.0.0.1:1313/", port: 1313, reused: true, detail: "Reused" });
      if (call.path === "/api/websites/website-programmer-ie/stop" && call.method === "POST") return json({ ok: true });
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    await user.click(await screen.findByRole("tab", { name: "Preview" }));
    await user.click(await screen.findByRole("button", { name: "Launch Hugo" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.path.endsWith("/launch"))).toBe(true);
    });
    await user.click(await screen.findByRole("button", { name: "Open folder" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.path.endsWith("/open-path"))).toBe(true);
    });
  });
});
