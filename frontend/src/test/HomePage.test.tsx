import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { HomePage } from "../pages/HomePage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeDashboard, makeSettings } from "./fixtures";

describe("HomePage", () => {
  it("renders the three priority books, resume checkpoint and outcomes from the API", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/dashboard") return json(makeDashboard());
      if (path === "/api/settings") return json(makeSettings());
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<HomePage />);

    expect(await screen.findByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Language: When Intelligence Enters the Channel" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inference From First Principles" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Adversarial Mathematics From First Principles" })).toBeInTheDocument();
    expect(screen.getByText("Lorentz proof validation reviewed.")).toBeInTheDocument();
    expect(screen.getByText("Books and publishing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI-assisted/ })).not.toBeInTheDocument();
  });

  it("persists priority reordering through the books reorder endpoint", async () => {
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/dashboard") return json(makeDashboard());
      if (path === "/api/settings") return json(makeSettings());
      if (path === "/api/books/reorder" && method === "POST") return json({ ok: true });
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<HomePage />);

    await screen.findByRole("heading", { name: "Inference From First Principles" });
    await user.click(screen.getByRole("button", { name: "Move Math up" }));

    await waitFor(() => {
      const reorder = calls.find((call) => call.path === "/api/books/reorder");
      expect(reorder).toBeTruthy();
      expect(reorder?.body).toEqual({
        ids: ["book-language", "book-math", "book-inference"],
      });
    });
  });

  it("shows an empty state when no checkpoint exists", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/dashboard")
        return json(makeDashboard({ focus: null, checkpoint: null, books: [], recommendations: [] }));
      if (path === "/api/settings") return json(makeSettings());
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<HomePage />);
    expect(await screen.findByText("No current focus")).toBeInTheDocument();
    expect(screen.getByText("No checkpoint yet")).toBeInTheDocument();
  });
});
