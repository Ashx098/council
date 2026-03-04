# Council User Guide

**A beginner's guide to using Council with ChatGPT and AI coding agents.**

---

## What You'll Learn

This guide will teach you how to:

1. Set up Council on your computer
2. Connect ChatGPT to your local projects
3. Run AI coding agents with automatic context syncing
4. Keep ChatGPT informed about what your agent is doing

---

## Prerequisites

Before starting, make sure you have:

- **Python 3.10 or later** - [Download Python](https://www.python.org/downloads/)
- **Google Chrome** - [Download Chrome](https://www.google.com/chrome/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **A ChatGPT account** - [ChatGPT](https://chatgpt.com/)

---

## Part 1: Installation

### Step 1: Download Council

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
# Clone the repository
git clone https://github.com/your-org/council.git

# Go into the directory
cd council
```

### Step 2: Install the Hub

The **Hub** is the central server that stores all your conversation data.

```bash
# Go to the hub package
cd packages/hub

# Install it
pip install -e .

# Go back to root
cd ../..
```

### Step 3: Install the CLI

The **CLI** (Command Line Interface) lets you run agents and connect them to the hub.

```bash
# Go to the CLI package
cd packages/cli

# Install it
pip install -e .

# Go back to root
cd ../..
```

### Step 4: Install the Chrome Extension

The **Extension** adds Council buttons to ChatGPT.

1. Open Chrome
2. Type `chrome://extensions/` in the address bar and press Enter
3. Toggle **"Developer mode"** ON (top right corner)
4. Click **"Load unpacked"**
5. Navigate to and select the `packages/extension` folder

You should now see the Council extension in your toolbar.

---

## Part 2: Starting the Hub

The Hub must be running for everything else to work.

### Starting the Hub

Open a new terminal window and run:

```bash
council-hub
```

You should see something like:

```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://127.0.0.1:7337
```

**Keep this terminal window open!** The hub needs to stay running.

### Verifying the Hub is Working

Open another terminal and run:

```bash
curl http://127.0.0.1:7337/health
```

You should see:

```json
{"status": "healthy", "version": "1.0.0-phase5"}
```

---

## Part 3: Your First Session

Let's walk through a complete workflow.

### Step 1: Open ChatGPT

1. Go to [chatgpt.com](https://chatgpt.com)
2. Start a new chat

### Step 2: Create a Pairing Code

The pairing code links your ChatGPT conversation to your terminal.

1. Click the **Council extension icon** in Chrome's toolbar
2. You'll see a popup with settings
3. Scroll down to **"Pairing Code"**
4. Click **"Create Pair Code"**

You'll see a 4-character code like `AB7K` displayed in large text, along with a countdown timer.

### Step 3: Claim the Code

Open a terminal and run:

```bash
council pair AB7K --repo ~/my-project
```

Replace `~/my-project` with the path to your project folder.

You should see:

```
✓ Paired successfully!
  Code: AB7K
  Session: cgpt:abc123...
  Repo: /home/you/my-project

You can now use:
  council attach --pair AB7K -- <command>
```

### Step 4: Attach an Agent

Now let's connect an AI agent to this session. Run:

```bash
council attach --pair AB7K -- echo "Hello from the agent!"
```

This is a simple test. In real usage, you'd run something like:

```bash
council attach --pair AB7K -- opencode
# or
council attach --pair AB7K -- claude-code
```

### Step 5: Sync to ChatGPT

Back in ChatGPT:

1. Type a message like: "I want to refactor the auth module"
2. Select the text you typed
3. Click the **Sync** button that appears in the toolbar

This sends your message to the hub.

### Step 6: Pull Context

When your agent finishes working:

1. Click the **Pull** button in ChatGPT
2. A digest of what happened is inserted into your composer
3. Now ChatGPT knows what the agent did!

---

## Part 4: Real-Time Notifications

Council can notify you automatically when important things happen.

### What Triggers Notifications

- **Question**: Agent needs your input
- **Run Report**: Agent finished a task
- **Test Failure**: Tests are failing
- **Decision**: Something was decided

### Setting Up Notifications

1. Click the **Council extension icon**
2. Toggle **"Auto-draft Pull on milestones"** ON
3. Toggle **"Notify on Patch"** ON if you want patch notifications

Now when an agent finishes, the digest is automatically inserted into ChatGPT's composer (but not sent - you still control that).

---

## Part 5: Common Workflows

### Workflow 1: Refactoring with Context

```bash
# Terminal 1: Start the hub
council-hub

# Terminal 2: Pair and attach
council pair AB7K --repo ~/my-app
council attach --pair AB7K -- opencode
```

In ChatGPT:
1. Describe the refactoring task
2. Sync the message
3. Wait for agent to work
4. Pull to see what changed
5. Continue the conversation with full context

### Workflow 2: Debugging with Test Results

```bash
# Run tests and capture output
council run --pair AB7K -- pytest tests/
```

The test results are automatically stored. Pull in ChatGPT to see:
- Which tests passed/failed
- Error messages
- What changed since last run

### Workflow 3: Multi-Agent Session

You can have multiple agents in the same session:

```bash
# Terminal 2: Primary agent
council attach --pair AB7K -- opencode

# Terminal 3: Background tests
council attach --pair AB7K -- pytest --watch
```

---

## Part 6: CLI Commands Reference

### `council pair`

Claim or manage pairing codes.

```bash
# Claim a code
council pair AB7K --repo ~/project

# List existing pairings
council pair --list

# Remove a pairing
council pair --remove AB7K
```

### `council attach`

Run an agent with output capture.

```bash
# Basic usage
council attach --pair AB7K -- opencode

# With session ID instead of pair
council attach --session cgpt:abc123 --repo ~/project -- opencode
```

### `council run`

Execute a single command and report results.

```bash
council run --pair AB7K -- pytest tests/
council run --pair AB7K -- npm run build
```

### `council tail`

View recent events.

```bash
# Last 10 events
council tail --pair AB7K

# Last 50 events
council tail --pair AB7K --limit 50
```

### `council snapshot`

View current session state.

```bash
council snapshot --pair AB7K
```

---

## Part 7: Troubleshooting

### "Connection refused" errors

**Problem**: CLI can't connect to hub.

**Solution**:
1. Make sure the hub is running: `curl http://127.0.0.1:7337/health`
2. Check the hub URL: `echo $COUNCIL_HUB_URL`
3. Restart the hub: `council-hub`

### Extension shows "Error" status

**Problem**: Extension can't connect to hub.

**Solution**:
1. Click the extension icon
2. Check the Hub URL setting
3. Make sure it matches `http://127.0.0.1:7337`
4. Refresh the ChatGPT page

### Pairing code "not found"

**Problem**: CLI says the code doesn't exist.

**Solution**:
1. Codes expire after 10 minutes - create a new one
2. Make sure you typed the code correctly
3. Check that hub is running

### SSE shows "stale" status

**Problem**: Extension shows "SSE: Stale (paused)".

**Solution**:
1. Click the **Reconnect** button in the extension popup
2. If that doesn't work, refresh the ChatGPT page
3. The connection should automatically reconnect within 1 minute

### No events showing up

**Problem**: Events aren't being stored.

**Solution**:
1. Check the hub terminal for errors
2. Verify the session ID matches
3. Try clearing the database: `rm ~/.council/council.db`

---

## Part 8: Tips and Best Practices

### Keep the Hub Running

The hub should always be running when you're using Council. Consider:

- Running it in a dedicated terminal tab
- Using a process manager like `tmux` or `screen`
- Setting it up as a system service (advanced)

### Use Pair Codes

Always use pairing codes instead of manual session IDs:
- Easier to remember (`AB7K` vs `cgpt:abc123-def456-...`)
- Automatically binds your repo path
- Less error-prone

### Pull Before Continuing

Always click Pull before continuing a ChatGPT conversation:
- ChatGPT needs to know what the agent did
- The digest is bounded (won't overflow context)
- Includes only what's relevant

### Check Status Regularly

Click the extension icon to see:
- Connection status
- Update count (how many new events)
- Current pairing code

---

## Part 9: Advanced Usage

### Custom Hub URL

If your hub runs on a different port:

```bash
export COUNCIL_HUB_URL=http://127.0.0.1:8080
council pair AB7K
```

In the extension:
1. Click the extension icon
2. Change the Hub URL
3. Click Save

### Environment Variables

```bash
# Hub settings
export COUNCIL_DATA_DIR=~/.council
export COUNCIL_PORT=7337

# CLI settings
export COUNCIL_HUB_URL=http://127.0.0.1:7337
```

### Direct API Access

You can interact with the hub directly via HTTP:

```bash
# Create event
curl -X POST http://127.0.0.1:7337/v1/sessions/cgpt:test/events \
  -H "Content-Type: application/json" \
  -d '{"source": "user", "type": "message", "body": "Hello!"}'

# Get digest
curl http://127.0.0.1:7337/v1/sessions/cgpt:test/digest
```

---

## Getting Help

- **Documentation**: See the `docs/` folder
- **Issues**: Open an issue on GitHub
- **Architecture**: See `docs/architecture.md`
- **API**: See `docs/protocol.md`

---

## Summary

You now know how to:

1. **Install** Council (hub, CLI, extension)
2. **Start** the hub server
3. **Create** pairing codes in ChatGPT
4. **Claim** codes with the CLI
5. **Attach** agents to sessions
6. **Sync** messages to the hub
7. **Pull** digests into ChatGPT
8. **Troubleshoot** common issues

**Next Steps**: Try using Council with a real project and agent!
