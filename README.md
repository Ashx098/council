# Council

**Council** is a local session store and digest service that bridges ChatGPT conversations with AI coding agents. It solves context bloat by providing bounded digests and canonical per-thread session storage.

## What Council Does

When you're working with ChatGPT and an AI coding agent (like OpenCode, Claude Code, or others), keeping them in sync is painful:

- **Context bloat**: ChatGPT doesn't know what the agent did
- **Manual copy-paste**: You constantly copy messages back and forth
- **Lost context**: Agent outputs get lost between sessions

Council solves this by acting as a **local hub** that both ChatGPT and your agents talk to:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Council Hub                               │
│                                                                  │
│   • Stores events (messages, patches, test results)             │
│   • Generates bounded digests for ChatGPT context               │
│   • Streams real-time updates via SSE                           │
│   • Pairs ChatGPT threads with CLI sessions                     │
│                                                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  ChatGPT    │  │    CLI      │  │  Extension  │
    │  (Browser)  │  │  (Agent)    │  │  (Chrome)   │
    └─────────────┘  └─────────────┘  └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Chrome browser (for extension)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/council.git
cd council

# Install the hub
cd packages/hub
pip install -e .

# Install the CLI
cd ../cli
pip install -e .

# Return to root
cd ../..
```

### Start the Hub

```bash
council-hub
# or: uvicorn council_hub.main:app --port 7337
```

The hub runs at `http://127.0.0.1:7337`.

### Install the Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `packages/extension` folder

### Basic Usage

**Step 1: Create a Pairing Code**

In ChatGPT, click the Council extension icon and click "Create Pair Code". You'll see a 4-character code like `AB7K`.

**Step 2: Claim the Code in CLI**

```bash
council pair AB7K --repo ~/my-project
```

**Step 3: Attach Your Agent**

```bash
council attach --pair AB7K -- opencode
```

**Step 4: Work Normally**

- ChatGPT sends messages to the hub via Sync button
- Agent outputs are captured and stored
- Pull button fetches bounded digest into ChatGPT
- Real-time notifications show when agent finishes

## Components

### Hub (packages/hub)

FastAPI server with SQLite backend:

- REST API for events, digests, artifacts
- SSE streaming for real-time updates
- Pairing service for session binding

### CLI (packages/cli)

Command-line interface:

- `council pair` - Claim pairing codes
- `council attach` - Run agents with output capture
- `council run` - Execute single commands
- `council tail` - View recent events
- `council snapshot` - View session state

### Extension (packages/extension)

Chrome extension for ChatGPT:

- Sync button: Send selected text to hub
- Pull button: Fetch digest into composer
- Real-time notifications for milestones
- Pairing code generation

## Event Types

| Type | Description |
|------|-------------|
| `message` | Chat message |
| `task_brief` | Task description |
| `question` | Open question requiring response |
| `patch` | Code change summary |
| `test_result` | Test run output |
| `run_report` | Execution summary |
| `decision` | Pinned decision |
| `milestone` | Checkpoint event |

## Pairing Flow

The pairing system removes the need to copy-paste session IDs:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Extension  │     │     Hub      │     │     CLI      │
│  (ChatGPT)   │     │  (port 7337) │     │  (terminal)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ Create pair code   │                    │
       │───────────────────>│                    │
       │                    │                    │
       │  Code: "AB7K"      │                    │
       │<───────────────────│                    │
       │                    │                    │
       │                    │  council pair AB7K │
       │                    │<───────────────────│
       │                    │                    │
       │                    │  Claim code        │
       │                    │  (binds session)   │
       │                    │───────────────────>│
       │                    │                    │
       │                    │  council attach    │
       │                    │  --pair AB7K       │
       │                    │<───────────────────│
```

## Documentation

- **[User Guide](docs/user-guide.md)** - Step-by-step tutorial for beginners
- **[Installation](docs/installation.md)** - Detailed setup instructions
- **[Pairing System](docs/pairing.md)** - How pairing works
- **[Architecture](docs/architecture.md)** - System design
- **[Protocol](docs/protocol.md)** - API specification

## Project Structure

```
council/
├── packages/
│   ├── hub/              # FastAPI server
│   │   ├── src/council_hub/
│   │   └── tests/
│   ├── cli/              # Command-line tool
│   │   └── src/council_cli/
│   └── extension/        # Chrome extension
│       ├── src/
│       ├── manifest.json
│       └── assets/
├── docs/
│   ├── user-guide.md
│   ├── installation.md
│   ├── pairing.md
│   ├── architecture.md
│   └── protocol.md
└── README.md
```

## API Overview

### Key Endpoints

```
POST /v1/sessions/{id}/events     # Ingest events
GET  /v1/sessions/{id}/digest     # Get bounded digest
GET  /v1/sessions/{id}/stream     # SSE stream
GET  /v1/sessions/{id}/context    # Context pack

POST /v1/pair/create              # Create pairing code
POST /v1/pair/claim               # Claim pairing code
GET  /v1/pair/{code}              # Get pairing status

GET  /health                      # Health check
```

### Example: Ingest Event

```bash
curl -X POST http://127.0.0.1:7337/v1/sessions/cgpt:abc123/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wrapper",
    "type": "patch",
    "body": "Modified src/auth.py: +45/-12 lines",
    "meta": {"files_changed": ["src/auth.py"]}
  }'
```

### Example: Get Digest

```bash
curl http://127.0.0.1:7337/v1/sessions/cgpt:abc123/digest?after=0
```

## Running Tests

```bash
# Hub tests
cd packages/hub
pytest -v

# CLI tests
cd packages/cli
pytest -v
```

## Configuration

### Environment Variables

```bash
# Hub
COUNCIL_DATA_DIR=~/.council      # Data directory
COUNCIL_PORT=7337                 # Server port

# CLI
COUNCIL_HUB_URL=http://127.0.0.1:7337   # Hub URL
```

### Extension Settings

Click the extension icon to access:

- Hub URL
- Auto-draft Pull (automatically insert digest on milestones)
- Notify on Patch (show notifications for patch events)

## Size Budgets

Digests are bounded to prevent context bloat:

| Budget | Limit |
|--------|-------|
| Digest max chars | 12,000 |
| Patch hunks per file | 3 |
| Lines per hunk | 20 |
| Log max lines | 200 |

## Roadmap

- [x] Phase 1: Hub MVP
- [x] Phase 2: CLI wrapper
- [x] Phase 3: Chrome extension
- [x] Phase 4: SSE streaming + milestones
- [x] Phase 4.1: MV3 service worker reliability
- [x] Phase 5: Pairing service
- [ ] Phase 6: LLM-powered summarization
- [ ] Phase 7: Multi-repo support

## Troubleshooting

### Hub won't start

```bash
# Check if port is in use
lsof -i :7337

# Clear database and restart
rm -rf ~/.council/*.db
council-hub
```

### Extension not connecting

1. Check hub is running: `curl http://127.0.0.1:7337/health`
2. Check hub URL in extension settings
3. Refresh the ChatGPT page

### CLI can't find pairing code

1. Make sure you created a code in the extension
2. Check hub is running
3. Verify hub URL: `echo $COUNCIL_HUB_URL`

## License

MIT
