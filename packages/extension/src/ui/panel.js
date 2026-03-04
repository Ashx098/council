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
  
  // Check if we have updates pending
  const sessionId = `cgpt:${threadId}`;
  const response = await chrome.runtime.sendMessage({
    action: 'getUpdateCount',
    sessionId
  });
  
  if (response && response.count > 0) {
    sseStatusText.textContent = `SSE: ${response.count} update(s)`;
  } else {
    sseStatusText.textContent = 'SSE: Active';
  }
}

// Event listeners
saveBtn.addEventListener('click', saveConfig);
testBtn.addEventListener('click', testConnection);
clearCursorBtn.addEventListener('click', clearCursor);
openHubBtn.addEventListener('click', openHub);

// Toggle listeners
autoPullToggle.addEventListener('change', saveConfig);
notifyPatchToggle.addEventListener('change', saveConfig);

// Initialize
loadConfig();
checkHealth();
getThreadId().then(id => {
  threadIdEl.textContent = id || '-';
});
updateSSEStatus();

// Periodically update SSE status
setInterval(updateSSEStatus, 5000);
