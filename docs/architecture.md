# Council Hub Architecture

> Phase 1 MVP - FastAPI server with SQLite backend

## Overview

Council Hub is a local FastAPI server that serves as the canonical per-thread session store. It provides event logging, artifact storage, and digest generation for the Council system.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Council Hub                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   FastAPI   │  │   SQLite    │  │   File System       │  │
│  │   Router    │──│   Database  │  │   (~/.council/)     │  │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘  │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │              Core Modules                            │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │    │
│  │  │  Ingest  │  │  Digest  │  │  Artifact Store  │   │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  CLI / curl     │
                    │  (clients)      │
                    └─────────────────┘
```

---

## Component Breakdown

### 1. FastAPI Application (`main.py`)

Entry point that mounts all routers and configures the application.

**Responsibilities:**
- Application bootstrap
- Router mounting
- Exception handlers
- Middleware (CORS, logging)

### 2. Database Layer (`db/`)

#### Schema (`schema.sql`)

SQLite schema with three main tables:

**sessions:**
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    repo_root TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_count INTEGER DEFAULT 0
);
```

**events:**
```sql
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,  -- user, chatgpt, opencode, claude_code, wrapper
    type TEXT NOT NULL,    -- message, task_brief, patch, test_result, etc.
    body TEXT NOT NULL,    -- summary text
    meta_json TEXT,        -- JSON metadata
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE INDEX idx_events_session_id ON events(session_id);
CREATE INDEX idx_events_session_ts ON events(session_id, ts);
```

**artifacts:**
```sql
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,    -- patch, test_log, command_output, repo_map, run_log
    path TEXT NOT NULL,    -- filesystem path
    byte_size INTEGER,
    sha256 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE INDEX idx_artifacts_session_id ON artifacts(session_id);
```

#### Repository (`repo.py`)

CRUD operations for all tables:

- `SessionRepo`: create, get, update, list sessions
- `EventRepo`: append, list (cursor-based), count
- `ArtifactRepo`: create, get, list by session

### 3. Core Modules (`core/`)

#### Ingest (`ingest.py`)

Handles event ingestion and artifact storage:

```python
class IngestService:
    def ingest_event(session_id: str, source: str, type: str, 
                     body: str, meta: dict) -> int: ...
    
    def ingest_artifact(session_id: str, kind: str, 
                        content: bytes) -> str: ...
```

**Key behaviors:**
- Auto-creates session if doesn't exist
- Updates session `updated_at` and `event_count`
- Returns `event_id` for cursor tracking
- Stores artifact content to filesystem

#### Digest (`digest.py`)

Generates bounded digests for ChatGPT consumption:

```python
class DigestService:
    def generate_digest(session_id: str, 
                       after: int = 0) -> DigestResult: ...
```

**Key behaviors:**
- Enforces DIGEST_MAX_CHARS budget
- Processes events in chronological order
- Extracts milestones separately
- Truncates patch/log content per budgets
- Returns `next_cursor` for pagination

### 4. Storage (`storage/`)

#### Artifacts (`artifacts.py`)

Filesystem storage for large content:

```python
class ArtifactStore:
    def store(session_id: str, artifact_id: str, 
              content: bytes) -> Path: ...
    
    def retrieve(session_id: str, 
                 artifact_id: str) -> bytes: ...
    
    def delete(session_id: str, 
               artifact_id: str) -> bool: ...
```

**Storage layout:**
```
~/.council/
├── artifacts/
│   └── cgpt:thread_abc123/
│       ├── art_001.bin
│       ├── art_002.bin
│       └── ...
└── council.db
```

### 5. Utils (`utils/`)

#### Text (`text.py`)

Text processing utilities:

```python
def truncate_lines(text: str, max_lines: int, 
                   tail_lines: int = None) -> str: ...

def extract_error_windows(text: str, keywords: list[str],
                         window_size: int) -> list[str]: ...

def truncate_to_budget(parts: list[str], 
                       max_chars: int) -> str: ...

def parse_diff_summary(diff_text: str) -> DiffSummary: ...
```

---

## API Endpoints (Phase 1)

### Base URL

```
http://localhost:8000/v1
```

### Sessions

#### Create Session
```
POST /sessions
```
**Request:**
```json
{
  "session_id": "cgpt:thread_abc123",
  "repo_root": "/home/user/project",
  "title": "Optional title"
}
```
**Response:**
```json
{
  "session_id": "cgpt:thread_abc123",
  "repo_root": "/home/user/project",
  "title": "Optional title",
  "created_at": "2026-03-04T12:00:00Z",
  "updated_at": "2026-03-04T12:00:00Z",
  "event_count": 0
}
```

#### Get Session
```
GET /sessions/{session_id}
```

#### List Sessions
```
GET /sessions?limit=20&offset=0
```

### Events

