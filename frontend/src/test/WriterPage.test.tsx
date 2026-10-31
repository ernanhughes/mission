import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { WriterPage } from "../pages/WriterPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import type { WriterBook, WriterChapter, WriterWorkspace } from "../types/api";

function chapter(overrides: Partial<WriterChapter> = {}): WriterChapter {
  return {
    chapter_id: "chapter:language:24-chapter",
    title: "Memory can be right and still make the present wrong",
    source_path: "C:\\Projects\\language\\content\\books\\language\\24-chapter.md",
    relative_path: "content/books/language/24-chapter.md",
    source_fingerprint: "abc123",
    order: 23,
    word_count: 2200,
    paragraph_count: 40,
    sentence_count: 120,
    status: "review_required",
    current: true,
    status_band: "high",
    highest_risk: { subdimension: "fragmentation", score: 29.3 },
    dimensions: [
      {
        id: "paragraph_load",
        label: "Paragraph load",
        score: 61.0,
        status_band: "watch",
        finding_codes: ["READABILITY.PARAGRAPH_DENSITY"],
        raw_metrics: { p90_paragraph_words: 124 },
        explanation: "Measures paragraph volume.",
        limitations: ["Heuristic."],
        scoring: { formula: "100 - penalty", weights: { density: 55 } },
      },
      {
        id: "sentence_load",
        label: "Sentence load",
        score: 95.9,
        status_band: "good",
        finding_codes: [],
        raw_metrics: { p90_sentence_words: 28 },
        explanation: "Measures sentence volume.",
        limitations: ["Heuristic."],
        scoring: { formula: "100 - penalty", weights: { sentence: 65 } },
      },
      {
        id: "fragmentation",
        label: "Fragmentation",
        score: 29.3,
        status_band: "high",
        finding_codes: ["READABILITY.FRAGMENTATION"],
        raw_metrics: { short_percent: 80.36, max_consecutive_short_run: 15 },
        explanation: "Detects excessive fragmentation.",
        limitations: ["Heuristic."],
        scoring: { formula: "100 - penalty", weights: { short: 70 } },
      },
      {
        id: "rhythm",
        label: "Rhythm",
        score: 53.6,
        status_band: "review",
        finding_codes: ["READABILITY.UNIFORM_CADENCE"],
        raw_metrics: { iqr_words: 8 },
        explanation: "Measures cadence.",
        limitations: ["Heuristic."],
        scoring: { formula: "100 - penalty", weights: { uniform: 55 } },
      },
      {
        id: "lexical_accessibility",
        label: "Lexical accessibility",
        score: 100.0,
        status_band: "good",
        finding_codes: [],
        raw_metrics: { flesch_reading_ease: 36.25 },
        explanation: "Approximate Flesch diagnostics.",
        limitations: ["Flesch does not establish comprehension."],
        scoring: { formula: "100 - penalty", weights: { fre: 3 } },
      },
      {
        id: "section_structure",
        label: "Section structure",
        score: 100.0,
        status_band: "good",
        finding_codes: [],
        raw_metrics: { section_count: 8 },
        explanation: "Measures navigation.",
        limitations: ["Heuristic."],
        scoring: { formula: "100 - penalty", weights: { section: 45 } },
      },
    ],
    finding_codes: ["READABILITY.FRAGMENTATION", "READABILITY.PARAGRAPH_DENSITY", "READABILITY.UNIFORM_CADENCE"],
    finding_count: 3,
    findings: [
      {
        finding_id: "edfinding:language-fragmentation",
        code: "READABILITY.FRAGMENTATION",
        severity: "high",
        dimension: "readability",
        subdimension: "fragmentation",
        book_id: "language",
        chapter_id: "chapter:language:24-chapter",
        source_path: "C:\\Projects\\language\\content\\books\\language\\24-chapter.md",
        locator: {
          chapter_id: "chapter:language:24-chapter",
          source_path: "C:\\Projects\\language\\content\\books\\language\\24-chapter.md",
          relative_path: "content/books/language/24-chapter.md",
          line_start: 22,
          line_end: 22,
          paragraph_index: 4,
          section_title: "Memory can be right and still make the present wrong",
          excerpt: "In October, she asks why a duplicate write can still appear during recovery.",
        },
        measured: { short_percent: 80.36 },
        reason: "Short one-sentence paragraphs dominate the diagnostic sample.",
        recommendation: "Check whether the short paragraphs are doing distinct work.",
        limitations: ["Heuristic."],
      },
    ],
    ...overrides,
  };
}

