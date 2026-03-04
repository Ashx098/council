# Council Protocol Specification

> Phase 1 MVP - Minimal but correct implementation

## Overview

This document defines the event types, artifact kinds, size budgets, and API contracts for the Council Hub. All specifications are designed for Phase 1 implementation with minimal scope.

---

## Event Types

Events are append-only records stored per session. Each event has a monotonic `event_id` (AUTOINCREMENT) for cursor-based pagination.

### Event Type Enum

| Type | Description | Source |
|------|-------------|--------|
| `message` | Chat message from user or ChatGPT | user, chatgpt |
| `task_brief` | Task description/assignment | chatgpt |
| `question` | Open question requiring response | chatgpt, wrapper |
| `patch` | Code change summary with artifact reference | wrapper |
| `tool_run` | Tool execution (linter, formatter, etc.) | wrapper |
| `test_result` | Test run output with pass/fail status | wrapper |
| `run_report` | Final summary after executor completes | wrapper |
| `decision` | Pinned decision or constraint | chatgpt, user |
| `milestone` | Significant checkpoint event | wrapper, chatgpt |

### Milestone Event Subtypes

Milestone events indicate significant state changes:

| Subtype | Trigger |
|---------|---------|
| `executor_started` | Wrapper begins execution |
| `executor_finished` | Wrapper completes successfully |
| `executor_failed` | Wrapper exits with error |
| `tests_passing` | All tests pass |
| `tests_failing` | One or more tests fail |
| `patch_applied` | Code changes committed/pushed |
| `question_asked` | Human input required |

---

## Artifact Kinds

Artifacts store large content on disk. Raw content is never inlined in events.

### Artifact Kind Enum

| Kind | Content Type | Max Size |
|------|--------------|----------|
| `patch` | Git diff output | 10 MB |
| `test_log` | Test command output | 5 MB |
| `command_output` | Generic command output | 5 MB |
| `repo_map` | Repository structure snapshot | 1 MB |
| `run_log` | Full execution transcript | 10 MB |

### Artifact Storage

- Location: `~/.council/artifacts/<session_id>/<artifact_id>.bin`
- Metadata stored in `artifacts` table (size, sha256, kind)
- Content is stored raw (no compression in Phase 1)

---

## Size Budgets

Hard limits to prevent context bloat. Digest generation must enforce these bounds.

### Digest Budgets

| Budget | Limit | Description |
|--------|-------|-------------|
| `DIGEST_MAX_CHARS` | 12,000 | Maximum characters in digest text |
| `DIGEST_MAX_EVENTS` | 100 | Maximum events processed per digest request |

### Patch Budgets

| Budget | Limit | Description |
|--------|-------|-------------|
| `PATCH_MAX_HUNKS_PER_FILE` | 3 | Number of diff hunks to include per file |
| `PATCH_MAX_LINES_PER_HUNK` | 20 | Lines per hunk in digest |
| `PATCH_MAX_FILES_IN_DIGEST` | 10 | File summaries in patch digest |

### Log Budgets

| Budget | Limit | Description |
|--------|-------|-------------|
| `LOG_MAX_LINES` | 200 | Total lines from log in digest |
| `LOG_TAIL_LINES` | 50 | Lines from end of log |
| `LOG_ERROR_WINDOW` | 10 | Lines around each error keyword |

### Error Keywords

Logs are scanned for these keywords to extract error context:

```python
ERROR_KEYWORDS = [
    "Error:",
    "ERROR",
    "Traceback",
    "FAILED",
    "FAIL:",
    "panic:",
    "panic(",
    "Exception",
    "SyntaxError",
    "TypeError",
    "ValueError",
    "AssertionError",
]
```

---

## Event Schema

### Event Object

