-- Council Hub Database Schema
-- SQLite3 compatible

-- Sessions table: one per ChatGPT thread or standalone session
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    repo_root TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_count INTEGER DEFAULT 0
);

-- Events table: append-only event log
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL CHECK(source IN (
        'user', 'chatgpt', 'opencode', 'claude_code', 'wrapper'
    )),
    type TEXT NOT NULL CHECK(type IN (
        'message', 'task_brief', 'question', 'patch', 'tool_run',
        'test_result', 'run_report', 'decision', 'milestone'
    )),
    body TEXT NOT NULL,
    meta_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_session_event_id ON events(session_id, event_id);

-- Artifacts table: metadata for stored artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN (
        'patch', 'test_log', 'command_output', 'repo_map', 'run_log'
    )),
    path TEXT NOT NULL,
    byte_size INTEGER,
    sha256 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_artifacts_session_id ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);



-- Pairing codes table: for session-cli binding
CREATE TABLE IF NOT EXISTS pairing_codes (
    code TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    repo_root TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    claimed_at TIMESTAMP,
    claimed_by TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pairing_codes_session ON pairing_codes(session_id);
CREATE INDEX IF NOT EXISTS idx_pairing_codes_expires ON pairing_codes(expires_at);
