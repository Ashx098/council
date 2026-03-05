/**
 * Council Extension Panel Script
 * 
 * Handles the popup panel UI.
 */

// Elements - all nullable
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const hubUrlInput = document.getElementById('hub-url');
const saveBtn = document.getElementById('save-btn');
const testBtn = document.getElementById('test-btn');
const threadIdEl = document.getElementById('thread-id');
const clearCursorBtn = document.getElementById('clear-cursor-btn');
const openHubBtn = document.getElementById('open-hub-btn');
const autoPullToggle = document.getElementById('auto-pull-toggle');
const notifyPatchToggle = document.getElementById('notify-patch-toggle');
const sseIndicator = document.getElementById('sse-indicator');
const sseStatusText = document.getElementById('sse-status-text');
const reconnectBtn = document.getElementById('reconnect-btn');
const pairCodeDisplay = document.getElementById('pair-code');
const pairExpires = document.getElementById('pair-expires');
const createPairBtn = document.getElementById('create-pair-btn');

/**
 * Load and display config.
 */
async function loadConfig() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getConfig' });
    if (hubUrlInput) hubUrlInput.value = response?.hubUrl || 'http://127.0.0.1:7337';
    if (autoPullToggle) autoPullToggle.checked = response?.autoPull || false;
    if (notifyPatchToggle) notifyPatchToggle.checked = response?.notifyOnPatch || false;
  } catch (e) {
    console.error('Failed to load config:', e);
  }
}

/**
 * Save config.
 */
async function saveConfig() {
  const hubUrl = hubUrlInput?.value?.trim() || 'http://127.0.0.1:7337';
  const autoPull = autoPullToggle?.checked || false;
  const notifyOnPatch = notifyPatchToggle?.checked || false;
  
  try {
    await chrome.runtime.sendMessage({
      action: 'setConfig',
      config: { hubUrl, autoPull, notifyOnPatch }
    });
  } catch (e) {
    console.error('Failed to save config:', e);
  }
  
  if (saveBtn) {
    saveBtn.textContent = 'Saved!';
    setTimeout(() => {
      if (saveBtn) saveBtn.textContent = 'Save';
    }, 1500);
  }
  
  checkHealth();
}

/**
 * Test hub connection.
 */
async function testConnection() {
  const hubUrl = hubUrlInput?.value?.trim() || 'http://127.0.0.1:7337';
  
  if (testBtn) testBtn.textContent = 'Testing...';
  
  try {
    const response = await fetch(`${hubUrl}/health`);
    if (response.ok) {
      const data = await response.json();
      if (testBtn) testBtn.textContent = 'OK!';
      updateStatus(true, `Connected (${data.version || 'ok'})`);
    } else {
      if (testBtn) testBtn.textContent = 'Failed';
      updateStatus(false, `HTTP ${response.status}`);
    }
  } catch (error) {
    if (testBtn) testBtn.textContent = 'Error';
    updateStatus(false, error.message);
  }
  
  setTimeout(() => {
    if (testBtn) testBtn.textContent = 'Test';
  }, 2000);
}

/**
 * Check hub health via background script.
 */
async function checkHealth() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'checkHealth' });
    if (response && response.healthy) {
      updateStatus(true, `Connected (${response.data?.version || 'ok'})`);
    } else {
      updateStatus(false, response?.error || 'Disconnected');
    }
  } catch (e) {
    updateStatus(false, 'Extension error');
  }
}

/**
 * Update status display.
 */
function updateStatus(ok, text) {
  if (statusDot) {
    statusDot.classList.toggle('ok', ok);
    statusDot.classList.toggle('error', !ok);
  }
  if (statusText) statusText.textContent = text;
  
  if (ok) {
    if (sseIndicator) sseIndicator.classList.add('active');
    if (sseStatusText) sseStatusText.textContent = 'SSE: Active';
  } else {
    if (sseIndicator) sseIndicator.classList.remove('active');
    if (sseStatusText) sseStatusText.textContent = 'SSE: Disconnected';
  }
}

/**
 * Get current tab's thread ID.
 */
async function getThreadId() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      const match = tab.url.match(/\/c\/([a-f0-9-]+)/i);
      if (match) {
        return match[1];
      }
    }
  } catch (e) {
    console.error('Failed to get thread ID:', e);
  }
  return '-';
}

/**
 * Clear cursor for current session.
 */
async function clearCursor() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    alert('No thread ID found');
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  
  try {
    await chrome.runtime.sendMessage({
      action: 'setCursor',
      sessionId,
      cursor: 0
    });
    
    await chrome.runtime.sendMessage({
      action: 'clearUpdates',
      sessionId
    });
  } catch (e) {
    console.error('Failed to clear cursor:', e);
  }
  
  if (clearCursorBtn) {
    clearCursorBtn.textContent = 'Cleared!';
    setTimeout(() => {
      if (clearCursorBtn) clearCursorBtn.textContent = 'Clear Cursor';
    }, 1500);
  }
}

/**
 * Open hub in new tab.
 */
function openHub() {
  const hubUrl = hubUrlInput?.value?.trim() || 'http://127.0.0.1:7337';
  chrome.tabs.create({ url: hubUrl });
}

/**
 * Update SSE status display.
 */
