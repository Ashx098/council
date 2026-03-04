/**
 * Council Extension Background Script (Service Worker)
 * 
 * Handles hub HTTP calls, SSE streaming, and message passing.
 * Phase 4.1: MV3 service worker reliability with alarms.
 */

// Storage keys
const STORAGE_KEY_PREFIX = 'council_cursor_';
const CONFIG_KEY = 'council_config';
const UPDATES_KEY_PREFIX = 'council_updates_';
const STATE_KEY_PREFIX = 'council_state_';

// SSE connection state per session
const sseConnections = new Map();

// Reconnect backoff settings
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;

// Keepalive settings
const KEEPALIVE_ALARM_NAME = 'council_keepalive';
const KEEPALIVE_INTERVAL_MINUTES = 1;
const STALE_THRESHOLD_MS = 3 * 60 * 1000; // 3 minutes

// Milestone event types that trigger notifications
const MILESTONE_TYPES = ['question', 'run_report'];

/**
 * Check if an event is a milestone that should notify.
 */
function isMilestone(event) {
  // Always notify for question and run_report
  if (MILESTONE_TYPES.includes(event.type)) {
    return true;
  }
  
  // Notify for test_result with non-zero exit code
  if (event.type === 'test_result') {
    const exitCode = event.meta?.exit_code;
    if (exitCode !== undefined && exitCode !== 0) {
      return true;
    }
  }
  
  return false;
}

/**
 * Get extension configuration.
 */
async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get([CONFIG_KEY], (result) => {
      resolve(result[CONFIG_KEY] || {
        hubUrl: 'http://127.0.0.1:7337',
        autoPull: false,
        notifyOnPatch: false
      });
    });
  });
}

/**
 * Get cursor for a session.
 */
async function getCursor(sessionId) {
  const key = STORAGE_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.get([key], (result) => {
      resolve(result[key] || 0);
    });
  });
}

/**
 * Set cursor for a session.
 */
async function setCursor(sessionId, cursor) {
  const key = STORAGE_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: cursor }, resolve);
  });
}

/**
 * Get update count for a session.
 */
async function getUpdateCount(sessionId) {
  const key = UPDATES_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.get([key], (result) => {
      resolve(result[key] || 0);
    });
  });
}

/**
 * Increment update count for a session.
 */
async function incrementUpdateCount(sessionId) {
  const key = UPDATES_KEY_PREFIX + sessionId;
  const current = await getUpdateCount(sessionId);
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: current + 1 }, resolve);
  });
}

/**
 * Clear update count for a session.
 */
async function clearUpdateCount(sessionId) {
  const key = UPDATES_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.remove([key], resolve);
  });
}

/**
 * Get session state (last_event_ts, status).
 */
async function getSessionState(sessionId) {
  const key = STATE_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.get([key], (result) => {
      resolve(result[key] || {
        lastEventTs: null,
        status: 'disconnected',
        lastConnectTs: null
      });
    });
  });
}

/**
 * Set session state.
 */
async function setSessionState(sessionId, state) {
  const key = STATE_KEY_PREFIX + sessionId;
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: state }, resolve);
  });
}

/**
 * Update session status.
 */
async function updateSessionStatus(sessionId, status) {
  const state = await getSessionState(sessionId);
  const now = Date.now();
  
  const newState = {
    ...state,
    status,
    lastConnectTs: status === 'connected' ? now : state.lastConnectTs
  };
  
  await setSessionState(sessionId, newState);
  return newState;
}

/**
 * Check if session is stale (no events for > STALE_THRESHOLD_MS).
 */
async function isSessionStale(sessionId) {
  const state = await getSessionState(sessionId);
  
  if (!state.lastEventTs) {
    return false; // Never received events, not stale
  }
  
  const now = Date.now();
  return (now - state.lastEventTs) > STALE_THRESHOLD_MS;
}

/**
 * Check hub health.
 */