function book(overrides: Partial<WriterBook> = {}): WriterBook {
  return {
    project_id: "language",
    title: "Language",
    status: "NEEDS_REVIEW",
    profile: "technical-nonfiction-v1",
    project_root: "C:\\Projects\\language",
    content_dir: "C:\\Projects\\language\\content\\books\\language",
    repository_path: "C:\\Projects\\language",
    chapters_available: 38,
    source_revision: "abc123",
    source_dirty: true,
    report_id: "edit-20261024T232619Z-f3560c0e6ce6",
    scope: { kind: "book", whole_book: true, chapter_ids: [] },
    last_checked: "2026-10-24T23:00:00Z",
    canonical_fingerprint: "f3560c0e6ce6",
    editing: { status: "NEEDS_REVIEW" },
    pipeline: {
      metadata: { status: "NOT_TRACKED" },
      mri: { status: "NOT_TRACKED" },
      strengthen: { status: "NOT_TRACKED" },
      editing: { status: "NEEDS_REVIEW" },
    },
    readability: {
      note: "Subdimensions are independent. No composite score is calculated.",
      subdimensions: [
        {
          id: "paragraph_load",
          label: "Paragraph load",
          worst_score: 61.0,
          worst_band: "watch",
          worst_chapter_id: "chapter:language:24-chapter",
          chapters_flagged: 0,
          chapter_scores: [],
        },
        {
          id: "fragmentation",
          label: "Fragmentation",
          worst_score: 29.3,
          worst_band: "high",
          worst_chapter_id: "chapter:language:24-chapter",
          chapters_flagged: 1,
          chapter_scores: [],
        },
      ],
      highest_risk: { subdimension: "fragmentation", score: 29.3, status_band: "high" },
    },
    highest_risk: {
      kind: "finding",
      severity: "high",
      code: "READABILITY.FRAGMENTATION",
      chapter_id: "chapter:language:24-chapter",
      chapter_title: "Memory can be right and still make the present wrong",
      subdimension: "fragmentation",
      score: 29.3,
      status_band: "high",
    },
    chapters: [chapter()],
    findings_preview: [chapter().findings[0]],
    errors: [],
    limitations: ["Read-only evidence."],
    ...overrides,
  };
}

function workspace(overrides: Partial<WriterWorkspace> = {}): WriterWorkspace {
  return {
    available: true,
    detail: "Read 3 Writer book summaries.",
    error: null,
    last_checked_at: "2026-10-24T23:00:00Z",
    generated_at: "2026-10-24T23:00:00Z",
    totals: {
      books: 3,
      with_manuscript: 2,
      audited: 2,
      current: 0,
      needs_review: 1,
      stale: 1,
      partial: 0,
      not_run: 1,
      blocked: 0,
      no_manuscript: 0,
      error: 0,
    },
    review_queue: [
      {
        project_id: "stale-book",
        title: "Stale Book",
        status: "STALE",
        risk_rank: 1,
        highest_risk: { subdimension: "fragmentation", score: 10, status_band: "high" },
        finding_count: 2,
        report_id: "edit-stale",
        last_checked: "2026-10-20T23:00:00Z",
      },
      {
        project_id: "language",
        title: "Language",
        status: "NEEDS_REVIEW",
        risk_rank: 2,
        highest_risk: { subdimension: "fragmentation", score: 29.3, status_band: "high" },
        finding_count: 3,
        report_id: "edit-language",
        last_checked: "2026-10-24T23:00:00Z",
      },
      {
        project_id: "not-run",
        title: "Not Run",
        status: "NOT_RUN",
        risk_rank: 4,
        highest_risk: null,
        finding_count: 0,
        report_id: null,
        last_checked: null,
      },
    ],
    decision_queue: [
      {
        id: "writer-decision:language:READABILITY.FRAGMENTATION:high",
        project_id: "language",
        book_title: "Language",
        book_status: "NEEDS_REVIEW",
        stale: false,
        code: "READABILITY.FRAGMENTATION",
        subdimension: "fragmentation",
        severity: "high",
        dimension: "readability",
        chapter_id: "chapter:language:24-chapter",
        chapter_title: "Memory can be right and still make the present wrong",
        chapter_order: 23,
        chapter_name: "24-chapter.md",
        finding_id: "edfinding:language-fragmentation",
        reason: "Short one-sentence paragraphs dominate the diagnostic sample.",
        recommendation: "Check whether the short paragraphs are doing distinct work.",
        locator: {
          chapter_id: "chapter:language:24-chapter",
          source_path: "C:\\Projects\\language\\content\\books\\language\\24-chapter.md",
          relative_path: "content/books/language/24-chapter.md",
          line_start: 22,
          line_end: 22,
          paragraph_index: 4,
          section_title: "Memory can be right and still make the present wrong",
          excerpt: "In October, she asks why a duplicate write can still appear during recovery.",
        },
        measured: { short_percent: 80.36 },
        limitations: ["Heuristic."],
        count: 3,
        chapter_count: 1,
        decided_count: 0,
        undecided_count: 3,
        state: "undecided",
        decision: null,
        workbench_link:
          "http://127.0.0.1:7420/#chapter=24-chapter.md&menu=edt&drawer=editing&finding=edfinding%3Alanguage-fragmentation",
        workbench_book_ready: true,
      },
    ],
    decision_totals: {
      groups: 1,
      findings: 3,
      undecided: 3,
      decided: 0,
      stale_groups: 0,
      missing_identity: 0,
      confirmed: 0,
      dismissed: 0,
      deferred: 0,
    },
    workbench: {
      url: "http://127.0.0.1:7420",
      book: "language",
      ready: true,
      note: "",
    },
    books: [
      book({
        project_id: "stale-book",
        title: "Stale Book",
        status: "STALE",
        report_id: "edit-stale",
        chapters: [chapter({ current: false, status: "review_required" })],
      }),
      book(),
      book({
        project_id: "not-run",
        title: "Not Run",
        status: "NOT_RUN",
        report_id: null,
        readability: null,
        highest_risk: null,
        chapters: [],
        findings_preview: [],
        last_checked: null,
        canonical_fingerprint: null,
      }),
    ],
    limitations: ["Mission Control displays Writer's report; it does not recalculate readability."],
    ...overrides,
  };
}

