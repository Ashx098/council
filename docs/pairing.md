# Council Pairing System

The pairing system eliminates the need to copy-paste session IDs between ChatGPT and the CLI.

---

## The Problem

Without pairing, connecting your CLI to a ChatGPT session requires:

1. Find the thread ID in the URL: `chatgpt.com/c/abc123-def456-...`
2. Construct session ID: `cgpt:abc123-def456-...`
3. Pass it to every command: `council attach --session cgpt:abc123-def456-...`

This is:
- **Error-prone**: Easy to mistype
- **Tedious**: Need to do it for every command
- **Not memorable**: Long random strings

---

## The Solution

With pairing:

1. Extension generates a 4-character code: `AB7K`
2. CLI claims it: `council pair AB7K --repo ~/project`
3. Use the code everywhere: `council attach --pair AB7K -- opencode`

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Council Hub                               │
│                                                                      │
│  ┌─────────────────┐                    ┌─────────────────────────┐ │
│  │ pairing_codes   │                    │ sessions                │ │
│  │ ────────────────│                    │ ────────────────────────│ │
│  │ code: AB7K      │───────────────────>│ session_id: cgpt:abc123 │ │
│  │ session_id: ... │                    │ repo_root: ~/project    │ │
│  │ expires_at: ... │                    │ event_count: 15         │ │
│  │ claimed_at: ... │                    │ ...                     │ │
│  └─────────────────┘                    └─────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Extension  │     │     Hub      │     │     CLI      │
│  (ChatGPT)   │     │  (port 7337) │     │  (terminal)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │  1. Create code    │                    │
       │───────────────────>│                    │
       │                    │                    │
       │  POST /v1/pair/create                   │
       │  {"session_id": "cgpt:..."}             │
       │                    │                    │
       │  2. Return code    │                    │
       │<───────────────────│                    │
       │  {"code": "AB7K"}  │                    │
       │                    │                    │
       │  3. Display AB7K   │                    │
       │                    │                    │
       │                    │  4. Claim code     │
       │                    │<───────────────────│
       │                    │                    │
       │                    │  POST /v1/pair/claim
       │                    │  {"code": "AB7K",  │
       │                    │   "repo_root":...} │
       │                    │                    │
       │                    │  5. Bind session   │
       │                    │───────────────────>│
       │                    │                    │
       │                    │  Store locally:    │
       │                    │  ~/.council/pairings.json
       │                    │                    │
       │                    │  6. Attach         │
       │                    │<───────────────────│
       │                    │                    │
       │                    │  council attach    │
       │                    │  --pair AB7K       │
       │                    │                    │
       │                    │  7. Resolve pair   │
       │                    │  → session_id      │
       │                    │                    │
```

---

## Using Pairing

### Creating a Pairing Code

**In the Extension:**

1. Open ChatGPT and navigate to a chat
2. Click the Council extension icon
3. Scroll to "Pairing Code" section
4. Click "Create Pair Code"

The extension displays:
- The 4-character code in large text
- A countdown timer showing expiration

**Via API:**

```bash
curl -X POST http://127.0.0.1:7337/v1/pair/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "cgpt:abc123-def456",
    "ttl_minutes": 10
  }'
```

Response:

```json
{
  "code": "AB7K",
  "session_id": "cgpt:abc123-def456",
  "repo_root": null,
  "created_at": "2024-01-15T10:30:00",
  "expires_at": "2024-01-15T10:40:00",
  "claimed_at": null,
  "claimed_by": null
}
```

### Claiming a Code

**Via CLI:**

```bash
council pair AB7K --repo ~/my-project
```

Output:

```
✓ Paired successfully!
  Code: AB7K
  Session: cgpt:abc123-def456
  Repo: /home/user/my-project

You can now use:
  council attach --pair AB7K -- <command>
```

**Via API:**

```bash
curl -X POST http://127.0.0.1:7337/v1/pair/claim \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AB7K",
    "claimed_by": "my-laptop",
    "repo_root": "/home/user/my-project"
  }'
```

### Using the Pair Code

Once claimed, use `--pair` instead of `--session`:

```bash
# Instead of:
council attach --session cgpt:abc123-def456 --repo ~/project -- opencode

# Use:
council attach --pair AB7K -- opencode
```

The repo path from the claim is remembered:

```bash
# Repo was bound during claim
council attach --pair AB7K -- opencode

