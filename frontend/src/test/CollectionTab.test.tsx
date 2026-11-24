import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CollectionTab } from "../features/websites/CollectionTab";
import { apiError, json, mockFetch, renderRoute } from "./helpers";
import type { Website, WebsiteCollectionQuality } from "../types/api";

const site = {
  id: "website-programmer-ie",
  name: "Programmer Ie",
  path: "C:\\websites\\programmer.ie",
  is_hugo: true,
  site_type: "hugo",
  evidence: [],
  hugo_config: "hugo.toml",
  content_section: "post",
  title: "Programmer.ie",
  available: true,
  launch_supported: false,
  hugo_available: false,
  running: false,
  preview_url: null,
  port: null,
  process_id: null,
} as unknown as Website;

function collectionFixture(): WebsiteCollectionQuality {
  return {
    schema: "site-collection-quality.v1",
    generated_at: "2026-01-01T00:00:00+00:00",
    generator: "mission.websites.collection.build_collection_quality_map",
    site: { website_id: "website-programmer-ie", blog_dir: "post" },
    inventory: { discovered: 4, published: 3, draft: 1, scheduled: 0, unknown: 0 },
    coverage: {
      denominator: "published posts only",
      published: 3,
      evaluated_current: 1,
      evaluated_stale: 1,
      unevaluated: 1,
      coverage_percent: 100 / 3,
    },
    scores: {
      rubric_id: "blog-editorial-v1",
      rubric_version: 1,
      aggregation_method: "sum_dimensions_v1",
      max_total: 1000,
      denominator: "current only",
      n_scored: 1,
      average: 800,
      min: 800,
      max: 800,
      weakest: [
        { identity: "alpha.md", relpath: "alpha.md", title: "Alpha", overall: 800, evaluation_id: "wpe-1" },
      ],
      excluded: { stale_or_superseded: 1, non_current_status: 0, other_rubric: 2, unscored_or_missing_post: 0 },
      rows_examined: 6,
      rows_capped: false,
    },
    review_queues: {
      stale_oldest_first: [
        {
          identity: "beta.md",
          relpath: "beta.md",
          title: "Beta",
          date: "2024-03-11T10:00:00+00:00",
          evaluation_id: "wpe-2",
          overall: 500,
          evaluated_digest: "a".repeat(64),
          live_digest: "b".repeat(64),
        },
      ],
      unevaluated_oldest_first: [{ identity: "gamma.md", relpath: "gamma.md", title: "Gamma" }],
    },
    duplication_candidates: [
      {
        candidate_id: "dup-title-001",
        kind: "shared_title",
        decision: "pending",
        note: "Human decision required; not a merge verdict.",
        evidence: { normalized_title: "same title", digest: "c".repeat(64), posts: [] },
      },
    ],
    duplication_unmapped: [],
    provisional: {
      contradictions: { status: "unavailable", reason: "No paired-quote evidence exists." },
      topic_gaps: { status: "unavailable", reason: "No topic taxonomy bound." },
      outdated_claims: { status: "unavailable", reason: "No dated external evidence." },
    },
    limitations: ["Editorial evidence, not a publication decision."],
  };
}

function mockCollection(collection: WebsiteCollectionQuality | null, extra?: (call: { path: string; method: string; body: unknown }) => Response | undefined) {
  return mockFetch(({ path, method, body }) => {
    if (extra) {
      const response = extra({ path, method, body });
      if (response) return response;
    }
    if (path === "/api/websites/website-programmer-ie/collection/quality") {
      if (collection === null) return apiError(500, "boom");
      return json(collection);
    }
    return apiError(404, `Unhandled ${path}`);
  });
}

