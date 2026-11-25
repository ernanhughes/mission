import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BookTab } from "../features/project/BookTab";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeBook, makeProjectDetail } from "./fixtures";
import type {
  PipelineBookMatrix,
  PipelineStage,
  QualityCampaign,
  QualityDiscovery,
} from "../types/api";

const NOW = "2026-11-24T12:00:00+00:00";

const CHAPTER: QualityDiscovery = {
  chapter_id: "01-chapter.md",
  title: "Stop Generating",
  source_path: "C:\\books\\jev\\01-chapter.md",
  revision: "a".repeat(64),
  has_current: false,
  current_model: null,
  current_id: null,
  compatible: false,
  eligibility: "missing",
};

const CAMPAIGN: QualityCampaign = {
  id: "mqcamp:chapter",
  project_id: "math",
  book_id: "book-math",
  book_root: "C:\\books\\math",
  mode: "selected",
  chapter_selection: ["01-chapter.md"],
  fingerprints: { "01-chapter.md": CHAPTER.revision },
  rubric_id: "manuscript-prose-v1",
  rubric_version: 1,
  prompt_version: "1",
  model: "opencode-go/deepseek-v4.1-flash",
  strategy: "direct",
  assessment_type: "prose",
  status: "pending",
  total: 1,
  completed: 0,
  skipped: 0,
  failed: 0,
  remaining: 1,
  usage: {},
  costs_unknown: true,
  current_chapter: null,
  error: null,
  heartbeat_at: null,
  created_at: NOW,
  updated_at: NOW,
  completed_at: null,
};

const TECH_CAMPAIGN: QualityCampaign = {
  ...CAMPAIGN,
  id: "mqcamp:technical",
  assessment_type: "technical",
};

function stage(overrides: Partial<PipelineStage>): PipelineStage {
  return {
    stage_id: "stage",
    name: "Stage",
    description: "Stage description.",
    owner: "writer",
    scope: "chapter",
    applicability: "Every chapter.",
    freshness_method: "Digest.",
    prerequisites: "None.",
    presentation_order: 10,
    availability: "implemented",
    availability_reason: "",
    execution_class: "governed",
    execution_note: "Needs explicit authorization.",
    ui_actions: [],
    ...overrides,
  };
}

const PIPELINE: PipelineBookMatrix = {
  project_id: "math",
  known: true,
  book_title: "Math",
  registry_version: "1",
  chapter_dir: "C:\\books\\math",
  chapter_pattern: "NN-chapter.md",
  profile: "technical-nonfiction-v1",
  discovery: {},
  chapters: [{ chapter_id: "01-chapter", filename: "01-chapter.md", path: "C:\\books\\math\\01-chapter.md" }],
  stages: [
    stage({
      stage_id: "mri",
      name: "MRI",
      presentation_order: 20,
      execution_class: "automatic",
      execution_note: "Allowlisted for automatic maintenance.",
    }),
    stage({
      stage_id: "metadata",
      name: "Metadata",
      presentation_order: 10,
      execution_class: "governed",
    }),
    stage({
      stage_id: "strengthening",
      name: "Strengthening",
      presentation_order: 40,
      availability: "planned",
      availability_reason: "Model spend and approval gates.",
      execution_class: "governed",
    }),
  ],
  summaries: {},
  matrix: {
    mri: [
      {
        chapter_id: "01-chapter",
        result: "unknown",
        freshness: "unknown",
        has_evidence: false,
        applicable: true,
        artifact_ref: "",
      },
    ],
    metadata: [
      {
        chapter_id: "01-chapter",
        result: "unknown",
        freshness: "unknown",
        has_evidence: true,
        applicable: true,
        artifact_ref: "metadata/01-chapter.yaml",
      },
    ],
  },
  refresh_note: "",
};