async function updateSSEStatus() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    if (sseStatusText) sseStatusText.textContent = 'SSE: No session';
    if (sseIndicator) sseIndicator.classList.remove('active');
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  
  let state = null;
  let updateCount = 0;
  
  try {
    const stateResponse = await chrome.runtime.sendMessage({
      action: 'getSessionState',
      sessionId
    });
    state = stateResponse?.state;
    
    const countResponse = await chrome.runtime.sendMessage({
      action: 'getUpdateCount',
      sessionId
    });
    updateCount = countResponse?.count || 0;
  } catch (e) {
    console.error('Failed to get SSE status:', e);
  }
  
  if (state?.status === 'connected') {
    if (sseIndicator) {
      sseIndicator.classList.add('active');
      sseIndicator.style.background = '#10b981';
    }
    if (sseStatusText) {
      sseStatusText.textContent = updateCount > 0 
        ? `SSE: ${updateCount} update(s)` 
        : 'SSE: Connected';
    }
  } else if (state?.status === 'stale') {
    if (sseIndicator) {
      sseIndicator.classList.remove('active');
      sseIndicator.style.background = '#f59e0b';
    }
    if (sseStatusText) sseStatusText.textContent = 'SSE: Stale (paused)';
  } else if (state?.status === 'reconnecting') {
    if (sseIndicator) {
      sseIndicator.classList.remove('active');
      sseIndicator.style.background = '#f59e0b';
    }
    if (sseStatusText) sseStatusText.textContent = 'SSE: Reconnecting...';
  } else if (state?.status === 'connecting') {
    if (sseIndicator) {
      sseIndicator.classList.remove('active');
      sseIndicator.style.background = '#3b82f6';
    }
    if (sseStatusText) sseStatusText.textContent = 'SSE: Connecting...';
  } else {
    if (sseIndicator) {
      sseIndicator.classList.remove('active');
      sseIndicator.style.background = '#6b7280';
    }
    if (sseStatusText) sseStatusText.textContent = 'SSE: Disconnected';
  }
}

/**
 * Reconnect SSE for current session.
 */
async function reconnectSSE() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  
  if (reconnectBtn) reconnectBtn.textContent = 'Reconnecting...';
  
  try {
    await chrome.runtime.sendMessage({
      action: 'reconnect',
      sessionId
    });
  } catch (e) {
    console.error('Failed to reconnect:', e);
  }
  
  setTimeout(() => {
    if (reconnectBtn) reconnectBtn.textContent = 'Reconnect';
    updateSSEStatus();
  }, 1000);
}

/**
 * Create a pairing code for the current session.
 */
async function createPairCode() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    if (pairCodeDisplay) pairCodeDisplay.textContent = 'No session';
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  
  let config;
  try {
    config = await chrome.runtime.sendMessage({ action: 'getConfig' });
  } catch (e) {
    console.error('Failed to get config:', e);
    if (pairCodeDisplay) pairCodeDisplay.textContent = 'Error';
    return;
  }
  
  if (createPairBtn) {
    createPairBtn.textContent = 'Creating...';
    createPairBtn.disabled = true;
  }
  
  try {
    const hubUrl = config?.hubUrl || 'http://127.0.0.1:7337';
    const response = await fetch(`${hubUrl}/v1/pair/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        ttl_minutes: 10
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    if (pairCodeDisplay) {
      pairCodeDisplay.textContent = data.code;
      pairCodeDisplay.style.fontSize = '24px';
      pairCodeDisplay.style.fontWeight = 'bold';
      pairCodeDisplay.style.color = '#10b981';
    }
    
    startPairCountdown(data.expires_at);
    
    if (createPairBtn) {
      createPairBtn.textContent = 'Refresh Code';
      createPairBtn.disabled = false;
    }
  } catch (error) {
    console.error('Failed to create pair code:', error);
    if (pairCodeDisplay) pairCodeDisplay.textContent = 'Error';
    if (createPairBtn) {
      createPairBtn.textContent = 'Create Pair Code';
      createPairBtn.disabled = false;
    }
  }
}

/**
 * Start countdown timer for pairing code expiration.
 */
function startPairCountdown(expiresAt) {
  if (window.pairCountdownInterval) {
    clearInterval(window.pairCountdownInterval);
  }
  
  const updateCountdown = () => {
    const now = new Date();
    const expiresStr = expiresAt.endsWith('Z') ? expiresAt : expiresAt + 'Z';
    const expires = new Date(expiresStr);
    const remaining = Math.max(0, expires - now);
    
    if (remaining === 0) {
      if (pairExpires) pairExpires.textContent = '(expired)';
      if (pairCodeDisplay) pairCodeDisplay.style.color = '#6b7280';
      clearInterval(window.pairCountdownInterval);
      return;
    }
    
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    if (pairExpires) {
      pairExpires.textContent = `(${minutes}:${seconds.toString().padStart(2, '0')})`;
    }
  };
  
  updateCountdown();
  window.pairCountdownInterval = setInterval(updateCountdown, 1000);
}


// Event listeners
if (saveBtn) saveBtn.addEventListener('click', saveConfig);
if (testBtn) testBtn.addEventListener('click', testConnection);
if (clearCursorBtn) clearCursorBtn.addEventListener('click', clearCursor);
if (openHubBtn) openHubBtn.addEventListener('click', openHub);
if (reconnectBtn) reconnectBtn.addEventListener('click', reconnectSSE);
if (autoPullToggle) autoPullToggle.addEventListener('change', saveConfig);
if (notifyPatchToggle) notifyPatchToggle.addEventListener('change', saveConfig);
if (createPairBtn) createPairBtn.addEventListener('click', createPairCode);

// Initialize
loadConfig();
checkHealth();
getThreadId().then(id => {
  if (threadIdEl) threadIdEl.textContent = id || '-';
});
updateSSEStatus();

// Periodically update SSE status
setInterval(updateSSEStatus, 5000);