# No need to specify --repo again!
```

### Managing Pairings

**List existing pairings:**

```bash
council pair --list
```

Output:

```
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Code ┃ Session ID           ┃ Repo              ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ AB7K │ cgpt:abc123-def456   │ /home/user/proj1  │
│ XYZ9 │ cgpt:789ghi012       │ /home/user/proj2  │
└──────┴──────────────────────┴───────────────────┘
```

**Remove a pairing:**

```bash
council pair --remove AB7K
```

---

## Code Format

Pairing codes are:

- **4 characters** long
- Use **uppercase letters** (A-Z) and **digits** (2-9)
- Exclude **ambiguous characters**: 0, O, 1, I, L

Examples: `AB7K`, `XYZ9`, `C3P0`, `R2D2`

This format ensures:
- Easy to read and type
- No confusion between similar characters
- Memorable (like robot names!)

---

## Expiration

Pairing codes have a **10-minute default expiration**.

### Timer Display

The extension shows a countdown:
- `9:45` - 9 minutes 45 seconds remaining
- `0:30` - 30 seconds remaining
- `(expired)` - Code has expired

### What Happens on Expiry

- The code becomes invalid
- You need to create a new code
- Already-claimed pairings are not affected

### Custom TTL

Create a code with custom expiration:

```bash
curl -X POST http://127.0.0.1:7337/v1/pair/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "cgpt:abc123",
    "ttl_minutes": 30
  }'
```

---

## Local Storage

Claimed pairings are stored locally at:

```
~/.council/pairings.json
```

Format:

```json
{
  "AB7K": {
    "session_id": "cgpt:abc123-def456",
    "repo_root": "/home/user/my-project",
    "claimed_by": "my-laptop",
    "claimed_at": "2024-01-15T10:35:00"
  }
}
```

This allows the CLI to resolve pair codes even after the hub forgets them.

---

## Security Considerations

### Local Network Only

The hub binds to `127.0.0.1` by default, meaning:
- Only accessible from your machine
- Not exposed to the network
- No external access possible

### Code Entropy

4-character codes with the allowed character set:
- 32 possible characters (26 letters + 10 digits - 4 excluded)
- 32^4 = ~1 million combinations
- Combined with 10-minute expiry = low attack surface

### No Authentication

Council is designed for **single-user local development**:
- No authentication mechanism
- No encryption
- Not intended for multi-user or network deployment

For shared environments, use appropriate network isolation.

---

## API Reference

### POST /v1/pair/create

Create a new pairing code.

**Request:**

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
  "created_at": "2024-01-15T10:30:00",
  "expires_at": "2024-01-15T10:40:00",
  "claimed_at": null,
  "claimed_by": null
}
```

### POST /v1/pair/claim

Claim a pairing code.

**Request:**

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
  "created_at": "2024-01-15T10:30:00",
  "expires_at": "2024-01-15T10:40:00",
  "claimed_at": "2024-01-15T10:35:00",
  "claimed_by": "my-laptop"
}
```

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Invalid or expired pairing code | Code doesn't exist or has expired |
| 400 | Pairing code already claimed | Someone else claimed it first |

### GET /v1/pair/{code}

Get pairing code status.

**Response:**

```json
{
  "code": "AB7K",
  "session_id": "cgpt:abc123",
  "repo_root": null,
  "created_at": "2024-01-15T10:30:00",
  "expires_at": "2024-01-15T10:40:00",
  "claimed_at": null,
  "claimed_by": null
}
```

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | pairing_not_found | Code doesn't exist or has expired |

### GET /v1/pair/session/{session_id}

Get the active pairing code for a session.

**Response:**

Same as GET /v1/pair/{code}

**Errors:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | no_active_pairing | No unclaimed code for this session |

---

## Troubleshooting

### "Unknown pairing code"

**Cause:** Code doesn't exist, expired, or not yet created.

**Solution:**
1. Create a new code in the extension
2. Claim it immediately (codes expire in 10 minutes)

### "Pairing code already claimed"

**Cause:** Someone else (or another terminal) claimed the code.

**Solution:**
1. Create a new code in the extension
2. Claim it before anyone else

### Code shows "(expired)" immediately

**Cause:** Clock skew between extension and hub.

**Solution:**
1. Check system time is correct
2. Create a new code

### Lost pairing after computer restart

**Cause:** Pairings are stored in memory on the hub.

**Solution:**
1. The CLI stores pairings locally in `~/.council/pairings.json`
2. Check if the pairing still exists: `council pair --list`
3. If lost, create and claim a new code

---

## Best Practices

1. **Create codes when needed**: Don't pre-create codes; they expire quickly
2. **Claim immediately**: Claim the code right after creating it
3. **Use descriptive claimed_by**: Include hostname or purpose for clarity
4. **Clean up old pairings**: Run `council pair --list` and remove unused ones
5. **Bind repo paths**: Always include `--repo` when claiming for automatic path resolution