function renderBook(campaigns: QualityCampaign[] = []) {
  const detail = makeProjectDetail({
    id: "math",
    name: "Math",
    book: makeBook({ id: "book-math", project_id: "math", project_name: "Math" }),
  });
  const calls = mockFetch(({ path, method }) => {
    if (path === "/api/living-book/projects/math" && method === "GET") {
      return apiError(404, "no book");
    }
    if (path === "/api/quality/campaigns" && method === "GET") return json(campaigns);
    if (path === "/api/pipeline/books/math" && method === "GET") return json(PIPELINE);
    if (path === "/api/quality/campaigns" && method === "POST") {
      return json(CAMPAIGN, 201);
    }
    if (path === `/api/quality/campaigns/${CAMPAIGN.id}/run` && method === "POST") {
      return json(CAMPAIGN);
    }
    if (path === "/api/technical/campaigns" && method === "POST") {
      return json(TECH_CAMPAIGN, 201);
    }
    if (path === `/api/technical/campaigns/${TECH_CAMPAIGN.id}/run` && method === "POST") {
      return json(TECH_CAMPAIGN);
    }
    if (path === "/api/pipeline/maintenance/retry" && method === "POST") {
      return json({ execution_id: "exec-1", status: "queued" });
    }
    return apiError(404, `Unhandled ${method} ${path}`);
  });
  renderRoute(
    <BookTab
      projectId="math"
      data={detail}
      discovery={[CHAPTER]}
      onRefresh={() => undefined}
    />,
    "/projects/math?tab=book",
  );
  return calls;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BookTab chapter execution", () => {
  it("starts a one-chapter prose review from the inventory", async () => {
    const user = userEvent.setup();
    const calls = renderBook();

    await screen.findByRole("heading", { name: "Manuscript and chapter inventory" });
    await user.click(screen.getByRole("button", { name: "Run chapter work for 01-chapter.md" }));

    expect(await screen.findByRole("heading", { name: "Run chapter work" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Run prose review/ }));

    await waitFor(() =>
      expect(
        calls.some((call) => call.method === "POST" && call.path === "/api/quality/campaigns"),
      ).toBe(true),
    );
    const created = calls.find(
      (call) => call.method === "POST" && call.path === "/api/quality/campaigns",
    );
    expect(created?.body).toMatchObject({
      project_id: "math",
      mode: "selected",
      chapters: ["01-chapter.md"],
      strategy: "direct",
    });
    expect(
      calls.some(
        (call) =>
          call.method === "POST" &&
          call.path === `/api/quality/campaigns/${CAMPAIGN.id}/run`,
      ),
    ).toBe(true);
  });

  it("starts technical analysis through the technical campaign endpoint", async () => {
    const user = userEvent.setup();
    const calls = renderBook();

    await user.click(
      await screen.findByRole("button", { name: "Run chapter work for 01-chapter.md" }),
    );
    await user.click(screen.getByRole("button", { name: /Run technical analysis/ }));

    await waitFor(() =>
      expect(
        calls.some(
          (call) => call.method === "POST" && call.path === "/api/technical/campaigns",
        ),
      ).toBe(true),
    );
    const created = calls.find(
      (call) => call.method === "POST" && call.path === "/api/technical/campaigns",
    );
    expect(created?.body).toMatchObject({
      project_id: "math",
      mode: "selected",
      chapters: ["01-chapter.md"],
    });
    expect(
      calls.some(
        (call) =>
          call.method === "POST" &&
          call.path === `/api/technical/campaigns/${TECH_CAMPAIGN.id}/run`,
      ),
    ).toBe(true);
  });

  it("queues deterministic MRI observation for the selected chapter", async () => {
    const user = userEvent.setup();
    const calls = renderBook();

    await user.click(
      await screen.findByRole("button", { name: "Run chapter work for 01-chapter.md" }),
    );
    await user.click(screen.getByRole("button", { name: /Run MRI observation/ }));

    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "POST" && call.path === "/api/pipeline/maintenance/retry",
        ),
      ).toBe(true),
    );
    const queued = calls.find(
      (call) => call.method === "POST" && call.path === "/api/pipeline/maintenance/retry",
    );
    expect(queued?.body).toEqual({
      project_id: "math",
      chapter_id: "01-chapter",
      stage_id: "mri",
    });
  });

  it("links to the Quality workspace filtered to the chapter", async () => {
    const user = userEvent.setup();
    renderBook();

    await user.click(
      await screen.findByRole("button", { name: "Run chapter work for 01-chapter.md" }),
    );
    expect(screen.getByRole("link", { name: "Open in Quality" })).toHaveAttribute(
      "href",
      "/projects/math?tab=quality&qview=chapters&qchapter=01-chapter.md",
    );
  });

  it("blocks a second prose launch while a campaign is active", async () => {
    const user = userEvent.setup();
    renderBook([{ ...CAMPAIGN, status: "running" }]);

    await user.click(
      await screen.findByRole("button", { name: "Run chapter work for 01-chapter.md" }),
    );

    expect(screen.getByText(/A prose campaign is running/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Re-run prose review|Run prose review/ })).toBeDisabled();
  });

  it("starts a missing-chapter campaign from the inventory header", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const calls = renderBook();

    await user.click(await screen.findByRole("button", { name: "Evaluate prose (1)" }));

    await waitFor(() =>
      expect(
        calls.some((call) => call.method === "POST" && call.path === "/api/quality/campaigns"),
      ).toBe(true),
    );
    const created = calls.find(
      (call) => call.method === "POST" && call.path === "/api/quality/campaigns",
    );
    expect(created?.body).toMatchObject({ project_id: "math", mode: "missing" });
  });
});
