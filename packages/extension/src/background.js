/**
 * Council Extension Background Script (Service Worker)
 * 
 * Handles hub HTTP calls and message passing.
 */

// Storage keys
const STORAGE_KEY_PREFIX = 'council_cursor_';
const CONFIG_KEY = 'council_config';

/**
 * Get extension configuration.
 */
async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get([CONFIG_KEY], (result) => {
      resolve(result[CONFIG_KEY] || {
        hubUrl: 'http://127.0.0.1:7337'
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
 * Get context from hub.
 */
async function getContext(hubUrl, sessionId) {
  const response = await fetch(`${hubUrl}/v1/sessions/${sessionId}/context`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  
  return response.json();
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
