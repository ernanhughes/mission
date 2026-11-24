-- LIVING-WORK-BLOG-01 D5: append-only deterministic Writer observation history.
--
-- One row per observation of a post's body. History is append-only:
-- staleness is derived at read time (body_sha256 vs the live evaluated
-- body), never by overwriting. A rename creates a new identity with no
-- transferred history. Editorial evaluations live in
-- website_post_evaluations (rubric-scoped readers there are rubric-blind in
-- places), so Writer evidence gets its own table and can never masquerade
-- as an editorial verdict.
CREATE TABLE IF NOT EXISTS website_post_writer_observations (
    id TEXT PRIMARY KEY,
    website_id TEXT NOT NULL,
    article_identity TEXT NOT NULL,
    relpath TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    producer_runtime TEXT NOT NULL DEFAULT 'artifact',
    method TEXT NOT NULL DEFAULT 'analyze_text',
    method_version TEXT NOT NULL DEFAULT 'writer-artifact-detection.v1',
    status TEXT NOT NULL DEFAULT 'complete',
    evaluation_id TEXT NOT NULL,
    envelope TEXT NOT NULL DEFAULT '{}',
    finding_count INTEGER NOT NULL DEFAULT 0,
    execution_id TEXT,
    policy_version TEXT NOT NULL DEFAULT 'blog-auto-v1',
    flags_version TEXT NOT NULL DEFAULT 'writer-artifact-detection.v1',
    fingerprint TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blog_writer_obs_site_article
    ON website_post_writer_observations (website_id, article_identity, created_at);
CREATE INDEX IF NOT EXISTS idx_blog_writer_obs_body
    ON website_post_writer_observations (website_id, article_identity, body_sha256);
