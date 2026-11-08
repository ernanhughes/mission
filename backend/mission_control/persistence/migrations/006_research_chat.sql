-- Contextual research conversations associated with a single Next opportunity.
-- These tables are owned by Mission Control.  They do not modify Next's
-- database, and a conversation is not a human decision or verified finding.

CREATE TABLE research_chat_sessions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    record_id TEXT,
    opportunity_title TEXT NOT NULL,
    context_schema TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    context_snapshot JSON NOT NULL,
    context_observed_at TEXT,
    model_route TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_local INTEGER NOT NULL DEFAULT 1,
    provider TEXT NOT NULL DEFAULT 'openai-compatible',
    endpoint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_research_chat_sessions_resource
    ON research_chat_sessions (application_id, resource_type, external_id, updated_at);

CREATE TABLE research_chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES research_chat_sessions(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed')),
    error TEXT,
    provider TEXT,
    model TEXT,
    route TEXT,
    request_key TEXT,
    metadata JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (session_id, sequence),
    UNIQUE (session_id, request_key)
);

CREATE INDEX idx_research_chat_messages_session
    ON research_chat_messages (session_id, sequence);