```json
{
  "event_id": 42,
  "session_id": "cgpt:thread_abc123",
  "ts": "2026-03-04T12:00:00Z",
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

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | integer | auto | Monotonic cursor (AUTOINCREMENT) |
| `session_id` | string | yes | Format: `cgpt:<thread_id>` or `session:<uuid>` |
| `ts` | ISO8601 | auto | Server timestamp |
| `source` | enum | yes | `user`, `chatgpt`, `opencode`, `claude_code`, `wrapper` |
| `type` | enum | yes | Event type from table above |
| `body` | string(4000) | yes | Summary text (truncated to fit) |
| `meta` | JSON | no | Structured metadata (varies by type) |

### Meta Schema by Type

**patch:**
```json
{
  "files_changed": ["src/auth.py"],
  "lines_added": 45,
  "lines_removed": 12,
  "artifact_id": "art_123",
  "commit_hash": "abc123"  // optional
}
```

**test_result:**
```json
{
  "command": "pytest tests/",
  "exit_code": 1,
  "passed": 42,
  "failed": 3,
  "skipped": 1,
  "artifact_id": "art_124"
}
```

**tool_run:**
```json
{
  "command": "ruff check src/",
  "exit_code": 0,
  "duration_ms": 1500,
  "artifact_id": "art_125"  // optional
}
```

**run_report:**
```json
{
  "status": "success",  // or "failure", "partial"
  "summary": "Fixed auth bug and added tests",
  "questions": ["Should I refactor the user model?"],
  "patches": ["art_123"],
  "tests": ["art_124"]
}
```

---

## Digest Format

The digest is a bounded, human-readable summary safe for ChatGPT context.

### Digest Response

```json
{
  "digest_text": "[bounded text per budgets]",
  "milestones": [
    {"event_id": 10, "subtype": "executor_started", "ts": "..."},
    {"event_id": 25, "subtype": "tests_failing", "ts": "..."}
  ],
  "next_cursor": 42,
  "has_more": true
}
```

### Digest Text Structure

```
## Summary
[Last run_report or milestone summary]

## Changes
[Patch summaries - file list + line counts + top hunks]

## Tests
[Test results - pass/fail counts + error excerpts]

## Open Questions
[List of unanswered question events]
```

### Digest Generation Rules

1. **Always bounded**: Never exceed DIGEST_MAX_CHARS
2. **Deterministic**: Same events produce same digest (no LLM in Phase 1)
3. **Truncation priority**: Keep recent events, truncate older ones
4. **Artifact references**: Include `artifact_id` for full content access

---

## Session Schema

### Session Object

```json
{
  "session_id": "cgpt:thread_abc123",
  "repo_root": "/home/user/myproject",
  "title": "Auth system refactor",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T12:00:00Z",
  "event_count": 42
}
```

### Session ID Format

| Prefix | Format | Example |
|--------|--------|---------|
| `cgpt:` | ChatGPT thread ID | `cgpt:thread_abc123` |
| `session:` | UUID for non-ChatGPT sessions | `session:550e8400-e29b-41d4-a716-446655440000` |

---

## API Contracts

### Error Responses

All errors return JSON with `error` field:

```json
{
  "error": "session_not_found",
  "message": "Session cgpt:thread_abc123 does not exist"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `session_not_found` | 404 | Session does not exist |
| `invalid_cursor` | 400 | Cursor parameter invalid |
| `invalid_event_type` | 400 | Unknown event type |
| `artifact_not_found` | 404 | Artifact does not exist |
| `payload_too_large` | 413 | Request body exceeds limit |
| `internal_error` | 500 | Unexpected server error |

---

## Phase 1 Limitations

Explicitly out of scope for Phase 1:

- **LLM summarization**: Digest uses deterministic truncation only
- **Compression**: Artifacts stored raw
- **Authentication**: No auth layer (local-only)
- **Migration system**: SQLite schema created fresh
- **SSE/streaming**: Polling only (streaming in Phase 4)
- **Pairing system**: Manual session_id entry (pairing in Phase 5)
- **Extension**: CLI and curl only

---

## Version

Protocol Version: `1.0.0-phase1`
