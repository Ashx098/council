# Council Protocol Specification

API specification for the Council Hub.

**Base URL**: `http://127.0.0.1:7337`

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/sessions/{id}/events` | Ingest events |
| GET | `/v1/sessions/{id}/events` | List events |
| GET | `/v1/sessions/{id}/digest` | Get bounded digest |
| GET | `/v1/sessions/{id}/stream` | SSE stream |
| GET | `/v1/sessions/{id}/context` | Context pack |
| POST | `/v1/pair/create` | Create pairing code |
| POST | `/v1/pair/claim` | Claim pairing code |
| GET | `/v1/pair/{code}` | Get pairing status |
| GET | `/v1/pair/session/{id}` | Get session pairing |

---

## Health

### GET /health

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0-phase5"
}
```

---

## Events

### POST /v1/sessions/{session_id}/events

Ingest one or more events.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | Session identifier (e.g., `cgpt:abc123`) |

**Request Body:**

```json
{
  "source": "user",
  "type": "message",
  "body": "Please refactor the auth module",
  "meta": {}
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source | string | Yes | Event source (see Sources) |
| type | string | Yes | Event type (see Types) |
| body | string | No | Event content (max 4000 chars) |
| meta | object | No | Additional metadata |

**Response:**

```json
{
  "event_id": 42,
  "session_id": "cgpt:abc123",
  "ts": "2024-01-15T10:30:00Z"
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 201 | Event created |
| 400 | Invalid source/type |
| 503 | Service not initialized |

### GET /v1/sessions/{session_id}/events

List events for a session.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| after | int | 0 | Only events with id > after |
| limit | int | 100 | Max events to return |

**Response:**

```json
{
  "events": [
    {
      "event_id": 1,
      "session_id": "cgpt:abc123",
      "ts": "2024-01-15T10:30:00Z",
      "source": "user",
      "type": "message",
      "body": "Hello",
      "meta": {}
    }
  ],
  "next_cursor": 1,
  "has_more": false
}
```

---

## Digest

### GET /v1/sessions/{session_id}/digest

Get a bounded digest of session events.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| after | int | 0 | Only events with id > after |

**Response:**

```json
{
  "session_id": "cgpt:abc123",
  "digest_text": "# Council Digest\n\n## Events (3)\n\n...",
  "event_count": 3,
  "next_cursor": 42,
  "truncated": false
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| digest_text | string | Formatted digest (max 12,000 chars) |
| event_count | int | Number of events included |
| next_cursor | int | Cursor for next fetch |
| truncated | bool | Whether digest was truncated |

---

## SSE Stream

### GET /v1/sessions/{session_id}/stream

Server-Sent Events stream for real-time updates.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| after | int | Only events with id > after |

**Headers:**

| Header | Description |
|--------|-------------|
| Accept | Should be `text/event-stream` |
| Last-Event-ID | Reconnect cursor (alternative to `after`) |

**Response Format:**

```
Content-Type: text/event-stream

event: hello
data: {"type":"connected","after":0}

event: council_event
id: 42
data: {"event_id":42,"ts":"...","source":"wrapper","type":"run_report","body_preview":"...","meta":{}}

event: council_event
id: 43
data: {"event_id":43,...}

: keepalive
```

**Event Types:**

| Event | Description |
|-------|-------------|
| hello | Sent on connection |
| council_event | New event ingested |
| keepalive | Empty comment (every 15s) |

**SSE Event Fields:**

| Field | Description |
|-------|-------------|
| id | Event ID (for reconnect) |
| event | Event type |
| data | JSON payload |

**Payload Structure:**

```json
{
  "event_id": 42,
  "ts": "2024-01-15T10:30:00Z",
  "source": "wrapper",
  "type": "run_report",
  "body_preview": "First 200 chars of body...",
  "meta": {
    "exit_code": 0,
    "duration_ms": 1500
  }
}
```

---

## Context Pack

### GET /v1/sessions/{session_id}/context

Get a context pack for AI consumption.

**Response:**

```json
{
  "session_id": "cgpt:abc123",
  "repo_root": "/home/user/project",
  "event_count": 15,
  "latest_events": [...],
  "artifacts": [
    {
      "artifact_id": "art_001",
      "kind": "patch",
      "byte_size": 2048
    }
  ]
}
```

---

## Pairing

### POST /v1/pair/create

Create a new pairing code.

**Request Body:**

```json
{
  "session_id": "cgpt:abc123",
  "ttl_minutes": 10
}
```

**Response:**

```json
{
  "code": "AB7K",
  "session_id": "cgpt:abc123",
  "repo_root": null,
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T10:40:00Z",
  "claimed_at": null,
  "claimed_by": null
}
```

### POST /v1/pair/claim

Claim a pairing code.

**Request Body:**

```json
{
  "code": "AB7K",
  "claimed_by": "my-laptop",
  "repo_root": "/home/user/project"
}
```

**Response:**

```json
{
  "code": "AB7K",
  "session_id": "cgpt:abc123",
  "repo_root": "/home/user/project",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T10:40:00Z",
  "claimed_at": "2024-01-15T10:35:00Z",
  "claimed_by": "my-laptop"
}
```

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Invalid or expired pairing code | Code not found or expired |
| 400 | Pairing code already claimed | Code was claimed by another |

### GET /v1/pair/{code}

Get pairing code status.

**Response:** Same as POST /v1/pair/create response.

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | pairing_not_found | Code doesn't exist or expired |

### GET /v1/pair/session/{session_id}

Get active pairing for a session.

**Response:** Same as POST /v1/pair/create response.

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | no_active_pairing | No unclaimed code for session |

---

## Event Sources

| Source | Description |
|--------|-------------|
| `user` | Direct user input |
| `chatgpt` | From ChatGPT |
| `opencode` | From OpenCode agent |
| `claude_code` | From Claude Code agent |
| `wrapper` | From CLI wrapper |

---

## Event Types

| Type | Description | Meta Fields |
|------|-------------|-------------|
| `message` | Chat message | - |
| `task_brief` | Task description | `priority`, `deadline` |
| `question` | Open question | `context` |
| `patch` | Code change | `files_changed`, `lines_added`, `lines_removed` |
| `tool_run` | Tool execution | `tool_name`, `exit_code` |
| `test_result` | Test output | `exit_code`, `test_count`, `pass_count`, `fail_count` |
| `run_report` | Execution summary | `exit_code`, `duration_ms`, `files_touched` |
| `decision` | Pinned decision | `approved`, `rationale` |
| `milestone` | Checkpoint | `kind` |

---

## Artifact Kinds

| Kind | Description |
|------|-------------|
| `patch` | Git diff |
| `test_log` | Test output |
| `command_output` | CLI output |
| `repo_map` | Repository structure |
| `run_log` | Execution log |

---

## Size Budgets

| Budget | Value |
|--------|-------|
| Digest max chars | 12,000 |
| Event body max chars | 4,000 |
| Patch hunks per file | 3 |
| Lines per hunk | 20 |
| Log max lines | 200 |
| SSE body preview | 200 |
| Pairing code TTL | 10 minutes (default) |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

Or for structured errors:

```json
{
  "detail": {
    "error": "error_code",
    "message": "Human readable message"
  }
}
```

---

## CORS

The hub includes CORS middleware allowing:

- Origins: `*` (all origins for local development)
- Methods: `GET, POST, OPTIONS`
- Headers: `Content-Type, Authorization`

---

## Rate Limiting

No rate limiting is enforced. The hub is designed for single-user local development.

---

## Versioning

The API version is returned in the health endpoint:

```json
{
  "status": "healthy",
  "version": "1.0.0-phase5"
}
```

Version format: `MAJOR.MINOR.PATCH-phase`

---

## Examples

### Ingest a Message

```bash
curl -X POST http://127.0.0.1:7337/v1/sessions/cgpt:abc123/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "user",
    "type": "message",
    "body": "Please refactor the auth module to use the adapter pattern"
  }'
```

### Get Digest

```bash
curl http://127.0.0.1:7337/v1/sessions/cgpt:abc123/digest?after=0
```

### Connect to SSE Stream

```bash
curl -N http://127.0.0.1:7337/v1/sessions/cgpt:abc123/stream?after=0
```

### Create Pairing Code

```bash
curl -X POST http://127.0.0.1:7337/v1/pair/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "cgpt:abc123",
    "ttl_minutes": 10
  }'
```

### Claim Pairing Code

```bash
curl -X POST http://127.0.0.1:7337/v1/pair/claim \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AB7K",
    "claimed_by": "my-laptop",
    "repo_root": "/home/user/project"
  }'
```
