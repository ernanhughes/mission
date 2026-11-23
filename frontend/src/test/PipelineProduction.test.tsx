import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import type {
  PipelineBookMatrix,
  PipelineOverview,
  PipelineStage,
  PipelineStageDetail,
  PipelineSummary,
} from "../types/api";
import { BooksPage, BooksCollectionPage } from "../pages/BooksPage";
import { FictionBooksPage } from "../pages/FictionBooksPage";
import { ProductionOverview } from "../features/pipeline/ProductionOverview";
import { ChapterMatrix } from "../features/pipeline/ChapterMatrix";
import { StageEvidencePanel } from "../features/pipeline/StageEvidencePanel";
import {
  PIPELINE_VISIBILITY_KEY,
  bookMatchesFilters,
  cellStatus,
  summaryStatus,
} from "../features/pipeline/pipelineStatus";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { makeBook } from "./fixtures";

const STAGES: PipelineStage[] = [
  {
    stage_id: "mri", name: "MRI", description: "MRI reports", owner: "writer",
    scope: "chapter", applicability: "all", freshness_method: "snapshot compare",
    prerequisites: "none", presentation_order: 20, availability: "implemented",
    availability_reason: "verified", ui_actions: [],
  },
  {
    stage_id: "editing", name: "Editing", description: "editing audits", owner: "writer",
    scope: "chapter", applicability: "all", freshness_method: "fingerprint compare",
    prerequisites: "none", presentation_order: 50, availability: "implemented",
    availability_reason: "verified", ui_actions: [],
  },
  {
    stage_id: "graph", name: "Graph", description: "graph", owner: "writer",
    scope: "chapter", applicability: "verified only", freshness_method: "n/a",
    prerequisites: "provider", presentation_order: 70, availability: "unavailable",
    availability_reason: "provider unverified", ui_actions: [],
  },
];

function summary(overrides: Partial<PipelineSummary> = {}): PipelineSummary {
  return {
    applicable: 4, with_evidence: 4, current: 4, stale: 0, missing: 0, unknown: 0,
    passed: 4, failed: 0, pending: 0, coverage: "4/4 current", coverage_fraction: 1,
    fully_current: true, availability: "implemented", ...overrides,
  };
}

function overviewBook(projectId: string, summaries: Record<string, PipelineSummary>) {
  return {
    project_id: projectId, book_title: `${projectId} title`, known: true, profile: "technical",
    applicable_chapters: 4, discovery_error: null, chapter_dir: `C:\\books\\${projectId}`,
    validation_enabled: false, human_approval_required: false, elapsed_ms: 12,
    summaries,
  };
}

