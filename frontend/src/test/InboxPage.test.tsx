import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InboxPage } from "../pages/InboxPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeInboxItem } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("InboxPage", () => {
  it("unifies Next and Work items without losing source identity", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/inbox")
        return json([
          makeInboxItem(),
          makeInboxItem({
            id: "inbox-res-work-1",
            source_application: "work",
            source_name: "Work",
            item_type: "work_opportunity",
            title: "Fixture qualified opportunity",
            summary: "Review the fixture opportunity.",
            priority: 95,
            actions: ["shortlist", "defer", "reject"],
            target_path: "/work?record=res-work-1",
            resource_id: "res-work-1",
          }),
        ]);
      return apiError(404, `Unhandled ${path}`);
    });

    renderRoute(<InboxPage />, "/inbox");

    expect(await screen.findByRole("heading", { name: "Awaiting your attention" })).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Fixture Next recommendation")).toBeInTheDocument();
    expect(screen.getByText("Fixture qualified opportunity")).toBeInTheDocument();
    expect(screen.getAllByText("Next").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Work").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Decision pending")).toHaveLength(2);
    expect(screen.getByText(/local_only/)).toBeInTheDocument();
  });

  it("records a decision locally through the source-scoped endpoint", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("Worth a bounded review.");
    let decided = false;
    const calls = mockFetch(({ path, method, body }) => {
      if (path === "/api/inbox")
        return json(decided ? [] : [makeInboxItem()]);
      if (path === "/api/integrations/next/resources/res-next-1/decision" && method === "POST") {
        decided = true;
        return json({
          id: "idec-1",
          application_id: "next",
          resource_type: "next_opportunity",
          external_id: "next-fixture-1",
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
    renderRoute(<InboxPage />, "/inbox");

    expect(await screen.findByText(/do not modify Next, Work, CoCoder/i)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Shortlist" }));
    await waitFor(() => {
      const decision = calls.find((call) => call.path.endsWith("/decision"));
      expect(decision?.body).toEqual({
        decision: "shortlist",
        reason: "Worth a bounded review.",
      });
    });
    expect(await screen.findByText("Nothing awaiting attention")).toBeInTheDocument();
  });

  it("shows an explicit empty state when no source has pending work", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/inbox") return json([]);
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<InboxPage />, "/inbox");
    expect(await screen.findByText("Nothing awaiting attention")).toBeInTheDocument();
    expect(
      screen.getByText(/Unresolved Next candidates, qualified Work opportunities/i),
    ).toBeInTheDocument();
  });
});
