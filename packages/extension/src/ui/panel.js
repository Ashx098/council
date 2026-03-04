/**
 * Council Extension Panel Script
 * 
 * Handles the popup panel UI.
 */

// Elements
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
  const response = await chrome.runtime.sendMessage({ action: 'getConfig' });
  hubUrlInput.value = response.hubUrl || 'http://127.0.0.1:7337';
  
  // Load toggle states
  autoPullToggle.checked = response.autoPull || false;
  notifyPatchToggle.checked = response.notifyOnPatch || false;
}

/**
 * Save config.
 */
async function saveConfig() {
  const hubUrl = hubUrlInput.value.trim();
  const autoPull = autoPullToggle.checked;
  const notifyOnPatch = notifyPatchToggle.checked;
  
  await chrome.runtime.sendMessage({
    action: 'setConfig',
    config: { hubUrl, autoPull, notifyOnPatch }
  });
  
  // Visual feedback
  saveBtn.textContent = 'Saved!';
  setTimeout(() => {
    saveBtn.textContent = 'Save';
  }, 1500);
  
  // Re-check health
  checkHealth();
}

/**
 * Test hub connection.
 */
async function testConnection() {
  const hubUrl = hubUrlInput.value.trim();
  
  testBtn.textContent = 'Testing...';
  
  try {
    const response = await fetch(`${hubUrl}/health`);
    if (response.ok) {
      const data = await response.json();
      testBtn.textContent = 'OK!';
      updateStatus(true, `Connected (${data.version || 'ok'})`);
    } else {
      testBtn.textContent = 'Failed';
      updateStatus(false, `HTTP ${response.status}`);
    }
  } catch (error) {
    testBtn.textContent = 'Error';
    updateStatus(false, error.message);
  }
  
  setTimeout(() => {
    testBtn.textContent = 'Test';
  }, 2000);
}

/**
 * Check hub health via background script.
 */
async function checkHealth() {
  const response = await chrome.runtime.sendMessage({ action: 'checkHealth' });
  
  if (response && response.healthy) {
    updateStatus(true, `Connected (${response.data?.version || 'ok'})`);
  } else {
    updateStatus(false, response?.error || 'Disconnected');
  }
}

/**
 * Update status display.
 */
function updateStatus(ok, text) {
  statusDot.classList.toggle('ok', ok);
  statusDot.classList.toggle('error', !ok);
  statusText.textContent = text;
  
  // Update SSE indicator
  if (ok) {
    sseIndicator.classList.add('active');
    sseStatusText.textContent = 'SSE: Active';
  } else {
    sseIndicator.classList.remove('active');
    sseStatusText.textContent = 'SSE: Disconnected';
  }
}

/**
 * Get current tab's thread ID.
 */
async function getThreadId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (tab && tab.url) {
    const match = tab.url.match(/\/c\/([a-f0-9-]+)/i);
    if (match) {
      return match[1];
    }
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
  
  await chrome.runtime.sendMessage({
    action: 'setCursor',
    sessionId,
    cursor: 0
  });
  
  // Also clear updates
  await chrome.runtime.sendMessage({
    action: 'clearUpdates',
    sessionId
  });
  
  clearCursorBtn.textContent = 'Cleared!';
  setTimeout(() => {
    clearCursorBtn.textContent = 'Clear Cursor';
  }, 1500);
}

/**
 * Open hub in new tab.
 */
function openHub() {
  const hubUrl = hubUrlInput.value.trim();
  chrome.tabs.create({ url: hubUrl });
}

/**
 * Update SSE status display.
 */
