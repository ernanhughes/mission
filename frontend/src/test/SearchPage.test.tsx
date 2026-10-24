import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SearchPage } from "../pages/SearchPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeSearchResult } from "./fixtures";

describe("SearchPage", () => {
  it("searches multiple real source systems and keeps attribution", async () => {
    const calls = mockFetch(({ path }) => {
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
          makeSearchResult({
            id: "res-cocoder-1",
            source: "CoCoder",
            source_id: "review-fixture:F-1",
            title: "HIGH: Exception handling widened",
            subtitle: "backend/example.py",
            target_path: "/cocoder?record=res-cocoder-1",
          }),
        ]);
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<SearchPage />, "/search?q=fixture");

    expect(await screen.findByRole("heading", { name: "Search everything" })).toBeInTheDocument();
    expect(await screen.findByText("Fixture Next recommendation")).toBeInTheDocument();
    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.getByText("HIGH: Exception handling widened")).toBeInTheDocument();
    expect(screen.getAllByText("Next").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Work").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CoCoder").length).toBeGreaterThan(0);
    expect(calls.filter((call) => call.path === "/api/search")).toHaveLength(1);

    const nextLink = screen.getByRole("link", { name: /Fixture Next recommendation/i });
    expect(nextLink).toHaveAttribute("href", "/next?record=res-next-1");
    const workLink = screen.getByRole("link", { name: /Fixture qualified opportunity/i });
    expect(workLink).toHaveAttribute("href", "/work?record=res-work-1");
  });

  it("filters results by source without merging records", async () => {
    mockFetch(({ path }) => {
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
    const user = userEvent.setup();
    renderRoute(<SearchPage />, "/search?q=fixture");

    await screen.findByText("Fixture Next recommendation");
    await user.click(screen.getByRole("button", { name: /^Work/ }));

    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.queryByText("Fixture Next recommendation")).not.toBeInTheDocument();
  });

  it("requires at least two characters before searching", async () => {
    const calls = mockFetch(({ path }) => apiError(404, `Unhandled ${path}`));
    renderRoute(<SearchPage />, "/search");
    expect(await screen.findByText("Search the working context")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });
});
