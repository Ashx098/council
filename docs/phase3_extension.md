# Phase 3: Council Chrome Extension

A Chrome extension that integrates Council Hub with ChatGPT's web interface.

## Features

- **Sync → Council**: Sync selected text or last messages to Council Hub
- **Pull ← Council**: Pull digest from Council Hub and insert into composer
- **Status Indicator**: Green/red dot shows hub connection status
- **Configurable Hub URL**: Set via extension popup

## Installation

1. Open Chrome and navigate to `chrome://extensions`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `packages/extension` directory
5. The extension should appear with a blue icon

## Configuration

Click the extension icon to open the settings panel:

- **Hub URL**: Default is `http://127.0.0.1:7337`
- **Current Session**: Shows the ChatGPT thread ID
- **Clear Cursor**: Reset the pull cursor for this thread
- **Open Hub**: Open hub URL in a new tab

## How It Works

### Sync (→ Council)

1. If text is selected on the page:
   - Syncs selected text as a user message
2. If no text selected:
   - Gets last user message + last assistant message from conversation
3. Posts to hub as events with:
   - `source`: "user" or "chatgpt"
   - `type`: "message"
   - `body`: extracted text
   - `meta`: { url, thread_id, role, ts }

### Pull (← Council)

1. Gets cursor from `chrome.storage.local` for this session
2. Calls `GET /v1/sessions/{session_id}/digest?after={cursor}`
3. Formats digest and inserts into ChatGPT composer
4. Updates cursor to `next_cursor` from response

### Session ID

Session IDs are derived from ChatGPT thread URLs:
- URL: `https://chatgpt.com/c/<thread_id>`
- Session ID: `cgpt:<thread_id>`

## DOM Selectors

The extension uses multiple selector strategies for resilience:

```javascript
// Messages
'[data-testid="conversation-turn"]'
'.text-base.gap-4'
'.group.w-full'

// User messages
'[data-testid="user-message"]'
'.whitespace-pre-wrap.font-user'

// Assistant messages
'[data-testid="assistant-message"]'
'.markdown.prose'

// Composer
'#prompt-textarea'
'textarea[placeholder*="Message"]'
'div[contenteditable="true"]'
```

If selectors fail, the extension shows an error toast.

## Validation Checklist

1. **Start the hub**:
   ```bash
   cd packages/hub
   source .venv/bin/activate
   uvicorn council_hub.main:app --port 7337
   ```

2. **Open ChatGPT** and navigate to a thread

3. **Click Sync → Council**:
   - Status indicator should be green
   - Toast shows "Synced N message(s)"

4. **Verify events in hub**:
   ```bash
   # Get thread ID from URL (e.g., https://chatgpt.com/c/abc123)
   curl -s "http://127.0.0.1:7337/v1/sessions/cgpt:abc123/events?after=0"
   ```

5. **Generate some events** (using CLI or direct API calls):
   ```bash
   # Example: add a patch event
   curl -X POST "http://127.0.0.1:7337/v1/sessions/cgpt:abc123/events" \
     -H "Content-Type: application/json" \
     -d '{"source":"wrapper","type":"patch","body":"Fixed bug"}'
   ```

6. **Click Pull ← Council**:
   - Digest should be inserted into composer
   - Toast shows "Pulled updates (cursor: N)"

7. **Click Pull again**:
   - Should show "(No new updates)" if no new events

8. **Test configuration**:
   - Click extension icon
   - Change hub URL to wrong value
   - Status should turn red
   - Revert to correct URL
   - Status should turn green

## Troubleshooting

### Hub not running

**Symptom**: Status indicator is red, "Sync" and "Pull" fail.

**Fix**: Start the hub:
```bash
cd packages/hub && uvicorn council_hub.main:app --port 7337
```

### CORS errors

**Symptom**: Console shows CORS errors.

**Fix**: The extension handles this via background script. Make sure:
- Extension has `host_permissions` for the hub URL
- Background script is running (check `chrome://extensions` for errors)

### Selectors not working

**Symptom**: "Could not insert into composer" or no messages found.

**Fix**: ChatGPT may have updated their DOM. Check:
1. Open DevTools (F12)
2. Inspect the composer element
3. Add new selectors to `dom_extract.js`

### Thread ID not found

**Symptom**: Session shows as `cgpt:tab-<uuid>` instead of thread ID.

**Fix**: This happens on non-thread pages. Navigate to a specific chat thread.

## Files

```
packages/extension/
├── manifest.json           # MV3 manifest
├── src/
│   ├── content_script.js   # Main UI injection
│   ├── content_styles.css  # Toolbar styles
│   ├── background.js       # Service worker for API calls
│   ├── ui/
│   │   ├── panel.html      # Popup panel
│   │   └── panel.js        # Panel logic
│   └── lib/
│       ├── api.js          # (Background API utilities)
│       ├── thread_id.js    # Thread ID extraction
│       ├── cursor_store.js # Cursor storage
│       ├── dom_extract.js  # DOM query utilities
│       └── format_digest.js # Digest formatting
└── assets/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## Known Limitations

- No auto-sync (must click buttons)
- No SSE/streaming
- No pairing (manual thread detection)
- Digest is plain text (no special formatting in composer)

## Future Enhancements

- Phase 4: SSE streaming for real-time updates
- Phase 5: Pairing service for thread binding
- Auto-sync on new messages
- Rich formatting in composer
