import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ActivityPage } from "../pages/ActivityPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";

function baseMocks(daily: unknown) {
  return mockFetch(({ path }) => {
    if (path === "/api/git-activity/timeline")
      return json({ items: [], total: 0, partial: false, limit: 100, offset: 0 });
    if (path === "/api/git-activity/summary")
      return json({
        commits_today: 6,
        projects_today: 2,
        commits_week: 6,
        commits_reviewed: 0,
        commits_indexed: 6,
        repos_indexed: 2,
        backfill_pending: 0,
        complete: true,
        generated_at: new Date().toISOString(),
      });
    if (path === "/api/git-activity/repos") return json([]);
    if (path === "/api/git-activity/roots") return json([]);
    if (path === "/api/git-activity/scan")
      return json({ running: false, status: "complete" });
    if (path === "/api/git-activity/daily/projects") return json(daily);
    return apiError(404, `Unhandled ${path}`);
  });
}

const dailyPayload = {
  date: "2026-11-10",
  timezone: "Europe/Dublin",
  start_ts: 1,
  end_ts: 2,
  total_commits: 30,
  total_repos: 2,
  partial: false,
  backfill_pending: 0,
  projects: [
    {
      repo_id: "gitrepo-writer",
      repo_name: "Writer",
      date: "2026-11-10",
      timezone: "Europe/Dublin",
      start_ts: 1,
      end_ts: 2,
      commit_count: 18,
      insertions: 100,
      deletions: 20,
      files_changed: 43,
      files_changed_distinct: null,
      files_changed_estimated: true,
      first_ts: 1,
      last_ts: 2,
      backfill_complete: true,
      index_complete: true,
      coverage_warning: null,
      snapshot_fingerprint: "snapwriter",
      commit_shas: ["a", "b"],
      review_status: "not_reviewed",
      review_id: null,
      review_mode: null,
      review_verdict: null,
      review_completed_at: null,
      review_stale: false,
      review_count: 0,
    },
    {
      repo_id: "gitrepo-workbench",
      repo_name: "Workbench",
      date: "2026-11-10",
      timezone: "Europe/Dublin",
      start_ts: 1,
      end_ts: 2,
      commit_count: 12,
      insertions: 50,
      deletions: 5,
      files_changed: 20,
      files_changed_distinct: null,
      files_changed_estimated: true,
      first_ts: 1,
      last_ts: 2,
      backfill_complete: true,
      index_complete: true,
      coverage_warning: null,
      snapshot_fingerprint: "snapwork",
      commit_shas: ["c"],
      review_status: "not_reviewed",
      review_id: null,
      review_mode: null,
      review_verdict: null,
      review_completed_at: null,
      review_stale: false,
      review_count: 0,
    },
  ],
};

describe("Daily Project Review", () => {
  it("shows project tabs with counts and requires a project selection", async () => {
    baseMocks(dailyPayload);
    const user = userEvent.setup();
    renderRoute(<ActivityPage />, "/activity");

    expect(await screen.findByText(/Daily Project Review/)).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: /All active \(2\)/ })).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: /Writer \(18\)/ })).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: /Workbench \(12\)/ })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Writer \(18\)/ }));
    expect(await screen.findByText("Selected: Writer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Explain with AI/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Review with AI/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Create prompt/ })).toBeEnabled();
  });

  it("shows an empty state when nothing was indexed that day", async () => {
    baseMocks({
      date: "2026-11-10",
      timezone: "Europe/Dublin",
      start_ts: 1,
      end_ts: 2,
      total_commits: 0,
      total_repos: 0,
      partial: false,
      backfill_pending: 0,
      projects: [],
    });
    renderRoute(<ActivityPage />, "/activity");
    expect(await screen.findByText(/Daily Project Review/)).toBeInTheDocument();
    expect(await screen.findByText(/No indexed commits on this day/)).toBeInTheDocument();
  });
});
