import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { WebsitesPage } from "../pages/WebsitesPage";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import { ToastProvider } from "../components/Toast";

const summary = {
  website_id: "website-programmer-ie",
  discovered: 3,
  published: 2,
  evaluated_current: 1,
  evaluated_stale: 0,
  unevaluated: 1,
  average_score: 800,
  average_denominator: 1,
  rubric_id: "blog-editorial-v1",
  rubric_version: 1,
  coverage_percent: 50,
};

const posts = {
  items: [
    {
      website_id: "website-programmer-ie",
      identity: "math.md",
      title: "The New Math",
      relpath: "math.md",
      date: "2026-11-21T10:00:00+00:00",
      post_status: "published",
      word_count: 4200,
      evaluation: {
        evaluation_id: "wpe-1",
        overall: 800,
        status: "CURRENT",
        freshness: "current",
        evaluated_at: "2026-11-22T10:00:00Z",
        stale: false,
        rubric_id: "blog-editorial-v1",
        rubric_version: 1,
      },
    },
    {
      website_id: "website-programmer-ie",
      identity: "code.md",
      title: "I Don't Write Code Anymore",
      relpath: "code.md",
      date: "2026-11-20T10:00:00+00:00",
      post_status: "published",
      word_count: 2100,
      evaluation: {
        evaluation_id: null,
        overall: null,
        status: null,
        freshness: "never",
        evaluated_at: null,
        stale: false,
        rubric_id: null,
        rubric_version: null,
      },
    },
  ],
  total: 2,
  limit: 20,
  offset: 0,
  published: 2,
  drafts: 0,
  scheduled: 0,
  unknown: 0,
};

const evaluation = {
  id: "wpe-1",
  website_id: "website-programmer-ie",
  article_identity: "math.md",
  relpath: "math.md",
  content_sha256: "abc",
  rubric_id: "blog-editorial-v1",
  rubric_version: 1,
  prompt_version: "1",
  requested_model: "fake",
  actual_model: "fake",
  status: "CURRENT",
  overall: 800,
  aggregation_method: "sum_dimensions_v1",
  dimensions: [
    { id: "thesis_purpose", label: "Thesis and purpose", score: 120, max_points: 150, explanation: "Clear." },
  ],
  assessment: "Strong piece.",
  strengths: ["a", "b", "c"],
  weaknesses: ["d", "e", "f"],
  improvements: [
    {
      finding_id: "improvement-1",
      rank: 1,
      title: "Sharpen thesis",
      problem: "Vague",
      why_it_matters: "Focus",
      suggestion: "State it",
      source_heading: "Intro",
      source_quote: "quoted passage",
      quote_anchored: true,
    },
  ],
  findings: [
    {
      finding_id: "f1",
      kind: "observation",
      title: "Note",
      detail: "Worth a follow-up.",
      source_heading: null,
      source_quote: "invented passage",
      quote_anchored: false,
    },
  ],
  uncertainty: "None.",
  limitations: ["Single-model review."],
  execution: {},
  previous_evaluation_id: null,
  freshness: "current",
  stale: false,
  created_at: "2026-11-22T10:00:00Z",
};

const detail = {
  post: posts.items[0],
  content: "# The New Math\n\nBody.",
  content_truncated: false,
  content_sha256: "abc",
  evaluations: [evaluation],
  current: evaluation,
};

function mockPosts(extra?: (call: { path: string; method: string; body: unknown }) => Response | undefined) {
  return mockFetch((call) => {
    if (extra) {
      const response = extra(call);
      if (response) return response;
    }
    if (call.path === "/api/websites")
      return json([
        {
          id: "website-programmer-ie", name: "Programmer Ie", path: "C:\\websites\\programmer.ie",
          is_hugo: true, site_type: "hugo", evidence: ["Hugo configuration observed: hugo.toml"],
          hugo_config: "hugo.toml", content_section: "post", title: "Programmer.ie",
          available: true, launch_supported: true, hugo_available: true,
          running: false, preview_url: null, port: null, process_id: null,
        },
      ]);
    if (call.path === "/api/websites/diagnostics")
      return json({ root: "C:\\websites", diagnostics: [] });
    if (call.path === "/api/websites/website-programmer-ie/posts/summary") return json(summary);
    if (call.path === "/api/websites/website-programmer-ie/posts") return json(posts);
    if (call.path === "/api/websites/website-programmer-ie/posts/math.md") return json(detail);
    if (call.path === "/api/websites/website-programmer-ie/posts/code.md")
      return json({
        post: posts.items[1],
        content: "# Code\n\nBody.",
        content_truncated: false,
        content_sha256: "def",
        evaluations: [],
        current: null,
      });
    if (call.path === "/api/websites/website-programmer-ie/evaluations/wpe-1/reviews") return json([]);
    return apiError(404, `Unhandled ${call.path}`);
  });
}

describe("PostsTab", () => {
  it("shows the Posts tab with summary, filters and scored list", async () => {
    mockPosts();
    const user = userEvent.setup();
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    await user.click(await screen.findByRole("tab", { name: "Posts" }));
    expect(await screen.findByText("Published articles")).toBeInTheDocument();
    expect(await screen.findByText("800 / 1000")).toBeInTheDocument();
    expect(await screen.findByText(/across 1 current blog-editorial-v1 v1 evaluation/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /The New Math/ })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /I Don't Write Code Anymore/ })).toBeInTheDocument();
  });

  it("opens article detail with dimensions, improvements and unanchored flags", async () => {
    mockPosts();
    const user = userEvent.setup();
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    await user.click(await screen.findByRole("tab", { name: "Posts" }));
    await user.click(await screen.findByRole("button", { name: /The New Math/ }));
    expect(await screen.findByText("800 / 1000")).toBeInTheDocument();
    expect(await screen.findByRole("progressbar", { name: /Thesis and purpose/ })).toBeInTheDocument();
    expect(
      (await screen.findAllByText((_, element) => element?.textContent === "#1 Sharpen thesis"))
        .length,
    ).toBeGreaterThan(0);
    expect(await screen.findByText(/Unanchored — not found verbatim/)).toBeInTheDocument();
  });

  it("records finding reviews and evaluates unevaluated articles", async () => {
    const calls = mockPosts((call) => {
      if (call.path.endsWith("/evaluate") && call.method === "POST") return json(evaluation);
      if (call.path.endsWith("/reviews") && call.method === "POST")
        return json({ id: "wpr-1", finding_id: "f1", decision: "ACCEPT" }, 201);
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(
      <ToastProvider>
        <WebsitesPage />
      </ToastProvider>,
      "/websites",
    );
    await user.click(await screen.findByRole("tab", { name: "Posts" }));
    await user.click(await screen.findByRole("button", { name: /The New Math/ }));
    const acceptButtons = await screen.findAllByRole("button", { name: "Accept" });
    await user.click(acceptButtons[0]);
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.path.endsWith("/reviews"))).toBe(true);
    });
    await user.click(screen.getByRole("button", { name: "Back to articles" }));
    await user.click(await screen.findByRole("button", { name: /I Don't Write Code Anymore/ }));
    // No current evaluation: the detail offers evaluation instead of scores.
    expect(await screen.findByRole("button", { name: "Evaluate with AI" })).toBeInTheDocument();
  });
});