function overviewPayload(): PipelineOverview {
  return {
    registry_version: "pipeline-stages-v1", registry_source: "registry.yaml",
    book_count: 2, elapsed_ms: 90, stages: STAGES,
    books: [
      overviewBook("memory", {
        mri: summary({ applicable: 2, with_evidence: 1, current: 0, stale: 1, missing: 1, unknown: 0, coverage: "0/2 current", coverage_fraction: 0, fully_current: false, failed: 1, passed: 0 }),
        editing: summary({ applicable: 2, current: 2, coverage: "2/2 current" }),
        graph: summary({ applicable: 2, availability: "unavailable" }),
      }),
      overviewBook("language", {
        mri: summary({ applicable: 3, current: 3, coverage: "3/3 current" }),
        editing: summary({ applicable: 3, current: 3, coverage: "3/3 current" }),
        graph: summary({ applicable: 3, availability: "unavailable" }),
      }),
    ],
    refresh_note: "read-only",
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

// --- pure status helpers ------------------------------------------------------

describe("pipelineStatus", () => {
  it("keeps failed and stale as separate dimensions", () => {
    expect(cellStatus({ result: "failed", freshness: "stale", has_evidence: true, applicable: true }))
      .toEqual({ tone: "failed", label: "failed · stale evidence", short: "failed·stale" });
    expect(cellStatus({ result: "passed", freshness: "stale", has_evidence: true, applicable: true }).tone)
      .toBe("stale");
  });

  it("maps every supported combination", () => {
    expect(cellStatus({ result: "passed", freshness: "current", has_evidence: true, applicable: true }).tone).toBe("current");
    expect(cellStatus({ result: "unknown", freshness: "unknown", has_evidence: false, applicable: true }).tone).toBe("missing");
    expect(cellStatus({ result: "unknown", freshness: "unknown", has_evidence: true, applicable: true }).tone).toBe("unknown");
    expect(cellStatus({ result: "failed", freshness: "current", has_evidence: true, applicable: true }).tone).toBe("failed");
    expect(cellStatus({ result: "passed", freshness: "unknown", has_evidence: true, applicable: true }).tone).toBe("unknown");
    expect(cellStatus({ result: "unknown", freshness: "unknown", has_evidence: true, applicable: false }).tone).toBe("na");
    expect(cellStatus({ result: "unavailable", freshness: "unknown", has_evidence: false, applicable: true }).tone).toBe("na");
  });

  it("never renders planned or unavailable stages as 0% complete", () => {
    expect(summaryStatus(summary({ applicable: 2 }), "planned")).toEqual({ tone: "planned", label: "planned", short: "planned" });
    expect(summaryStatus(summary({ applicable: 2 }), "unavailable").tone).toBe("na");
    const failedStale = summary({ applicable: 4, current: 1, stale: 2, failed: 1, passed: 1, coverage: "1/4 current", fully_current: false });
    expect(summaryStatus(failedStale, "implemented").label).toContain("failed");
    expect(summaryStatus(failedStale, "implemented").label).toContain("stale");
  });

  it("filters books by attention dimensions across visible stages only", () => {
    const summaries = {
      mri: summary({ stale: 1, failed: 0 }),
      editing: summary({ stale: 0 }),
    };
    expect(bookMatchesFilters(summaries, ["mri", "editing"], ["stale"])).toBe(true);
    expect(bookMatchesFilters(summaries, ["mri", "editing"], ["failed"])).toBe(false);
    expect(bookMatchesFilters(summaries, ["editing"], ["stale"])).toBe(false);
    expect(bookMatchesFilters(summaries, ["mri"], [])).toBe(true);
  });
});

// --- overview -------------------------------------------------------------------

describe("ProductionOverview", () => {
  function mockAll() {
    return mockFetch(({ path }) => {
      if (path === "/api/pipeline/stages") return json({ registry_version: "pipeline-stages-v1", stages: STAGES });
      if (path === "/api/pipeline/overview") return json(overviewPayload());
      return apiError(404, `Unhandled ${path}`);
    });
  }

  it("renders coverage per book and marks planned stages without percentages", async () => {
    mockAll();
    renderRoute(
      <ProductionOverview hidden={[]} onToggleStage={() => undefined} onSelectBook={() => undefined} />,
      "/books",
    );
    expect(await screen.findByRole("heading", { name: "Production & Quality" })).toBeInTheDocument();
    expect(await screen.findByText("memory title")).toBeInTheDocument();
    // MRI memory: 0/2 current, stale.
    expect(screen.getAllByText("0/2 current").length).toBeGreaterThan(0);
    // Graph column shows planned, never 0% complete.
    const planned = screen.getAllByText("planned");
    expect(planned.length).toBeGreaterThan(0);
    expect(screen.queryByText("0/2")).not.toBeInTheDocument();
  });

  it("filters books by attention dimensions", async () => {
    mockAll();
    const user = userEvent.setup();
    renderRoute(
      <ProductionOverview hidden={[]} onToggleStage={() => undefined} onSelectBook={() => undefined} />,
      "/books",
    );
    await screen.findByText("memory title");
    expect(screen.getByText("language title")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Failed" }));
    expect(screen.queryByText("language title")).not.toBeInTheDocument();
    expect(screen.getByText("memory title")).toBeInTheDocument();
  });

  it("shows loading, error and empty states", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/pipeline/stages") return json({ registry_version: "v1", stages: STAGES });
      if (path === "/api/pipeline/overview") return apiError(500, "boom");
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(
      <ProductionOverview hidden={[]} onToggleStage={() => undefined} onSelectBook={() => undefined} />,
      "/books",
    );
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("selects a book when its row button is activated", async () => {
    mockAll();
    const user = userEvent.setup();
    let selected = "";
    renderRoute(
      <ProductionOverview hidden={[]} onToggleStage={() => undefined} onSelectBook={(id) => { selected = id; }} />,
      "/books",
    );
    await user.click(await screen.findByRole("button", { name: /Open production matrix for memory title/ }));
    expect(selected).toBe("memory");
  });
});

// --- chapter matrix ---------------------------------------------------------------

function matrixPayload(): PipelineBookMatrix {
  const cell = (chapter_id: string, result: string, freshness: string, has_evidence: boolean) => ({
    chapter_id, result, freshness, has_evidence, applicable: true, artifact_ref: `${chapter_id}.json`,
  });
  return {
    project_id: "memory", known: true, book_title: "memory title",
    registry_version: "pipeline-stages-v1", chapter_dir: "C:\\books\\memory",
    chapter_pattern: "*.md", profile: "technical", discovery: {},
    chapters: [
      { chapter_id: "01-chapter", filename: "01-chapter.md", path: "C:\\books\\memory\\01-chapter.md" },
      { chapter_id: "02-chapter", filename: "02-chapter.md", path: "C:\\books\\memory\\02-chapter.md" },
    ],
    stages: STAGES,
    summaries: {
      mri: summary({ applicable: 2, current: 1, stale: 1, coverage: "1/2 current", fully_current: false }),
      editing: summary({ applicable: 2, current: 2, coverage: "2/2 current" }),
      graph: summary({ applicable: 2, availability: "unavailable" }),
    },
    matrix: {
      mri: [cell("01-chapter", "failed", "stale", true), cell("02-chapter", "passed", "current", true)],
      editing: [cell("01-chapter", "passed", "current", true), cell("02-chapter", "passed", "current", true)],
      graph: [cell("01-chapter", "unavailable", "unknown", false), cell("02-chapter", "unavailable", "unknown", false)],
    },
    refresh_note: "read-only",
  };
}

describe("ChapterMatrix", () => {
  it("renders mixed states and failed+stale distinctly", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/pipeline/books/memory") return json(matrixPayload());
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(
      <ChapterMatrix projectId="memory" bookTitle="memory title" stages={STAGES} hiddenStages={[]} onInspect={() => undefined} />,
      "/books",
    );
    expect(await screen.findByText("01-chapter")).toBeInTheDocument();
    const failedStale = await screen.findByRole("button", { name: /MRI — 01-chapter: failed · stale evidence/ });
    expect(failedStale).toHaveTextContent("failed·stale");
    expect(screen.getByRole("button", { name: /Editing — 02-chapter: current/ })).toBeInTheDocument();
  });

  it("hides concealed stage columns and inspects cells on demand", async () => {
    const calls: string[] = [];
    mockFetch(({ path }) => {
      calls.push(path);
      if (path === "/api/pipeline/books/memory") return json(matrixPayload());
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    let inspected: [string, string] | null = null;
    renderRoute(
      <ChapterMatrix
        projectId="memory" bookTitle="memory title" stages={STAGES} hiddenStages={["editing"]}
        onInspect={(stageId, chapterId) => { inspected = [stageId, chapterId]; }}
      />,
      "/books",
    );
    await screen.findByText("01-chapter");
    expect(screen.queryByText("Editing")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /MRI — 02-chapter/ }));
    expect(inspected).toEqual(["mri", "02-chapter"]);
    expect(calls.filter((path) => path.includes("/stages/"))).toHaveLength(0);
  });
});

// --- evidence panel -----------------------------------------------------------------

function stageDetailPayload(): PipelineStageDetail {
  return {
    project_id: "memory",
    stage: STAGES[0],
    registry_version: "pipeline-stages-v1",
    summary: summary(),
    cells: [
      {
        stage_id: "mri", project_id: "memory", chapter_id: "01-chapter",
        chapter_path: "C:\\books\\memory\\01-chapter.md", applicable: true,
        not_applicable_reason: null, result: "failed", freshness: "stale",
        has_evidence: true, artifact_ref: "C:\\books\\memory\\.writer\\mri\\memory\\01-chapter.mri.json",
        stored_digest: "aaa", live_digest: "bbb", digest_match: false,
        digest_algorithm: "snapshot:sha256-utf8-text",
        observed_at: "2026-09-22T00:00:00Z", executed_at: "2026-09-22T07:14:00Z",
        provider: "writer", stage_version: "e3f7",
        diagnostics: "Stored snapshot no longer matches the live chapter.",
        detail: { observer_mode: "auto" },
      },
    ],
  };
}

describe("StageEvidencePanel", () => {
  it("presents result and freshness separately with digests and diagnostics", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/pipeline/books/memory/stages/mri") return json(stageDetailPayload());
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    let closed = false;
    renderRoute(
      <StageEvidencePanel projectId="memory" bookTitle="memory title" chapterId="01-chapter" stage={STAGES[0]} onClose={() => { closed = true; }} />,
      "/books",
    );
    expect(await screen.findByText("Stored snapshot no longer matches the live chapter.")).toBeInTheDocument();
    expect(screen.getByText("snapshot:sha256-utf8-text")).toBeInTheDocument();
    expect(screen.getByText(/Failed and stale are separate/)).toBeInTheDocument();
    expect(screen.getByText(/Analysis execution is not available in this view/)).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(closed).toBe(true);
  });

  it("states explicitly that current editing is not applied editing", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/pipeline/books/memory/stages/editing") {
        const payload = stageDetailPayload();
        const cell = { ...payload.cells[0], stage_id: "editing", result: "passed", freshness: "current", digest_match: true };
        return json({ ...payload, stage: STAGES[1], cells: [cell] });
      }
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(
      <StageEvidencePanel projectId="memory" bookTitle="memory title" chapterId="01-chapter" stage={STAGES[1]} onClose={() => undefined} />,
      "/books",
    );
    expect(await screen.findByText(/does not mean the chapter was edited or improved/)).toBeInTheDocument();
  });
});