describe("CollectionTab", () => {
  it("shows stats, queues and filters without inventing scores", async () => {
    mockCollection(collectionFixture());
    const user = userEvent.setup();
    renderRoute(<CollectionTab site={site} />, "/websites");
    expect(await screen.findByText("Collection quality")).toBeInTheDocument();
    expect(screen.getByText("33%")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Filter collection view"), "stale");
    expect(screen.queryByText("Gamma")).not.toBeInTheDocument();
    expect(await screen.findByText("Beta")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Filter collection view"), "duplicates");
    expect(await screen.findByText(/Shared title/)).toBeInTheDocument();
    expect(screen.getAllByText(/pending/i).length).toBeGreaterThan(0);
  });

  it("runs a deterministic Writer check on demand and shows the binding", async () => {
    const calls = mockCollection(collectionFixture(), ({ path, method }) => {
      if (path === "/api/websites/website-programmer-ie/posts/beta.md/writer-observation" && method === "POST")
        return json({
          schema_version: "writer.evaluation-envelope.v1",
          evaluation_id: "artifact-rev9",
          observed_at: "2026-01-02T00:00:00Z",
          status: "complete",
          work_object: {
            kind: "post",
            target_id: "beta.md",
            source_hash: "d".repeat(64),
            content_sha256: "e".repeat(64),
            text_sha256: "d".repeat(64),
          },
          producer: { runtime_name: "artifact", method: "analyze_text", method_version: "writer-artifact-detection.v1" },
          dimensions: [{ dimension: "artifact_score", score: 90 }],
          findings: [{ code: "ANAPHORA_RUN", claim: "Anaphora chant", severity: "MED", evidence: ["L1: x"] }],
          limitations: ["Deterministic stylistic detector only."],
        });
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CollectionTab site={site} />, "/websites");
    await screen.findByText("Beta");
    const detailButtons = screen.getAllByRole("button", { name: "Show evidence" });
    await user.click(detailButtons[0]);
    await user.click(screen.getByRole("button", { name: "Run Writer check" }));
    expect(await screen.findByText(/ANAPHORA_RUN/)).toBeInTheDocument();
    expect(screen.getByText(/bound to the observed body bytes/)).toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/writer-observation") && call.method === "POST")).toBe(true);
  });

  it("shows human review state on the latest evaluation", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/websites/website-programmer-ie/collection/quality") return json(collectionFixture());
      if (path === "/api/websites/website-programmer-ie/evaluations/wpe-2/reviews")
        return json([{ id: "r1", evaluation_id: "wpe-2", finding_id: "f1", decision: "accept", reason: "Good", reviewer: "author", source_digest: "d", created_at: "2026-01-02T00:00:00Z" }]);
      return apiError(404, `Unhandled ${path}`);
    });
    const user = userEvent.setup();
    renderRoute(<CollectionTab site={site} />, "/websites");
    await screen.findByText("Beta");
    await user.click(screen.getAllByRole("button", { name: "Show evidence" })[0]);
    expect(await screen.findByText(/Human review: 1 recorded/)).toBeInTheDocument();
  });

  it("opens the full post detail and navigates back", async () => {
    mockCollection(collectionFixture(), ({ path }) => {
      if (path === "/api/websites/website-programmer-ie/posts/beta.md")
        return json({
          post: {
            website_id: "website-programmer-ie",
            identity: "beta.md",
            title: "Beta",
            relpath: "beta.md",
            date: "2024-03-11T10:00:00+00:00",
            post_status: "published",
            word_count: 100,
            evaluation: { evaluation_id: null, overall: null, status: null, freshness: "never", evaluated_at: null, stale: false, rubric_id: null, rubric_version: null },
          },
          content: "# Beta\n\nBody.",
          content_truncated: false,
          content_sha256: "b".repeat(64),
          evaluations: [],
          current: null,
        });
      return undefined;
    });
    const user = userEvent.setup();
    renderRoute(<CollectionTab site={site} />, "/websites");
    await screen.findByText("Beta");
    await user.click(screen.getAllByRole("button", { name: "Show evidence" })[0]);
    await user.click(screen.getAllByRole("button", { name: "Open full post" })[0]);
    expect(await screen.findByRole("heading", { name: "Beta" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to collection" }));
    expect(await screen.findByText("Collection quality")).toBeInTheDocument();
  });

  it("shows loading and error states", async () => {
    mockFetch(({ path }) => {
      if (path === "/api/websites/website-programmer-ie/collection/quality") return apiError(500, "boom");
      return apiError(404, `Unhandled ${path}`);
    });
    renderRoute(<CollectionTab site={site} />, "/websites");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows an empty state when the blog section is missing", async () => {
    renderRoute(<CollectionTab site={{ ...site, content_section: null }} />, "/websites");
    expect(await screen.findByText("No blog section")).toBeInTheDocument();
  });
});
