/**
 * Digest formatting utilities.
 * 
 * Makes the digest readable and bounded for pasting into ChatGPT.
 */

(function() {
  'use strict';

  /**
   * Format a digest for pasting into ChatGPT.
   * 
   * @param {Object} digestResult - Result from hub digest endpoint
   * @param {string} sessionId - Session ID
   * @returns {string} Formatted digest text
   */
  function formatDigest(digestResult, sessionId) {
    const lines = [];
    
    // Header
    lines.push('═══════════════════════════════════════');
    lines.push('📋 COUNCIL UPDATES');
    lines.push(`Session: ${sessionId || 'unknown'}`);
    lines.push('═══════════════════════════════════════');
    lines.push('');
    
    // Main digest content
    if (digestResult.digest_text) {
      lines.push(digestResult.digest_text);
    } else {
      lines.push('(No new updates)');
    }
    
    // Footer with cursor info
    lines.push('');
    lines.push('───────────────────────────────────────');
    lines.push(`Cursor: ${digestResult.next_cursor}`);
    if (digestResult.has_more) {
      lines.push('(More updates available - pull again)');
    }
    lines.push('═══════════════════════════════════════');
    
    return lines.join('\n');
  }

  /**
   * Truncate text to a maximum length.
   * 
   * @param {string} text - Text to truncate
   * @param {number} maxLen - Maximum length
   * @returns {string} Truncated text
   */
  function truncate(text, maxLen = 4000) {
    if (!text || text.length <= maxLen) return text || '';
    return text.slice(0, maxLen - 3) + '...';
  }

  /**
   * Format a message for syncing to hub.
   * 
   * @param {string} content - Message content
   * @param {string} role - 'user' or 'assistant'
   * @param {Object} meta - Additional metadata
   * @returns {Object} Formatted message object
   */
  function formatMessageForSync(content, role, meta = {}) {
    return {
      source: role === 'user' ? 'user' : 'chatgpt',
      type: 'message',
      body: truncate(content, 4000),
      meta: {
        ...meta,
        role: role,
        ts: new Date().toISOString()
      }
    };
  }

  /**
   * Create a summary of events for display.
   * 
   * @param {Array} events - Events from hub
   * @returns {string} Summary text
   */
  function summarizeEvents(events) {
    if (!events || events.length === 0) {
      return 'No events';
    }

    const counts = {};
    for (const event of events) {
      counts[event.type] = (counts[event.type] || 0) + 1;
    }

    const parts = [];
    for (const [type, count] of Object.entries(counts)) {
      parts.push(`${count} ${type}`);
    }

    return `${events.length} events: ${parts.join(', ')}`;
  }

  // Export to window
  window.CouncilFormat = {
    formatDigest,
    truncate,
    formatMessageForSync,
    summarizeEvents
  };
})();