async function updateSSEStatus() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    sseStatusText.textContent = 'SSE: No session';
    sseIndicator.classList.remove('active');
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  
  // Get session state
  const stateResponse = await chrome.runtime.sendMessage({
    action: 'getSessionState',
    sessionId
  });
  
  // Get update count
  const countResponse = await chrome.runtime.sendMessage({
    action: 'getUpdateCount',
    sessionId
  });
  
  const state = stateResponse?.state;
  const updateCount = countResponse?.count || 0;
  
  // Update indicator based on status
  if (state?.status === 'connected') {
    sseIndicator.classList.add('active');
    sseIndicator.style.background = '#10b981';
    
    if (updateCount > 0) {
      sseStatusText.textContent = `SSE: ${updateCount} update(s)`;
    } else {
      sseStatusText.textContent = 'SSE: Connected';
    }
  } else if (state?.status === 'stale') {
    sseIndicator.classList.remove('active');
    sseIndicator.style.background = '#f59e0b';
    sseStatusText.textContent = 'SSE: Stale (paused)';
  } else if (state?.status === 'reconnecting') {
    sseIndicator.classList.remove('active');
    sseIndicator.style.background = '#f59e0b';
    sseStatusText.textContent = 'SSE: Reconnecting...';
  } else if (state?.status === 'connecting') {
    sseIndicator.classList.remove('active');
    sseIndicator.style.background = '#3b82f6';
    sseStatusText.textContent = 'SSE: Connecting...';
  } else {
    sseIndicator.classList.remove('active');
    sseIndicator.style.background = '#6b7280';
    sseStatusText.textContent = 'SSE: Disconnected';
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
  
  reconnectBtn.textContent = 'Reconnecting...';
  
  await chrome.runtime.sendMessage({
    action: 'reconnect',
    sessionId
  });
  
  setTimeout(() => {
    reconnectBtn.textContent = 'Reconnect';
    updateSSEStatus();
  }, 1000);
}

/**
 * Create a pairing code for the current session.
 */
async function createPairCode() {
  const threadId = await getThreadId();
  
  if (threadId === '-') {
    pairCodeDisplay.textContent = 'No session';
    return;
  }
  
  const sessionId = `cgpt:${threadId}`;
  const config = await getConfig();
  
  createPairBtn.textContent = 'Creating...';
  createPairBtn.disabled = true;
  
  try {
    const response = await fetch(`${config.hubUrl}/v1/pair/create`, {
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
    
    // Display the code
    pairCodeDisplay.textContent = data.code;
    pairCodeDisplay.style.fontSize = '24px';
    pairCodeDisplay.style.fontWeight = 'bold';
    pairCodeDisplay.style.color = '#10b981';
    
    // Start countdown
    startPairCountdown(data.expires_at);
    
    createPairBtn.textContent = 'Refresh Code';
    createPairBtn.disabled = false;
  } catch (error) {
    console.error('Failed to create pair code:', error);
    pairCodeDisplay.textContent = 'Error';
    createPairBtn.textContent = 'Create Pair Code';
    createPairBtn.disabled = false;
  }
}

/**
 * Start countdown timer for pairing code expiration.
 */
function startPairCountdown(expiresAt) {
  // Clear any existing interval
  if (window.pairCountdownInterval) {
    clearInterval(window.pairCountdownInterval);
  }
  
  const updateCountdown = () => {
    const now = new Date();
    const expires = new Date(expiresAt);
    const remaining = Math.max(0, expires - now);
    
    if (remaining === 0) {
      pairExpires.textContent = '(expired)';
      pairCodeDisplay.style.color = '#6b7280';
      clearInterval(window.pairCountdownInterval);
      return;
    }
    
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    pairExpires.textContent = `(${minutes}:${seconds.toString().padStart(2, '0')})`;
  };
  
  updateCountdown();
  window.pairCountdownInterval = setInterval(updateCountdown, 1000);
}


// Event listeners
if (saveBtn) saveBtn.addEventListener('click', saveConfig);
if (testBtn) testBtn.addEventListener('click', testConnection);
if (clearCursorBtn) clearCursorBtn.addEventListener('click', clearCursor);
if (openHubBtn) openHubBtn.addEventListener('click', openHub);
if (reconnectBtn) {
  reconnectBtn.addEventListener('click', reconnectSSE);
}

// Toggle listeners
if (autoPullToggle) autoPullToggle.addEventListener('change', saveConfig);
if (notifyPatchToggle) notifyPatchToggle.addEventListener('change', saveConfig);
if (createPairBtn) {
  createPairBtn.addEventListener('click', createPairCode);
}
// Initialize
loadConfig();
checkHealth();
getThreadId().then(id => {
  threadIdEl.textContent = id || '-';
});
updateSSEStatus();

// Periodically update SSE status
setInterval(updateSSEStatus, 5000);
