-- MC-WEBSITES-POSTS-01: blog-post editorial evaluation history, website-scoped.
-- One row per evaluation observation; history is append-only. Staleness is
-- derived at read time (content_sha256 vs the live file hash), never by
-- overwriting. Blocked/error outcomes carry no scores (overall NULL).
CREATE TABLE IF NOT EXISTS website_post_evaluations (
    id TEXT PRIMARY KEY,
    website_id TEXT NOT NULL,
    article_identity TEXT NOT NULL,
    relpath TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    rubric_id TEXT NOT NULL DEFAULT 'blog-editorial-v1',
    rubric_version INTEGER NOT NULL DEFAULT 1,
    prompt_version TEXT NOT NULL DEFAULT '1',
    requested_model TEXT,
    actual_model TEXT,
    status TEXT NOT NULL DEFAULT 'CURRENT',
    overall REAL,
    aggregation_method TEXT NOT NULL DEFAULT 'sum_dimensions_v1',
    dimensions TEXT NOT NULL DEFAULT '{}',
    assessment TEXT NOT NULL DEFAULT '',
    strengths TEXT NOT NULL DEFAULT '[]',
    weaknesses TEXT NOT NULL DEFAULT '[]',
    improvements TEXT NOT NULL DEFAULT '[]',
    findings TEXT NOT NULL DEFAULT '[]',
    uncertainty TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '[]',
    execution TEXT NOT NULL DEFAULT '{}',
    previous_evaluation_id TEXT REFERENCES website_post_evaluations(id) ON DELETE SET NULL,
    supersedes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_website_post_evals_site_article
    ON website_post_evaluations (website_id, article_identity, created_at);
CREATE INDEX IF NOT EXISTS idx_website_post_evals_revision
    ON website_post_evaluations (website_id, article_identity, content_sha256);
CREATE TABLE IF NOT EXISTS website_post_reviews (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT REFERENCES website_post_evaluations(id) ON DELETE CASCADE,
    finding_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    source_digest TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_website_post_reviews_eval
    ON website_post_reviews (evaluation_id, finding_id);
