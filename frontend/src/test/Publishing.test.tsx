import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BookPublishingPage } from "../pages/BookPublishingPage";
import { PublishingWorkbenchPage } from "../pages/PublishingWorkbenchPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { ToastProvider } from "../components/Toast";

const summary = {
  project_id: "math",
  project_name: "Math",
  book_id: "book-math",
  book_title: "Adversarial Mathematics",
  manuscript_root: "C:\\books\\math\\content\\books\\math",
  chapter_count: 39,
  lifecycle: "research",
  lifecycle_note: "Writer lifecycle is knowledge state, not publication approval.",
  publication_gate: "Unknown",
  policy_version: null,
  identity: { identity_state: "resolved" },
  source_fingerprint: { ok: true },
  git_revision: {},
  fingerprint_match: true,
  observed_at: "2026-11-22T00:00:00Z",
  evidence: [
    {
      book_id: "book-math",
      evidence_type: "manuscript_discovery",
      source_system: "writer",
      source_reference: "C:\\books\\math\\content\\books\\math",
      source_revision: "",
      observed_at: "2026-11-22T00:00:00Z",
      executed_at: "",
      result: "passed",
      freshness: "current",
      diagnostics: "39 chapter files.",
      available_actions: ["Refresh book"],
      detail: { chapter_count: 39 },
    },
    {
      book_id: "book-math",
      evidence_type: "builder_artifacts",
      source_system: "bookbuilder",
      source_reference: "dist",
      source_revision: "",
      observed_at: "2026-11-22T00:00:00Z",
      executed_at: "",
      result: "unknown",
      freshness: "stale",
      diagnostics: "Artifacts predate the newest chapter edit.",
      available_actions: ["Rebuild with Bookbuilder to refresh artifacts."],
      detail: {},
    },
  ],
  gates: [
    {
      gate_id: "manuscript_identity",
      label: "The release candidate binds to an exact manuscript snapshot.",
      gate_group: "identity",
      status: "passed",
      stale: false,
      evidence: [
        { evidence_type: "manuscript_discovery", result: "passed", freshness: "current", source_system: "writer", source_reference: "x" },
      ],
    },
  ],
  blockers: { failed: [], stale: ["builder_artifacts"], missing: ["proof_claims"], identity_conflicts: [] },
  refresh_note: "Refresh rereads stored evidence only.",
};

const overview = {
  books: [
    {
      project_id: "math",
      project_name: "Math",
      book_id: "book-math",
      book_title: "Adversarial Mathematics",
      lifecycle: "research",
      publication_gate: "Unknown",
      chapter_count: 39,
      fingerprint_match: true,
      identity_state: "resolved",
      failed: [],
      stale: ["builder_artifacts"],
      missing: ["proof_claims"],
      identity_conflicts: [],
      error: null,
    },
  ],
  count: 1,
  needs_attention: 1,
  observed_at: "2026-11-22T00:00:00Z",
  refresh_note: "Refresh rereads stored evidence only.",
};

function mockPublishing(extra?: (call: { path: string; method: string; body: unknown }) => Response | undefined) {
  return mockFetch((call) => {
    if (extra) {
      const response = extra(call);
      if (response) return response;
    }
    if (call.path === "/api/publication/publishing/overview") return json(overview);
    if (call.path === "/api/publication/publishing" && call.method === "GET") return json(summary);
    if (call.path === "/api/publication/publishing/refresh" && call.method === "POST") return json(summary);
    if (call.path === "/api/publication/assessments" && call.method === "GET") return json([]);
    if (call.path === "/api/publication/followups") {
      if (call.method === "GET") return json([]);
      return json(
        {
          id: "pfl-1", project_id: "math", book_id: "book-math", evidence_type: "builder_artifacts",
          source_reference: "dist", fingerprint: "abc", observed_at: "2026-11-22T00:00:00Z",
          target_type: "task", target_id: "task-1", title: "T", rationale: "R",
          status: "open", reviewer: "", created_at: "", updated_at: "",
        },
        201,
      );
    }
    if (call.path === "/api/books/identity-conflicts") return json({ candidates: [], conflicts: [], unavailable: [], unregistered_writer: [] });
    return apiError(404, `Unhandled ${call.path}`);
  });
}

describe("PublishingWorkbenchPage", () => {
  it("lists all books with gate and blocker rollups", async () => {
    mockPublishing();
    renderRoute(
      <ToastProvider>
        <PublishingWorkbenchPage />
      </ToastProvider>,
      "/publishing",
    );
    expect(await screen.findByRole("heading", { name: "Publishing workbench" })).toBeInTheDocument();
    expect(await screen.findByText("Adversarial Mathematics")).toBeInTheDocument();
    expect(
      await screen.findByText((_, element) => element?.textContent === "Needs attention · 2"),
    ).toBeInTheDocument();
  });

  it("shows the identity inbox empty state when nothing conflicts", async () => {
    mockPublishing();
    renderRoute(
      <ToastProvider>
        <PublishingWorkbenchPage />
      </ToastProvider>,
      "/publishing",
    );
    expect(await screen.findByText(/No identity conflicts/)).toBeInTheDocument();
  });
});

describe("BookPublishingPage", () => {
  function renderBookPage() {
    return render(
      <ToastProvider>
        <MemoryRouter initialEntries={["/projects/math/publishing"]}>
          <Routes>
            <Route path="/projects/:projectId/publishing" element={<BookPublishingPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>,
    );
  }
  it("renders gates joined to evidence and the refresh action", async () => {
    const calls = mockPublishing();
    const user = userEvent.setup();
    renderBookPage();
    expect(await screen.findByText("The release candidate binds to an exact manuscript snapshot.")).toBeInTheDocument();
    const gate = (await screen.findByText("manuscript_identity", { exact: false })).closest(".panel") as HTMLElement;
    expect(within(gate).getByText("passed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Refresh evidence/ }));
    await screen.findByText("Evidence re-read (no validation, build or publish ran)");
    expect(calls.some((call) => call.method === "POST" && call.path === "/api/publication/publishing/refresh")).toBe(true);
  });

  it("promotes a blocker to a follow-up without touching other books", async () => {
    const calls = mockPublishing();
    const user = userEvent.setup();
    renderBookPage();
    const [track] = await screen.findAllByRole("button", { name: "Track" });
    await user.click(track);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await screen.findByText("Follow-up opened");
    const posted = calls.find((call) => call.method === "POST" && call.path === "/api/publication/followups");
    expect(posted).toBeTruthy();
    expect((posted!.body as Record<string, unknown>).evidence_type).toBe("builder_artifacts");
  });
});
