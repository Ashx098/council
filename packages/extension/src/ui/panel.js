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

/**
 * Load and display config.
 */
async function loadConfig() {
  const response = await chrome.runtime.sendMessage({ action: 'getConfig' });
  hubUrlInput.value = response.hubUrl || 'http://127.0.0.1:7337';
}

/**
 * Save config.
 */
async function saveConfig() {
  const hubUrl = hubUrlInput.value.trim();
  
  await chrome.runtime.sendMessage({
    action: 'setConfig',
    config: { hubUrl }
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

// Event listeners
saveBtn.addEventListener('click', saveConfig);
testBtn.addEventListener('click', testConnection);
clearCursorBtn.addEventListener('click', clearCursor);
openHubBtn.addEventListener('click', openHub);

// Initialize
loadConfig();
checkHealth();
getThreadId().then(id => {
  threadIdEl.textContent = id || '-';
});
