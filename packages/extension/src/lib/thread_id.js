/**
 * Thread ID extraction for ChatGPT.
 * 
 * Extracts thread ID from URL or generates/stores a per-tab ID.
 */

(function() {
  'use strict';

  /**
   * Extract thread ID from ChatGPT URL.
   * URLs are like: https://chatgpt.com/c/<thread_id>
   * or: https://chat.openai.com/c/<thread_id>
   * 
   * @returns {string|null} Thread ID or null if not found
   */
  function extractThreadId() {
    const url = window.location.href;
    
    // Match /c/<thread_id> pattern
    const match = url.match(/\/c\/([a-f0-9-]+)/i);
    if (match && match[1]) {
      return match[1];
    }
    
    // Try alternative patterns
    // Some URLs might have /chat/<id>
    const chatMatch = url.match(/\/chat\/([a-f0-9-]+)/i);
    if (chatMatch && chatMatch[1]) {
      return chatMatch[1];
    }
    
    // Try query parameter (fallback for some versions)
    const urlParams = new URLSearchParams(window.location.search);
    const threadParam = urlParams.get('thread') || urlParams.get('id');
    if (threadParam) {
      return threadParam;
    }
    
    return null;
  }

  /**
   * Get session ID for Council Hub.
   * Format: "cgpt:<thread_id>"
   * 
   * @returns {string} Session ID
   */
  function getSessionId() {
    const threadId = extractThreadId();
    if (threadId) {
      return `cgpt:${threadId}`;
    }
    
    // Generate UUID for this tab if no thread ID
    // Store in sessionStorage for persistence during tab lifetime
    let tabSessionId = sessionStorage.getItem('council_tab_session');
    if (!tabSessionId) {
      tabSessionId = `cgpt:tab-${generateUUID()}`;
      sessionStorage.setItem('council_tab_session', tabSessionId);
    }
    return tabSessionId;
  }

  /**
   * Generate a simple UUID v4.
   * 
   * @returns {string} UUID
   */
  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  // Export to window for use in content script
  window.CouncilThread = {
    extractThreadId,
    getSessionId,
    generateUUID
  };
})();