describe("WriterPage", () => {
  it("preserves independent subdimensions and shows NOT_RUN separately from a pass", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/writer/books") return json(workspace());
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<WriterPage />, "/writer");

    expect(await screen.findByRole("heading", { name: "Book editing" })).toBeInTheDocument();
    expect(screen.getByText("Cross-book review queue")).toBeInTheDocument();
    expect(screen.getAllByText("NEEDS_REVIEW").length).toBeGreaterThan(0);
    expect(screen.getAllByText("STALE").length).toBeGreaterThan(0);
    expect(screen.getAllByText("NOT_RUN").length).toBeGreaterThan(0);
    expect(screen.getAllByText("29.3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("61").length).toBeGreaterThan(0);
    expect(screen.getByText(/No evidence, not a pass/i)).toBeInTheDocument();
    expect(screen.getByText(/No composite score/)).toBeInTheDocument();
  });

  it("drills into a chapter finding with its source locator and raw metrics", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/writer/books") return json(workspace());
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<WriterPage />, "/writer");
    await screen.findByRole("heading", { name: "Book editing" });

    const languageRow = (await screen.findAllByRole("row")).find((row) =>
      row.textContent?.includes("Language"),
    );
    expect(languageRow).toBeTruthy();
    await user.click(languageRow!);
    expect(
      (await screen.findAllByText("Memory can be right and still make the present wrong")).length,
    ).toBeGreaterThan(0);
    expect((await screen.findAllByText("READABILITY.FRAGMENTATION")).length).toBeGreaterThan(0);
    expect(
      Array.from(document.querySelectorAll("code.writer-locator")).some((element) =>
        element.textContent?.includes("content/books/language/24-chapter.md:22"),
      ),
    ).toBe(true);
    expect(screen.getByText(/Check whether the short paragraphs/)).toBeInTheDocument();
    expect(screen.getAllByText(/Raw metrics and scoring/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Flesch does not establish comprehension/).length).toBeGreaterThan(0);
  });

  it("groups repeated findings and links the representative to the exact Workbench finding", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/writer/books") return json(workspace());
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<WriterPage />, "/writer");

    expect(await screen.findByRole("heading", { name: "Decision queue" })).toBeInTheDocument();
    expect(screen.getAllByText("READABILITY.FRAGMENTATION").length).toBeGreaterThan(0);
    expect(screen.getByText("Undecided")).toBeInTheDocument();
    expect(screen.getByText("3 findings in 1 chapter")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Open in Workbench/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("#chapter=24-chapter.md"));
    expect(link).toHaveAttribute("href", expect.stringContaining("finding=edfinding"));
  });


  it("marks partial book evidence in the decision queue", async () => {
    const base = workspace();
    mockFetch(({ path }) => {
      if (path === "/api/writer/books") {
        return json(
          workspace({
            decision_queue: [{ ...base.decision_queue[0], book_status: "PARTIAL" }],
          }),
        );
      }
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<WriterPage />, "/writer");
    expect(await screen.findByText("Partial evidence")).toBeInTheDocument();
  });

  it("shows a truthful unavailable state when Writer is not configured", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/writer/books")
        return json(
          workspace({
            available: false,
            detail: "Writer CLI is unavailable.",
            error: "Writer repository unavailable",
            books: [],
            review_queue: [],
          }),
        );
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<WriterPage />, "/writer");
    expect(await screen.findByText(/Writer CLI is unavailable/)).toBeInTheDocument();
    expect(screen.getByText("No Writer editing evidence")).toBeInTheDocument();
  });
});