async function checkHealth(hubUrl) {
  try {
    const response = await fetch(`${hubUrl}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    if (response.ok) {
      return { healthy: true, data: await response.json() };
    }
    return { healthy: false, error: `HTTP ${response.status}` };
  } catch (e) {
    return { healthy: false, error: e.message };
  }
}

/**
 * Ingest an event to the hub.
 */
async function ingestEvent(hubUrl, sessionId, event) {
  const response = await fetch(`${hubUrl}/v1/sessions/${sessionId}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  
  return response.json();
}

/**
 * Get digest from hub.
 */
async function getDigest(hubUrl, sessionId, after) {
  const url = `${hubUrl}/v1/sessions/${sessionId}/digest?after=${after}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  
  return response.json();
}

/**
 * Start SSE connection for a session.
 */
async function startSSE(sessionId, hubUrl, reconnectDelay = INITIAL_RECONNECT_DELAY) {
  // Don't start if already connected
  if (sseConnections.has(sessionId)) {
    console.log(`[Council SSE] Already connected for ${sessionId}`);
    return;
  }
  
  const cursor = await getCursor(sessionId);
  const url = `${hubUrl}/v1/sessions/${sessionId}/stream?after=${cursor}`;
  
  console.log(`[Council SSE] Starting connection for ${sessionId}`);
  
  const connection = {
    abortController: new AbortController(),
    reconnectDelay,
    sessionId
  };
  
  sseConnections.set(sessionId, connection);
  
  // Update status to connecting
  await updateSessionStatus(sessionId, 'connecting');
  
  try {
    const response = await fetch(url, {
      signal: connection.abortController.signal,
      headers: {
        'Accept': 'text/event-stream',
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    // Reset reconnect delay on successful connection
    connection.reconnectDelay = INITIAL_RECONNECT_DELAY;
    
    // Update status to connected
    await updateSessionStatus(sessionId, 'connected');
    
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log(`[Council SSE] Stream ended for ${sessionId}`);
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      
      // Process complete SSE events
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      let eventData = null;
      let eventId = null;
      
      for (const line of lines) {
        if (line.startsWith('id: ')) {
          eventId = parseInt(line.slice(4), 10);
        } else if (line.startsWith('data: ')) {
          try {
            eventData = JSON.parse(line.slice(6));
          } catch (e) {
            console.warn('[Council SSE] Failed to parse data:', line);
          }
        } else if (line === '' && eventData) {
          // Empty line signals end of event
          await handleSSEEvent(sessionId, eventId, eventData, hubUrl);
          eventData = null;
          eventId = null;
        }
      }
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log(`[Council SSE] Connection aborted for ${sessionId}`);
    } else {
      console.error(`[Council SSE] Error for ${sessionId}:`, error.message);
      await updateSessionStatus(sessionId, 'error');
    }
  } finally {
    sseConnections.delete(sessionId);
    
    // Attempt reconnect with exponential backoff
    if (!connection.abortController.signal.aborted) {
      const delay = Math.min(connection.reconnectDelay * 2, MAX_RECONNECT_DELAY);
      console.log(`[Council SSE] Reconnecting ${sessionId} in ${delay}ms`);
      await updateSessionStatus(sessionId, 'reconnecting');
      
      setTimeout(async () => {
        const config = await getConfig();
        startSSE(sessionId, config.hubUrl, delay);
      }, delay);
    }
  }
}

/**
 * Handle an incoming SSE event.
 */
async function handleSSEEvent(sessionId, eventId, eventData, hubUrl) {
  // Skip hello event
  if (eventData.type === 'connected') {
    console.log(`[Council SSE] Connected to ${sessionId}, after=${eventData.after}`);
    return;
  }
  
  console.log(`[Council SSE] Event ${eventId} for ${sessionId}:`, eventData.type);
  
  // Update cursor
  if (eventId !== null) {
    await setCursor(sessionId, eventId);
  }
  
  // Update last event timestamp
  const state = await getSessionState(sessionId);
  await setSessionState(sessionId, {
    ...state,
    lastEventTs: Date.now(),
    status: 'connected'
  });
  
  // Check if milestone
  if (isMilestone(eventData)) {
    // Increment update count
    await incrementUpdateCount(sessionId);
    
    // Notify content script
    const config = await getConfig();
    const updateCount = await getUpdateCount(sessionId);
    
    // Find ChatGPT tabs for this session
    const tabs = await chrome.tabs.query({ url: 'https://chatgpt.com/*' });
    
    for (const tab of tabs) {
      try {
        await chrome.tabs.sendMessage(tab.id, {
          action: 'milestone',
          sessionId,
          updateCount,
          event: eventData
        });
      } catch (e) {
        // Tab might not have content script loaded
      }
    }
    
    // Auto-pull if enabled
    if (config.autoPull) {
      try {
        const cursor = await getCursor(sessionId);
        const digest = await getDigest(hubUrl, sessionId, cursor - 1); // -1 to include current event
        
        for (const tab of tabs) {
          try {
            await chrome.tabs.sendMessage(tab.id, {
              action: 'autoDigest',
              sessionId,
              digest
            });
          } catch (e) {
            // Tab might not have content script loaded
          }
        }
      } catch (e) {
        console.error('[Council SSE] Auto-pull failed:', e.message);
      }
    }
  }
}

/**
 * Stop SSE connection for a session.
 */
async function stopSSE(sessionId) {
  const connection = sseConnections.get(sessionId);
  if (connection) {
    connection.abortController.abort();
    sseConnections.delete(sessionId);
    await updateSessionStatus(sessionId, 'disconnected');
    console.log(`[Council SSE] Stopped connection for ${sessionId}`);
  }
}

/**
 * Ensure SSE is connected for a session (reconnect if needed).
 */
async function ensureSSEConnected(sessionId, hubUrl) {
  const isConnected = sseConnections.has(sessionId);
  const state = await getSessionState(sessionId);
  
  if (!isConnected) {
    console.log(`[Council SSE] Ensuring connection for ${sessionId} (status: ${state.status})`);
    await startSSE(sessionId, hubUrl);
  }
}

/**
 * Start SSE for active ChatGPT tabs.
 */
async function startSSEForActiveTabs() {
  const tabs = await chrome.tabs.query({ url: 'https://chatgpt.com/*' });
  const config = await getConfig();
  
  for (const tab of tabs) {
    // Extract thread ID from URL
    const match = tab.url?.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      const sessionId = `cgpt:${match[1]}`;
      await ensureSSEConnected(sessionId, config.hubUrl);
    }
  }
}

/**
 * Keepalive alarm handler - ensure SSE connections are alive.
 */
async function handleKeepaliveAlarm() {
  console.log('[Council Keepalive] Checking SSE connections...');
  
  const config = await getConfig();
  const tabs = await chrome.tabs.query({ url: 'https://chatgpt.com/*' });
  
  for (const tab of tabs) {
    const match = tab.url?.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      const sessionId = `cgpt:${match[1]}`;
      
      // Check if connected
      const isConnected = sseConnections.has(sessionId);
      const state = await getSessionState(sessionId);
      
      if (!isConnected && state.status !== 'connecting') {
        console.log(`[Council Keepalive] Reconnecting stale session ${sessionId}`);
        await startSSE(sessionId, config.hubUrl);
      } else if (isConnected) {
        // Check for staleness
        const stale = await isSessionStale(sessionId);
        if (stale) {
          await updateSessionStatus(sessionId, 'stale');
          // Notify content script
          try {
            await chrome.tabs.sendMessage(tab.id, {
              action: 'staleStatus',
              sessionId
            });
          } catch (e) {
            // Tab might not have content script
          }
        }
      }
    }
  }
}

/**
 * Setup keepalive alarm.
 */
function setupKeepaliveAlarm() {
  // Create alarm if not exists
  chrome.alarms.get(KEEPALIVE_ALARM_NAME, (alarm) => {
    if (!alarm) {
      chrome.alarms.create(KEEPALIVE_ALARM_NAME, {
        periodInMinutes: KEEPALIVE_INTERVAL_MINUTES
      });
      console.log('[Council] Keepalive alarm created');
    }
  });
}

// Message handler
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Handle async responses
  (async () => {
    const config = await getConfig();
    const hubUrl = config.hubUrl || 'http://127.0.0.1:7337';
    
    try {
      switch (message.action) {
        case 'checkHealth': {
          const result = await checkHealth(hubUrl);
          sendResponse(result);
          break;
        }
        
        case 'sync': {
          const { sessionId, events } = message;
          const results = [];
          
          for (const event of events) {
            const result = await ingestEvent(hubUrl, sessionId, event);
            results.push(result);
          }
          
          sendResponse({ success: true, results });
          break;
        }
        
        case 'pull': {
          const { sessionId } = message;
          const cursor = await getCursor(sessionId);
          const digest = await getDigest(hubUrl, sessionId, cursor);
          
          // Update cursor
          await setCursor(sessionId, digest.next_cursor);
          
          // Clear update count on manual pull
          await clearUpdateCount(sessionId);
          
          sendResponse({ success: true, digest, nextCursor: digest.next_cursor });
          break;
        }
        
        case 'getCursor': {
          const { sessionId } = message;
          const cursor = await getCursor(sessionId);
          sendResponse({ cursor });
          break;
        }
        
        case 'setCursor': {
          const { sessionId, cursor } = message;
          await setCursor(sessionId, cursor);
          sendResponse({ success: true });
          break;
        }
        
        case 'getConfig': {
          sendResponse(config);
          break;
        }
        
        case 'setConfig': {
          await chrome.storage.local.set({ [CONFIG_KEY]: message.config });
          sendResponse({ success: true });
          break;
        }
        
        case 'startSSE': {
          const { sessionId } = message;
          await startSSE(sessionId, hubUrl);
          sendResponse({ success: true });
          break;
        }
        
        case 'stopSSE': {
          const { sessionId } = message;
          await stopSSE(sessionId);
          sendResponse({ success: true });
          break;
        }
        
        case 'getUpdateCount': {
          const { sessionId } = message;
          const count = await getUpdateCount(sessionId);
          sendResponse({ count });
          break;
        }
        
        case 'clearUpdates': {
          const { sessionId } = message;
          await clearUpdateCount(sessionId);
          sendResponse({ success: true });
          break;
        }
        
        case 'getSessionState': {
          const { sessionId } = message;
          const state = await getSessionState(sessionId);
          sendResponse({ state });
          break;
        }
        
        case 'reconnect': {
          const { sessionId } = message;
          await stopSSE(sessionId);
          await startSSE(sessionId, hubUrl);
          sendResponse({ success: true });
          break;
        }
        
        default:
          sendResponse({ error: 'Unknown action' });
      }
    } catch (error) {
      console.error('[Council Background]', error);
      sendResponse({ error: error.message });
    }
  })();
  
  // Return true to indicate async response
  return true;
});

// On installed
chrome.runtime.onInstalled.addListener(() => {
  console.log('[Council] Extension installed');
  setupKeepaliveAlarm();
});

// On startup (when service worker wakes)
chrome.runtime.onStartup.addListener(() => {
  console.log('[Council] Service worker started');
  setupKeepaliveAlarm();
  
  // Reconnect SSE for active tabs
  startSSEForActiveTabs();
});

// Alarm handler
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === KEEPALIVE_ALARM_NAME) {
    handleKeepaliveAlarm();
  }
});

// Start SSE when tab is activated
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  if (tab.url && tab.url.includes('chatgpt.com')) {
    const match = tab.url.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      const config = await getConfig();
      const sessionId = `cgpt:${match[1]}`;
      await ensureSSEConnected(sessionId, config.hubUrl);
    }
  }
});

// Start SSE when tab URL changes (navigation within ChatGPT)
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('chatgpt.com')) {
    const match = tab.url.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      const config = await getConfig();
      const sessionId = `cgpt:${match[1]}`;
      await ensureSSEConnected(sessionId, config.hubUrl);
    }
  }
});

// Stop SSE when tab is closed
chrome.tabs.onRemoved.addListener(async (tabId) => {
  // Find which session this tab was for and stop SSE if no other tabs for that session
  const tabs = await chrome.tabs.query({ url: 'https://chatgpt.com/*' });
  const activeSessions = new Set();
  
  for (const tab of tabs) {
    const match = tab.url?.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      activeSessions.add(`cgpt:${match[1]}`);
    }
  }
  
  // Stop SSE for sessions without active tabs
  for (const [sessionId] of sseConnections.entries()) {
    if (!activeSessions.has(sessionId)) {
      console.log(`[Council] No active tabs for ${sessionId}, stopping SSE`);
      await stopSSE(sessionId);
    }
  }
});

// Context menu for quick sync (optional)
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'council-sync-selection',
    title: 'Sync to Council',
    contexts: ['selection']
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'council-sync-selection' && info.selectionText) {
    // Send to content script to handle
    chrome.tabs.sendMessage(tab.id, {
      action: 'syncSelection',
      text: info.selectionText
    });
  }
});

// Initial setup on script load
setupKeepaliveAlarm();
