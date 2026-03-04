/**
 * Cursor storage utilities using chrome.storage.local.
 */

(function() {
  'use strict';

  const STORAGE_KEY_PREFIX = 'council_cursor_';
  const CONFIG_KEY = 'council_config';

  /**
   * Get the cursor for a session.
   * 
   * @param {string} sessionId - Session ID
   * @returns {Promise<number>} Cursor value (0 if not set)
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
   * Set the cursor for a session.
   * 
   * @param {string} sessionId - Session ID
   * @param {number} cursor - Cursor value
   * @returns {Promise<void>}
   */
  async function setCursor(sessionId, cursor) {
    const key = STORAGE_KEY_PREFIX + sessionId;
    return new Promise((resolve) => {
      chrome.storage.local.set({ [key]: cursor }, resolve);
    });
  }

  /**
   * Clear the cursor for a session.
   * 
   * @param {string} sessionId - Session ID
   * @returns {Promise<void>}
   */
  async function clearCursor(sessionId) {
    const key = STORAGE_KEY_PREFIX + sessionId;
    return new Promise((resolve) => {
      chrome.storage.local.remove([key], resolve);
    });
  }

  /**
   * Get extension configuration.
   * 
   * @returns {Promise<Object>} Config object
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
   * Set extension configuration.
   * 
   * @param {Object} config - Config object
   * @returns {Promise<void>}
   */
  async function setConfig(config) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [CONFIG_KEY]: config }, resolve);
    });
  }

  /**
   * Get hub URL from config.
   * 
   * @returns {Promise<string>} Hub URL
   */
  async function getHubUrl() {
    const config = await getConfig();
    return config.hubUrl || 'http://127.0.0.1:7337';
  }

  // Export (for use in background script via importScripts or module)
  window.CouncilStorage = {
    getCursor,
    setCursor,
    clearCursor,
    getConfig,
    setConfig,
    getHubUrl
  };
})();
