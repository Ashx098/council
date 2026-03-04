Cool. Below is a **detailed build plan + repo layout + architecture** for the “Council per ChatGPT thread” system, with the friction points handled (context bloat, push/poll, pairing).

I’m going to design it so you can ship **Phase 1** quickly and still have a clean path to “auto-run from guidance” later.

---

# Architecture (final shape)

### Components

1. **council-hub** (local server on Kaarya)

* Canonical per-thread session store
* Event log + artifact store
* Digest builder (summarize/truncate)
* SSE stream for realtime updates
* Pairing service to bind ChatGPT thread ↔ session

2. **council-cli** (terminal entrypoint)

* `pair`, `attach`, `snapshot`, `tail`, `ask`, `run`
* Wrapper runner for OpenCode / Claude Code
* Captures diffs/tests/logs → pushes to hub

3. **council-extension** (Chrome extension)

* Detect ChatGPT thread id
* “Sync → Council”, “Pull ← Council”
* SSE listener + milestone notifications
* Pairing code UI

4. **Optional later: council-dashboard**

* Web UI for mobile monitoring (read-only)
* Copy snapshot button

---

# Repo layout (monorepo)

```
council/
  README.md
  docs/
    architecture.md
    protocol.md
    security.md
    runbook.md
  packages/
    hub/
      pyproject.toml
      src/council_hub/
        main.py                  # FastAPI app
        config.py
        db/
          schema.sql
          migrations/            # optional
          models.py              # SQLAlchemy or raw sqlite
          repo.py                # CRUD
        api/
          sessions.py            # /v1/sessions/*
          pairing.py             # /v1/pair/*
          stream.py              # SSE endpoint
          artifacts.py           # artifact fetch
        core/
          ingest.py              # append events + artifact handling
          digest.py              # "views" generation
          summarizer.py          # truncate + optional LLM summarizer
          policies.py            # size budgets, milestone rules
          session_map.py         # cgpt thread id ↔ session id
        storage/
          artifacts.py           # filesystem storage + metadata
        utils/
          redaction.py           # secrets scrubber
          text.py                # truncation helpers
      tests/
        test_digest.py
        test_pairing.py
        test_sse.py

    cli/
      pyproject.toml
      src/council_cli/
        __main__.py
        commands/
          pair.py                # claim pairing code
          attach.py              # run wrapper + attach to session
          snapshot.py            # compact digest output
          tail.py                # last N events
          ask.py                 # fetch digest / artifacts on demand
        wrapper/
          runner.py              # starts agent tool (opencode/claude)
          capture.py             # capture stdout/stderr
          gitwatch.py            # git diff snapshots
          cmdwatch.py            # allowlisted cmd capture
          report.py              # generate run_report event
          safety.py              # allowlist + repo jail + destructive checks
        client/
          hub_client.py          # HTTP client to hub
          sse_client.py          # optional
        config/
          default.yaml           # model/tool settings (optional)
      tests/

    extension/
      manifest.json
      src/
        content_script.js        # inject UI buttons into ChatGPT
        background.js            # SSE connection + storage
        ui/
          panel.html
          panel.js               # pairing display, status, settings
        lib/
          api.js                 # hub calls
          thread_id.js           # extract ChatGPT thread id
          format_digest.js       # render digest into ChatGPT box
          cursor_store.js        # per-session cursor handling
      assets/
        icon.png

    dashboard/                   # optional later
      ...
```

---

# Data model (Hub)

### Sessions

* One session per ChatGPT thread:

  * `session_id = cgpt:<thread_id>`
* Session stores:

  * `repo_root` (optional but recommended)
  * `created_at`
  * `title` (optional)
  * `pinned` decisions/constraints

### Events (append-only)

Table: `events`

* `event_id` (monotonic int or UUID + ts)
* `session_id`
* `ts`
* `source` (user/chatgpt/opencode/claude_code/wrapper)
* `type` (message/task_brief/question/patch/tool_run/test_result/run_report/decision)
* `body` (small text or pointer)
* `meta_json` (files, cmd, exit_code, artifact_ids, etc.)

### Artifacts

Table: `artifacts`

* `artifact_id`
* `session_id`
* `kind` (patch, test_log, repo_map, command_output)
* `path` (file path in artifacts store)
* `byte_size`
* `sha256`
* `created_at`

Artifacts live on disk:

* `~/.council/artifacts/<session_id>/<artifact_id>.txt`

---

# API surface (Hub)

## Pairing

### Create pairing code (extension)

`POST /v1/pair/create`

* input: `{ session_id, thread_meta }`
* output: `{ pairing_code, expires_at }`

### Claim pairing code (CLI)

`POST /v1/pair/claim`

* input: `{ pairing_code, repo_root, agent_kind }`
* output: `{ session_id, repo_root }`

This avoids “thread id drift” and makes it usable on mobile too.

---

## Ingest events

`POST /v1/sessions/{session_id}/events`

* body: `{ source, type, body, meta }`
* returns: `{ event_id }`

## List events (cursor-based)

`GET /v1/sessions/{session_id}/events?after=<event_id>&limit=50`

## Digest (safe for ChatGPT)

`GET /v1/sessions/{session_id}/digest?after=<event_id>`
Returns **only bounded views**:

* `digest_text` (<= token/char budget)
* `milestones` (list)
* `next_cursor`

## Artifacts (raw, on-demand)

`GET /v1/sessions/{session_id}/artifacts/{artifact_id}`

## Context pack (for executor briefing)

`GET /v1/sessions/{session_id}/context`
Returns:

* pinned decisions/constraints
* current task
* last patch summary
* last test status
* recent digest

