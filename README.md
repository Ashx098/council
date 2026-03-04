# Council

Council is a local session store and digest service that bridges ChatGPT conversations with AI coding agents. It solves context bloat by providing bounded digests and canonical per-thread session storage.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Council Hub                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   FastAPI   │  │   SQLite    │  │   File System       │  │
│  │   Server    │  │   Database  │  │   (~/.council/)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   ChatGPT    │      │  CLI Wrapper │      │  Extension   │
│   (Browser)  │◄────►│  (Agent)     │◄────►│  (Chrome)    │
└──────────────┘      └──────────────┘      └──────────────┘
```

## Phase 1: Hub MVP

This repository contains the Phase 1 implementation of Council Hub - a FastAPI server with:

- **Session Management**: Create and manage per-thread sessions
- **Event Ingestion**: Append-only event log with cursor-based pagination
- **Artifact Storage**: Large content (diffs, logs) stored on filesystem
- **Digest Generation**: Bounded, deterministic summaries for ChatGPT context
- **Context Pack**: Briefing pack for executor initialization

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
cd packages/hub
pip install -e ".[dev]"
```

### Running the Server

```bash
# Run with uvicorn directly
uvicorn council_hub.main:app --reload --port 8000

# Or use the module
python -m council_hub.main
```

The server will start on `http://localhost:8000`.

### Environment Variables

```bash
# Optional: Custom data directory (default: ~/.council)
export COUNCIL_DATA_DIR=/path/to/data

# Optional: Custom port (default: 8000)
export COUNCIL_PORT=8080
```

## API Usage

### Create a Session

```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "cgpt:thread_abc123",
    "repo_root": "/home/user/myproject",
    "title": "Auth refactor"
  }'
```

### Ingest an Event

```bash
curl -X POST http://localhost:8000/v1/sessions/cgpt:thread_abc123/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wrapper",
    "type": "patch",
    "body": "Modified src/auth.py: +45/-12 lines",
    "meta": {
      "files_changed": ["src/auth.py"],
      "lines_added": 45,
      "lines_removed": 12
    }
  }'
```

### Get Digest

```bash
# Get full digest
curl http://localhost:8000/v1/sessions/cgpt:thread_abc123/digest

# Get digest after cursor
curl "http://localhost:8000/v1/sessions/cgpt:thread_abc123/digest?after=10"
```

### Get Context Pack

```bash
curl http://localhost:8000/v1/sessions/cgpt:thread_abc123/context
```

### List Events

```bash
# First page
curl "http://localhost:8000/v1/sessions/cgpt:thread_abc123/events?limit=50"

# Next page (using last event_id as cursor)
curl "http://localhost:8000/v1/sessions/cgpt:thread_abc123/events?after=50&limit=50"
```

## Running Tests

```bash
cd packages/hub
pytest

# With verbose output
pytest -v

# Specific test file
pytest tests/test_events.py
pytest tests/test_digest.py
```

## Data Storage

Council stores data in `~/.council/` (or `$COUNCIL_DATA_DIR`):

```
~/.council/
├── council.db           # SQLite database
└── artifacts/
    └── cgpt_thread_abc123/     # Session directory
        ├── art_001.bin         # Artifact files
        └── art_002.bin
```

## Event Types

| Type | Description |
|------|-------------|
| `message` | Chat message |
| `task_brief` | Task description |
| `question` | Open question |
| `patch` | Code change |
| `tool_run` | Tool execution |
| `test_result` | Test results |
| `run_report` | Execution summary |
| `decision` | Pinned decision |
| `milestone` | Checkpoint event |

## Size Budgets

Digest generation enforces hard limits:

- **Digest**: 12,000 characters max
- **Patch hunks**: 3 per file, 20 lines per hunk
- **Logs**: 200 lines total, 50 tail lines + error windows

See `docs/protocol.md` for full specification.

## Project Structure

```
packages/hub/
├── pyproject.toml
├── src/
│   └── council_hub/
│       ├── main.py           # FastAPI app
│       ├── config.py         # Settings
│       ├── db/
│       │   ├── schema.sql    # SQLite schema
│       │   └── repo.py       # CRUD operations
│       ├── core/
│       │   ├── ingest.py     # Event/artifact ingestion
│       │   └── digest.py     # Digest generation
│       ├── storage/
│       │   └── artifacts.py  # Filesystem storage
│       └── utils/
│           └── text.py       # Text utilities
└── tests/
    ├── test_events.py
    └── test_digest.py
```

## Documentation

- `docs/protocol.md` - Event types, artifact kinds, budgets, API contracts
- `docs/architecture.md` - System design, data flow, component breakdown

## Roadmap

- **Phase 2**: CLI wrapper for agent capture
- **Phase 3**: Chrome extension for ChatGPT integration
- **Phase 4**: SSE streaming + milestones
- **Phase 5**: Pairing service (thread ↔ session binding)

## License

MIT