#### Ingest Event
```
POST /sessions/{session_id}/events
```
**Request:**
```json
{
  "source": "wrapper",
  "type": "patch",
  "body": "Modified src/auth.py: +45/-12 lines",
  "meta": {
    "files_changed": ["src/auth.py"],
    "lines_added": 45,
    "lines_removed": 12,
    "artifact_id": "art_123"
  }
}
```
**Response:**
```json
{
  "event_id": 42,
  "session_id": "cgpt:thread_abc123",
  "ts": "2026-03-04T12:00:00Z"
}
```

#### List Events (Cursor-based)
```
GET /sessions/{session_id}/events?after=0&limit=50
```
**Response:**
```json
{
  "events": [...],
  "next_cursor": 42,
  "has_more": true
}
```

### Digest

#### Get Digest
```
GET /sessions/{session_id}/digest?after=0
```
**Response:**
```json
{
  "digest_text": "## Summary\n...",
  "milestones": [
    {"event_id": 10, "subtype": "executor_started", "ts": "..."}
  ],
  "next_cursor": 42,
  "has_more": true
}
```

### Context Pack

#### Get Context Pack
```
GET /sessions/{session_id}/context
```
**Response:**
```json
{
  "session_id": "cgpt:thread_abc123",
  "pinned_decisions": [...],
  "current_task": {...},
  "last_patch": {...},
  "last_test_status": {...},
  "recent_digest": "..."
}
```

### Artifacts

#### Get Artifact
```
GET /sessions/{session_id}/artifacts/{artifact_id}
```
**Response:** Raw bytes (Content-Type varies by kind)

---

## Data Flow

### Event Ingestion Flow

```
1. Client POST /sessions/{id}/events
        ↓
2. IngestService.ingest_event()
   - Validate event type
   - Create session if needed
   - Insert event (event_id = AUTOINCREMENT)
   - Update session stats
        ↓
3. Response with event_id
```

### Artifact Storage Flow

```
1. Client POST artifact content (via event meta)
        ↓
2. IngestService.ingest_artifact()
   - Generate artifact_id (uuid)
   - Compute sha256
   - Write to ~/.council/artifacts/<session>/<id>.bin
   - Insert artifact record
        ↓
3. Return artifact_id for event meta
```

### Digest Generation Flow

```
1. Client GET /sessions/{id}/digest?after=N
        ↓
2. DigestService.generate_digest()
   - Fetch events after cursor (limit 100)
   - For each event:
     * If milestone: add to milestones list
     * Format based on type:
       - patch: file list + truncated hunks
       - test_result: counts + error windows
       - message/task: body text
   - Apply budgets (chars, lines, hunks)
   - Truncate if over budget
        ↓
3. Return digest with next_cursor
```

---

## Configuration

Environment variables (with defaults):

```bash
COUNCIL_DATA_DIR=~/.council
COUNCIL_DB_PATH=~/.council/council.db
COUNCIL_PORT=8000
COUNCIL_HOST=127.0.0.1

# Budgets
DIGEST_MAX_CHARS=12000
DIGEST_MAX_EVENTS=100
PATCH_MAX_HUNKS_PER_FILE=3
PATCH_MAX_LINES_PER_HUNK=20
LOG_MAX_LINES=200
LOG_TAIL_LINES=50
```

---

## Error Handling

All errors return JSON with consistent structure:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {}  // Optional additional context
}
```

HTTP Status Codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `413` - Payload Too Large
- `500` - Internal Server Error

---

## Phase 1 Scope

### Included
- SQLite database with schema
- CRUD for sessions/events/artifacts
- Deterministic digest generation
- File-based artifact storage
- Cursor-based event pagination
- Context pack endpoint

### Excluded (Future Phases)
- SSE/streaming (Phase 4)
- Pairing service (Phase 5)
- LLM summarization (Phase 2+)
- Extension integration (Phase 3)
- Authentication/authorization
- Database migrations
- Compression

---

## Testing Strategy

Unit tests cover:
- `test_events.py`: Event CRUD, cursor pagination
- `test_digest.py`: Budget enforcement, truncation logic

Integration tests (manual):
- Start server
- Create session via curl
- Ingest events
- Retrieve digest

---

## Directory Structure

```
packages/hub/
├── pyproject.toml
├── src/
│   └── council_hub/
│       ├── __init__.py
│       ├── main.py           # FastAPI entry point
│       ├── config.py         # Settings
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.sql    # SQLite DDL
│       │   └── repo.py       # CRUD operations
│       ├── core/
│       │   ├── __init__.py
│       │   ├── ingest.py     # Event/artifact ingestion
│       │   └── digest.py     # Digest generation
│       ├── storage/
│       │   ├── __init__.py
│       │   └── artifacts.py  # Filesystem storage
│       └── utils/
│           ├── __init__.py
│           └── text.py       # Text utilities
└── tests/
    ├── test_events.py
    └── test_digest.py
```

---

## Dependencies

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pytest>=7.4.0
httpx>=0.25.0  # for test client
```

---

## Running Locally

```bash
# Install
cd packages/hub
pip install -e ".[dev]"

# Run server
python -m council_hub.main

# Or with uvicorn directly
uvicorn council_hub.main:app --reload --port 8000
```
