/**
 * Council Extension Content Script
 * 
 * Injects UI into ChatGPT and handles Sync/Pull operations.
 */

(function() {
  'use strict';

  let toolbar = null;
  let statusIndicator = null;

  /**
   * Create the toolbar UI.
   */
  function createToolbar() {
    if (toolbar) return toolbar;

    toolbar = document.createElement('div');
    toolbar.id = 'council-toolbar';
    toolbar.innerHTML = `
      <div class="council-toolbar-inner">
        <div class="council-status" title="Hub status">
          <span class="council-status-dot"></span>
        </div>
        <button class="council-btn council-btn-sync" title="Sync selected text or last messages to Council Hub">
          <span class="council-icon">↑</span>
          Sync → Council
        </button>
        <button class="council-btn council-btn-pull" title="Pull digest from Council Hub">
          <span class="council-icon">↓</span>
          Pull ← Council
        </button>
      </div>
    `;

    // Find insertion point - near the composer
    const composer = window.CouncilDOM.getComposer();
    let container = composer?.parentElement?.parentElement;
    
    if (!container) {
      // Fallback: insert at top of main area
      container = document.querySelector('main') || document.body;
    }

    // Insert before composer's parent container
    const composerContainer = composer?.closest('[class*="composer"]') || 
                              composer?.parentElement?.parentElement?.parentElement;
    
    if (composerContainer?.parentElement) {
      composerContainer.parentElement.insertBefore(toolbar, composerContainer);
    } else {
      container.appendChild(toolbar);
    }

    // Wire up events
    const syncBtn = toolbar.querySelector('.council-btn-sync');
    const pullBtn = toolbar.querySelector('.council-btn-pull');
    statusIndicator = toolbar.querySelector('.council-status-dot');

    syncBtn.addEventListener('click', handleSync);
    pullBtn.addEventListener('click', handlePull);

    return toolbar;
  }

  /**
   * Update status indicator color.
   */
  async function updateStatus() {
    if (!statusIndicator) return;

    const response = await chrome.runtime.sendMessage({ action: 'checkHealth' });
    
    if (response && response.healthy) {
      statusIndicator.classList.remove('council-status-error');
      statusIndicator.classList.add('council-status-ok');
      statusIndicator.title = 'Council Hub: Connected';
    } else {
      statusIndicator.classList.remove('council-status-ok');
      statusIndicator.classList.add('council-status-error');
      statusIndicator.title = `Council Hub: ${response?.error || 'Disconnected'}`;
    }
  }

  /**
   * Handle Sync button click.
   */
  async function handleSync() {
    const sessionId = window.CouncilThread.getSessionId();
    
    // Check for selected text first
    const selectedText = window.CouncilDOM.getSelectedText();
    
    let events = [];
    
    if (selectedText) {
      // Sync selected text as user message
      events.push(window.CouncilFormat.formatMessageForSync(selectedText, 'user', {
        url: window.location.href,
        thread_id: window.CouncilThread.extractThreadId(),
        source: 'selection'
      }));
    } else {
      // Get last user and assistant messages
      const messages = window.CouncilDOM.getLastMessages(2);
      
      if (messages.length === 0) {
        window.CouncilDOM.showToast('No messages to sync', 'error');
        return;
      }
      
      for (const msg of messages) {
        events.push(window.CouncilFormat.formatMessageForSync(
          msg.content,
          msg.role,
          {
            url: window.location.href,
            thread_id: window.CouncilThread.extractThreadId()
          }
        ));
      }
    }
    
    // Send to background script
    try {
      const response = await chrome.runtime.sendMessage({
        action: 'sync',
        sessionId,
        events
      });
      
      if (response.success) {
        window.CouncilDOM.showToast(`Synced ${events.length} message(s)`, 'success');
      } else {
        window.CouncilDOM.showToast(`Sync failed: ${response.error}`, 'error');
      }
    } catch (error) {
      window.CouncilDOM.showToast(`Sync error: ${error.message}`, 'error');
    }
  }

  /**
   * Handle Pull button click.
   */
  async function handlePull() {
    const sessionId = window.CouncilThread.getSessionId();
    
    try {
      const response = await chrome.runtime.sendMessage({
        action: 'pull',
        sessionId
      });
      
      if (response.success) {
        const formattedDigest = window.CouncilFormat.formatDigest(
          response.digest,
          sessionId
        );
        
        // Insert into composer
        const inserted = window.CouncilDOM.insertIntoComposer(formattedDigest);
        
        if (inserted) {
          window.CouncilDOM.showToast(
            `Pulled updates (cursor: ${response.nextCursor})`,
            'success'
          );
        } else {
          window.CouncilDOM.showToast('Could not insert into composer', 'error');
        }
      } else {
        window.CouncilDOM.showToast(`Pull failed: ${response.error}`, 'error');
      }
    } catch (error) {
      window.CouncilDOM.showToast(`Pull error: ${error.message}`, 'error');
    }
  }

  /**
   * Initialize the extension.
   */
  function init() {
    // Wait for page to be ready
    const checkReady = setInterval(() => {
      if (window.CouncilDOM.isPageReady()) {
        clearInterval(checkReady);
        
        // Create toolbar
        createToolbar();
        
        // Update status
        updateStatus();
        
        // Periodically update status
        setInterval(updateStatus, 30000);
        
        console.log('[Council] Extension initialized');
      }
    }, 500);

    // Timeout after 30 seconds
    setTimeout(() => {
      clearInterval(checkReady);
    }, 30000);
  }

  // Listen for messages from background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'syncSelection') {
      // Handle context menu sync
      const sessionId = window.CouncilThread.getSessionId();
      const event = window.CouncilFormat.formatMessageForSync(message.text, 'user', {
        url: window.location.href,
        source: 'context-menu'
      });
      
      chrome.runtime.sendMessage({
        action: 'sync',
        sessionId,
        events: [event]
      }).then(response => {
        if (response.success) {
          window.CouncilDOM.showToast('Synced selection', 'success');
        }
      });
    }
    sendResponse({ received: true });
    return true;
  });

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
