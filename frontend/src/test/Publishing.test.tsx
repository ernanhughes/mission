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
    if (call.path === "/api/publication/publishing/chapters" && call.method === "GET")
      return json({ project_id: "math", chapters: [], count: 0, assessment: null, approvals: [], manuscript_fingerprint: null, observed_at: "" });
    if (call.path === "/api/publication/publishing/candidates" && call.method === "GET")
      return json({ project_id: "math", candidates: [], count: 0, observed_at: "" });
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
    await user.click(screen.getByRole("tab", { name: "Evidence" }));
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
    await user.click(screen.getByRole("tab", { name: "Publish" }));
    const [track] = await screen.findAllByRole("button", { name: "Track" });
    await user.click(track);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await screen.findByText("Follow-up opened");
    const posted = calls.find((call) => call.method === "POST" && call.path === "/api/publication/followups");
    expect(posted).toBeTruthy();
    expect((posted!.body as Record<string, unknown>).evidence_type).toBe("builder_artifacts");
  });

  it("organizes publishing into tabs with chapters and candidates", async () => {
    mockPublishing();
    const user = userEvent.setup();
    renderBookPage();
    for (const tab of ["Overview", "Chapters", "Evidence", "Editorial", "Candidates", "Review", "Publish"]) {
      expect(screen.getByRole("tab", { name: tab })).toBeInTheDocument();
    }
    await user.click(screen.getByRole("tab", { name: "Chapters" }));
    expect(await screen.findByText(/unassessed-or-unknown/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Candidates" }));
    expect(await screen.findByText("No retained candidates")).toBeInTheDocument();
  });

  it("requires a human reviewer before recording approval", async () => {
    mockPublishing((call) => {
      if (call.path === "/api/publication/assessments" && call.method === "GET") {
        return json([{ id: "asmt-1", assessment_status: "NOT_YET_ASSESSED", freshness: "CURRENT", manuscript_fingerprint: "a".repeat(64) }]);
      }
      return undefined;
    });
    const user = userEvent.setup();
    renderBookPage();
    await user.click(screen.getByRole("tab", { name: "Review" }));
    expect(await screen.findByText(/Approval is a mandatory gate/)).toBeInTheDocument();
    const record = screen.getByRole("button", { name: "Record approval" });
    expect(record).toBeDisabled();
    await user.type(screen.getByLabelText("Approval reviewer"), "Author");
    expect(record).toBeEnabled();
  });

  it("requests chapter improvement only after explicit human authorization", async () => {
    const calls = mockPublishing((call) => {
      if (call.path === "/api/publication/publishing/chapters" && call.method === "GET") {
        return json({ project_id: "math", chapters: [{ chapter_id: "01-chapter", title: "Chapter 1", filename: "01-chapter.md", bytes: 100, fingerprint: "a".repeat(64), state: "unassessed", issues: [], followups: [] }], count: 1, chapter_named_in_assessment: [], assessment: null, approvals: [], manuscript_fingerprint: "b".repeat(64), observed_at: "" });
      }
      if (call.path === "/api/publication/improvements" && call.method === "POST") {
        return json({ status: "prepared", packet: { chapter: { chapter_id: "01-chapter" } }, dispatched: false, note: "Prepared (no dispatch)." }, 201);
      }
      return undefined;
    });
    const user = userEvent.setup();
    renderBookPage();
    await user.click(screen.getByRole("tab", { name: "Chapters" }));
    expect(await screen.findByText(/01-chapter/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Improve chapter" }));
    expect(screen.getByLabelText("Editorial strategy")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Prepare request" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Improvement actor"), "Author");
    await user.type(screen.getByLabelText("Improvement authorization note"), "Authorized probe");
    expect(submit).toBeEnabled();
    await user.click(submit);
    await screen.findByText(/Prepared \(no dispatch\)/);
    const posted = calls.filter((call) => call.method === "POST" && call.path === "/api/publication/improvements");
    expect(posted).toHaveLength(1);
    expect((posted[0].body as Record<string, unknown>).mode).toBe("inspect");
  });
});