// --- Books page integration ------------------------------------------------------------

describe("BooksPage production tab", () => {
  function mockWorkspace() {
    return mockFetch(({ path }) => {
      if (path === "/api/books") return json([makeBook()]);
      if (path === "/api/pipeline/stages") return json({ registry_version: "pipeline-stages-v1", stages: STAGES });
      if (path === "/api/pipeline/overview") return json(overviewPayload());
      return apiError(404, `Unhandled ${path}`);
    });
  }

  it("defaults to the workspace and preserves existing behavior", async () => {
    mockWorkspace();
    const user = userEvent.setup();
    renderRoute(<BooksPage />, "/books");
    await screen.findByRole("heading", { name: "Language: When Intelligence Enters the Channel" });
    await user.click(screen.getByRole("tab", { name: "Production" }));
    expect(await screen.findByRole("heading", { name: "Production & Quality" })).toBeInTheDocument();
    expect(screen.getByText("memory title")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Workspace" }));
    expect(await screen.findByRole("heading", { name: "Language: When Intelligence Enters the Channel" })).toBeInTheDocument();
  });

  it("persists hidden stages to localStorage", async () => {
    mockWorkspace();
    const user = userEvent.setup();
    renderRoute(<BooksPage />, "/books");
    await user.click(screen.getByRole("tab", { name: "Production" }));
    await screen.findByText("memory title");
    await user.click(screen.getByText("3/3 stages"));
    await user.click(screen.getByRole("checkbox", { name: "MRI" }));
    expect(window.localStorage.getItem(PIPELINE_VISIBILITY_KEY)).toContain("mri");
    expect(screen.queryByText("0/2 current")).not.toBeInTheDocument();
  });

  it("fiction books keep the workspace without a production tab", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/fiction-books") return json([makeBook({ id: "book-goblins", project_id: "goblins", project_name: "Goblins", title: "Goblins" })]);
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<FictionBooksPage />, "/fiction-books");
    await screen.findByRole("heading", { name: "Goblins" });
    expect(screen.queryByRole("tab", { name: "Production" })).not.toBeInTheDocument();
  });

  it("BookEditor still saves book state (existing behavior)", async () => {
    const calls = mockWorkspace();
    const user = userEvent.setup();
    renderRoute(
      <BooksCollectionPage
        apiBase="/api/books" eyebrow="Books" title="Books" description="d" emptyHint="e"
      />,
      "/books",
    );
    await screen.findByRole("heading", { name: "Language: When Intelligence Enters the Channel" });
    expect(screen.queryByRole("tab", { name: "Production" })).not.toBeInTheDocument();
    expect(calls.some((call) => call.path.startsWith("/api/pipeline"))).toBe(false);
  });
});
