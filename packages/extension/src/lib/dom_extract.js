/**
 * DOM extraction utilities for ChatGPT pages.
 * 
 * Handles extraction of messages and composer manipulation.
 * Designed to be resilient to minor DOM changes.
 */

(function() {
  'use strict';

  // Multiple selector strategies for resilience
  const SELECTORS = {
    // Chat messages
    messages: [
      '[data-testid="conversation-turn"]',
      '.text-base.gap-4',  // Fallback
      '.group.w-full',      // Another fallback
      '[class*="conversation-turn"]'
    ],
    
    // User messages within a turn
    userMessage: [
      '[data-testid="user-message"]',
      '.whitespace-pre-wrap.font-user',
      '[class*="user-message"]'
    ],
    
    // Assistant messages within a turn
    assistantMessage: [
      '[data-testid="assistant-message"]',
      '.markdown.prose',
      '[class*="assistant-message"]'
    ],
    
    // Input composer
    composer: [
      '#prompt-textarea',
      'textarea[placeholder*="Message"]',
      'div[contenteditable="true"]',
      'textarea'
    ],
    
    // Send button (for detecting ready state)
    sendButton: [
      '[data-testid="send-button"]',
      'button[data-testid="fruitjuice-send-button"]',
      'button[aria-label="Send"]'
    ],
    
    // Chat container
    chatContainer: [
      '[data-testid="conversation-panel"]',
      '.flex-1.overflow-hidden',
      'main'
    ]
  };

  /**
   * Try multiple selectors until one works.
   * 
   * @param {string[]} selectors - List of CSS selectors to try
   * @param {Element} root - Root element to search from
   * @returns {Element|null} First matching element or null
   */
  function trySelectors(selectors, root = document) {
    for (const selector of selectors) {
      try {
        const element = root.querySelector(selector);
        if (element) return element;
      } catch (e) {
        // Invalid selector, skip
        console.warn(`[Council] Invalid selector: ${selector}`);
      }
    }
    return null;
  }

  /**
   * Try multiple selectors, returning all matches.
   * 
   * @param {string[]} selectors - List of CSS selectors to try
   * @param {Element} root - Root element to search from
   * @returns {Element[]} All matching elements
   */
  function trySelectorsAll(selectors, root = document) {
    for (const selector of selectors) {
      try {
        const elements = root.querySelectorAll(selector);
        if (elements.length > 0) return Array.from(elements);
      } catch (e) {
        console.warn(`[Council] Invalid selector: ${selector}`);
      }
    }
    return [];
  }

  /**
   * Get the last N message turns from the conversation.
   * 
   * @param {number} count - Number of turns to get
   * @returns {Array<{role: string, content: string}>} Messages
   */
  function getLastMessages(count = 2) {
    const turns = trySelectorsAll(SELECTORS.messages);
    const messages = [];

    // Get last N turns
    const lastTurns = turns.slice(-count);

    for (const turn of lastTurns) {
      // Try to find user message
      const userEl = trySelectors(SELECTORS.userMessage, turn);
      if (userEl) {
        messages.push({
          role: 'user',
          content: userEl.textContent.trim()
        });
        continue;
      }

      // Try to find assistant message
      const assistantEl = trySelectors(SELECTORS.assistantMessage, turn);
      if (assistantEl) {
        messages.push({
          role: 'assistant',
          content: assistantEl.textContent.trim()
        });
      }
    }

    return messages;
  }

  /**
   * Get selected text on the page.
   * 
   * @returns {string} Selected text or empty string
   */
  function getSelectedText() {
    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      return selection.toString().trim();
    }
    return '';
  }

  /**
   * Get the composer element.
   * 
   * @returns {Element|null} Composer element
   */
  function getComposer() {
    return trySelectors(SELECTORS.composer);
  }

  /**
   * Insert text into the ChatGPT composer.
   * 
   * @param {string} text - Text to insert
   * @returns {boolean} Success
   */
  function insertIntoComposer(text) {
    const composer = getComposer();
    if (!composer) {
      console.error('[Council] Could not find composer element');
      return false;
    }

    // Handle textarea
    if (composer.tagName === 'TEXTAREA') {
      composer.value = text;
      composer.focus();
      // Dispatch events to trigger UI update
      composer.dispatchEvent(new Event('input', { bubbles: true }));
      composer.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }

    // Handle contenteditable
    if (composer.getAttribute('contenteditable') === 'true') {
      // Clear existing content
      composer.textContent = text;
      composer.focus();
      
      // Move cursor to end
      const range = document.createRange();
      range.selectNodeContents(composer);
      range.collapse(false);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      
      // Dispatch events
      composer.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    }

    console.error('[Council] Unknown composer type:', composer.tagName);
    return false;
  }

  /**
   * Check if the page is ready for interaction.
   * 
   * @returns {boolean} Ready state
   */
  function isPageReady() {
    return getComposer() !== null;
  }

  /**
   * Create a toast notification.
   * 
   * @param {string} message - Message to show
   * @param {string} type - 'success', 'error', or 'info'
   */
  function showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.getElementById('council-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'council-toast';
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 8px;
      font-family: system-ui, sans-serif;
      font-size: 14px;
      z-index: 100000;
      animation: council-fade-in 0.3s ease;
      max-width: 300px;
    `;

    const colors = {
      success: 'background: #10b981; color: white;',
      error: 'background: #ef4444; color: white;',
      info: 'background: #3b82f6; color: white;'
    };
    toast.style.cssText += colors[type] || colors.info;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
      toast.style.animation = 'council-fade-out 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // Export to window
  window.CouncilDOM = {
    getLastMessages,
    getSelectedText,
    getComposer,
    insertIntoComposer,
    isPageReady,
    showToast,
    trySelectors,
    trySelectorsAll,
    SELECTORS
  };
})();