## SSE stream (push)

`GET /v1/sessions/{session_id}/stream`

* emits events as they arrive
* extension listens to milestone types only

---

# Hub digest/summarizer design (solves log dump problem)

### Policy budgets (hard limits)

* `DIGEST_MAX_CHARS` (ex: 12k)
* `PATCH_SUMMARY_MAX_HUNKS_PER_FILE` (ex: 3)
* `LOG_MAX_LINES` (ex: 200)
* `ERROR_WINDOWS` around keywords (`Traceback`, `ERROR`, `FAILED`, `panic`, etc.)

### Views vs artifacts

* raw diff stored as artifact
* digest includes:

  * file list + +/- line counts
  * top hunks only
* raw test logs stored as artifact
* digest includes:

  * last N lines + error windows
  * “root cause guess” (optional later)

**Result:** ChatGPT sees small, high-signal info.

---

# CLI wrapper design (executor bridge)

## Commands (Phase 1)

### `council pair`

* prints pairing code (if you don’t want extension to create)
* or “claim” code made by extension

### `council attach`

Attaches an agent tool to a session:

* pulls context pack
* generates Supervisor Brief
* runs agent tool
* captures events/artifacts

### `council snapshot`

Prints mobile-friendly digest:

* status + last changes + last tests + open questions

### `council tail`

Show last N events

---

## Wrapper internals (how it captures “proof”)

* **stdout capture**: logs agent messages
* **gitwatch**:

  * periodically runs `git diff` (and optionally `git status`)
  * stores raw diff as artifact
  * pushes `patch` event with summary in `body` and artifact_id in `meta`
* **cmdwatch**:

  * allowlist commands (`pytest`, `npm test`, `go test`, `ruff`, etc.)
  * capture output → artifact + `tool_run`/`test_result` events
* **run_report** on completion:

  * what changed
  * tests run
  * questions

### Safety (non-negotiable)

* repo jail: refuse commands outside repo root
* destructive command guard: `rm`, `git reset --hard` needs manual confirmation
* redact secrets in logs (basic regex scrub)

---

# Extension design (ChatGPT supervisor console)

### UX inside a ChatGPT thread

* Button: **Sync → Council**

  * sends selected text or last message to hub as `message`
* Button: **Pull ← Council**

  * calls `/digest?after=cursor`
  * pastes digest into ChatGPT composer (not auto-send unless you choose)
* Badge/Toast on milestone events via SSE:

  * “Executor finished”
  * “Tests failing”
  * “Question needs approval”

### State

* per session cursor stored in extension storage:

  * `cursor[cgpt:<thread_id>] = last_event_id`

### Pairing flow

* Extension creates pairing code and shows it in a small panel:

  * `PAIR-7H3K`
* You run:

  * `council pair claim PAIR-7H3K --repo ~/repo -- opencode`

---

# Detailed build plan (phased)

## Phase 0 — Spec + protocol (half day)

Deliverables:

* `docs/protocol.md` (event types, artifact kinds, budgets)
* Decide budgets (chars/lines/hunks)
* Define milestone event types

## Phase 1 — Hub MVP (1–2 days)

Deliverables:

* FastAPI server with:

  * sessions/events endpoints
  * artifact store on disk
  * digest builder (deterministic truncator)
  * cursor-based event listing
* SQLite schema + CRUD

Success criteria:

* Can ingest events and pull digest without bloat.

## Phase 2 — CLI MVP (1–2 days)

Deliverables:

* `council snapshot`, `tail`
* `council attach` wrapper:

  * pulls context pack
  * runs agent tool
  * captures stdout
  * captures git diffs + test outputs
  * pushes artifacts + summaries

Success criteria:

* Run OpenCode, see diffs/tests captured in hub.

## Phase 3 — Extension MVP (1–2 days)

Deliverables:

* Content script UI (Sync/Pull buttons)
* Thread ID extraction
* Cursor storage
* Digest formatting pasted into composer

Success criteria:

* ChatGPT thread can Sync/Pull from hub with zero manual copy-paste.

## Phase 4 — Push updates (SSE) + milestones (1 day)

Deliverables:

* SSE endpoint in hub
* Extension listener
* badge/toast notifications
* “auto-draft pull” option on milestone

Success criteria:

* When executor finishes, ChatGPT UI shows it instantly.

## Phase 5 — Pairing (0.5–1 day)

Deliverables:

* `/pair/create` + `/pair/claim`
* extension UI shows pairing code
* CLI claim binds repo_root + session_id

Success criteria:

* No more copying thread ids into terminal ever.

---

# Flow (exact, per your intended use)

### 1) In ChatGPT thread

* You + ChatGPT discuss
* Click **Sync → Council** (messages go to hub)

### 2) Pair and attach executor

* Extension shows `PAIR-ABCD`
* Terminal:

  ```bash
  council pair claim PAIR-ABCD --repo ~/repo -- opencode
  council attach --session cgpt:<thread_id> --repo ~/repo -- opencode
  ```

### 3) Executor does repo overview

* Wrapper pushes repo overview report → hub
* Extension sees milestone → badge
* Click Pull → ChatGPT gets digest

### 4) You approve plan, executor implements

* ChatGPT generates Task Brief
* Sync → Council
* Executor runs, wrapper captures diffs/tests
* ChatGPT pulls digest, reviews, asks for targeted diff if needed

---

# Add cron/automation later (your idea)

Once the above is stable, adding “auto-run tasks” is easy:

* cron watches sessions for new `task_brief` events
* triggers `council attach` automatically
* pushes run_report back

This becomes “semi-autonomous executor” while you supervise.

