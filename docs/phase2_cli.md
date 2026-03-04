# Phase 2: Council CLI

Council CLI is a wrapper for AI coding agents that captures their activity and logs it to the Council Hub.

## Commands

### `council tail`

Show recent events for a session:

```bash
council tail --session cgpt:demo --n 50
```

Output:
```
ID     Time                Source     Type         Body
1      12:00:00           wrapper    message      Hello from agent...
2      12:00:05           wrapper    patch        Files: a.py (+1/-0)...
```

### `council snapshot`

Show a clipboard-friendly snapshot of session state:

```bash
council snapshot --session cgpt:demo
# Or with cursor:
council snapshot --session cgpt:demo --after 10
```

Output includes:
- Session ID
- Current task (if present)
- Latest test status
- Latest patch summary
- Open questions
- Bounded digest text
- Next cursor

### `council run`

Run a command and upload results:

```bash
council run --session cgpt:demo --repo /path/to/repo -- pytest -q
```

Features:
- Safety allowlist (use `--allow-any-command` to bypass)
- Detects test commands and uses `test_log` artifact kind
- Emits `tool_run` event (or `test_result` for tests)
- Uploads output as artifact

### `council attach`

Attach to an agent process with monitoring:

```bash
council attach --session cgpt:demo --repo /path/to/repo -- your-agent-command
```

Features:
- Prints "Supervisor Brief" at startup
- Batches stdout/stderr into message events
- Watches git diffs every `--git-interval` seconds
- Emits `patch` events when diffs change
- Emits `run_report` at end

Options:
- `--git-interval 2` - Git check interval
- `--batch-interval 2` - Output batch interval  
- `--batch-lines 50` - Max lines per batch

## Installation

```bash
cd packages/cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Set hub URL via environment variable:

```bash
export COUNCIL_HUB_URL=http://127.0.0.1:7337
```

## Validation Demo

### Terminal 1: Start Hub

```bash
cd packages/hub
source .venv/bin/activate
uvicorn council_hub.main:app --port 7337
```

### Terminal 2: Run CLI Demo

```bash
cd packages/cli
source .venv/bin/activate
export COUNCIL_HUB_URL=http://127.0.0.1:7337

# Create a test repo
TMP=$(mktemp -d)
cd "$TMP"
git init
echo "hi" > a.txt
git add a.txt && git commit -m "init"

# Attach and edit file
council attach --session cgpt:demo --repo "$TMP" -- bash -lc 'echo "more" >> a.txt; sleep 1;'

# Snapshot the results
council snapshot --session cgpt:demo

# Run a command
council run --session cgpt:demo --repo "$TMP" -- python -c 'print("ok")'

# Tail events
council tail --session cgpt:demo --n 10
```

### Expected Results

1. **attach** posts:
   - message events (from bash output)
   - patch event with artifact (from git diff)
   - run_report event

2. **snapshot** shows:
   - Session info
   - Patch summary with artifact reference
   - Bounded digest

3. **run** posts:
   - tool_run event with artifact
   - Command output stored as artifact

4. **tail** shows:
   - All events in compact format

## Architecture

```
packages/cli/
├── src/council_cli/
│   ├── cli.py           # Typer app entry point
│   ├── client/
│   │   └── hub_client.py   # HTTP client for hub API
│   ├── commands/
│   │   ├── attach.py    # Agent monitoring
│   │   ├── run.py       # Command execution
│   │   ├── snapshot.py  # Session snapshot
│   │   └── tail.py      # Event listing
│   ├── wrapper/
│   │   ├── capture.py   # Output batching
│   │   ├── gitwatch.py  # Git diff monitoring
│   │   ├── report.py    # Run report generation
│   │   ├── runner.py    # Command execution
│   │   └── safety.py    # Command allowlist
│   └── utils/
│       ├── text.py      # Text utilities
│       └── time.py      # Time utilities
└── tests/
    ├── test_hub_client.py
    └── test_gitwatch_summary.py
```

## Safety

By default, commands must be in the allowlist. The allowlist includes:
- Python tools: `python`, `pytest`, `pip`, `poetry`, `uv`
- Test runners: `pytest`, `go test`, `npm test`, `cargo test`
- Linters: `ruff`, `black`, `mypy`, `eslint`
- Git: `git status`, `git diff`, etc.
- Shell: `bash`, `sh` (shell commands are still checked)

Use `--allow-any-command` to bypass (not recommended for untrusted input).

## Known Limitations

- No SSE/streaming (planned for Phase 4)
- No pairing service (planned for Phase 5)
- No extension integration (planned for Phase 3)
- Digest is deterministic truncation (no LLM summarization)
