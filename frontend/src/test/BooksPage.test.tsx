import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BooksPage } from "../pages/BooksPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeBook } from "./fixtures";

describe("BooksPage", () => {
  it("selects a book and shows its persisted workspace", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/books")
        return json([
          makeBook(),
          makeBook({
            id: "book-inference",
            project_id: "inference",
            project_name: "Inference",
            title: "Inference From First Principles",
            status: "drafting",
            current_milestone: "Chapters 01-28 have starter manuscripts.",
            next_action: "Choose the next chapter to draft.",
            priority: 2,
          }),
        ]);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<BooksPage />, "/books");

    await screen.findByRole("heading", { name: "Language: When Intelligence Enters the Channel" });
    await user.click(screen.getByRole("button", { name: "Inference — drafting" }));

    expect(
      await screen.findByRole("heading", { name: "Inference From First Principles" }),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Chapters 01-28 have starter manuscripts.")).toBeInTheDocument();
  });

  it("shows an empty state when no book workspaces exist", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/books") return json([]);
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<BooksPage />, "/books");
    expect(await screen.findByText("No book workspaces")).toBeInTheDocument();
  });
});
