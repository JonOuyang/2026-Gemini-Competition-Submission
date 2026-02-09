/**
 * Status Bubble - Agent status indicator
 *
 * Shows/hides the status bubble at the top of the screen.
 * Used to display agent activity like "Opening file...", "Searching online..."
 */

(function() {
  const statusBubble = document.getElementById('status-bubble');
  const statusText = document.getElementById('status-bubble-text');
  const statusIcon = document.getElementById('status-bubble-icon');
  const statusDismiss = document.getElementById('status-bubble-dismiss');

  let hideTimeout = null;
  let completionTimeout = null;
  let isTransitioning = false;
  let finalResponseText = '';
  let isFinalExpanded = false;
  let currentSource = 'unknown';
  let finalSource = 'unknown';
  let currentTheme = null;

  const DEFAULT_DONE_TEXT = 'Task done';
  const DEFAULT_DONE_DELAY = 2000;
  const normalizeSource = (source) =>
    (typeof source === 'string' && source.trim()) ? source.trim() : 'unknown';
  const logStatusText = (channel, text, source = currentSource) => {
    if (channel === 'update') return;
    const safeText = typeof text === 'string' ? text : String(text ?? '');
    console.log(`[renderer][ui_status][${normalizeSource(source)}][${channel}] ${safeText}`);
  };
  const hasSelectionInsideStatusBubble = () => {
    const selection = window.getSelection ? window.getSelection() : null;
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return false;
    }
    const range = selection.getRangeAt(0);
    const container = range.commonAncestorContainer;
    const node = container.nodeType === Node.ELEMENT_NODE
      ? container
      : container.parentElement;
    return !!(node && statusBubble.contains(node));
  };

  const applyTheme = (theme) => {
    if (!theme) return;
    currentTheme = { ...theme };
    statusBubble.style.setProperty('--status-bg', theme.statusBg || '');
    statusBubble.style.setProperty('--status-border', theme.statusBorder || '');
    statusBubble.style.setProperty('--status-text', theme.statusText || '');
    statusBubble.style.setProperty('--status-shimmer', theme.statusShimmer || '');
    statusBubble.style.setProperty('--status-check', theme.statusCheck || '');
    if (theme.icon) {
      statusIcon.setAttribute('data-icon', theme.icon);
    } else {
      statusIcon.setAttribute('data-icon', 'check');
    }
  };

  const clearTimers = () => {
    if (hideTimeout) {
      clearTimeout(hideTimeout);
      hideTimeout = null;
    }
    if (completionTimeout) {
      clearTimeout(completionTimeout);
      completionTimeout = null;
    }
  };

  const resetFinalState = () => {
    isFinalExpanded = false;
    finalResponseText = '';
    finalSource = currentSource;
    statusBubble.classList.remove('status-bubble--interactive', 'status-bubble--expanded', 'status-bubble--pulse');
    statusText.classList.remove('status-bubble-text--final');
    if (statusDismiss) {
      statusDismiss.style.display = 'none';
    }
  };

  const setText = (text, shimmer = true) => {
    const nextText = text || '';
    statusText.classList.remove('rotating-out', 'rotating-in');
    statusText.textContent = nextText;
    statusText.setAttribute('data-text', nextText);
    if (shimmer) {
      statusText.classList.add('status-bubble-text--shimmer');
    } else {
      statusText.classList.remove('status-bubble-text--shimmer');
    }
  };

  const ensureVisible = () => {
    statusBubble.classList.remove('status-bubble--closing');
    statusBubble.setAttribute('aria-hidden', 'false');
    statusBubble.classList.add('status-bubble--visible');
    if (window.overlayCollapseCommandBar) {
      window.overlayCollapseCommandBar();
    }
  };

  const expandWithFinalText = () => {
    statusBubble.classList.add('status-bubble--expanded', 'status-bubble--pulse', 'status-bubble--interactive');
    statusText.classList.add('status-bubble-text--final');
    setText(finalResponseText || 'Task completed.', false);
    isFinalExpanded = true;
    if (statusDismiss) {
      statusDismiss.style.display = 'inline-flex';
    }
  };

  /**
   * Show the status bubble with initial text
   * @param {string} text - The status text to display
   */
  window.showStatusBubble = function(text = 'Working...', theme = null, source = 'unknown') {
    currentSource = normalizeSource(source);
    logStatusText('show', text, currentSource);
    applyTheme(theme);
    clearTimers();
    resetFinalState();
    isTransitioning = false;

    statusIcon.classList.remove('visible');
    setText(text, true);
    if (theme?.icon === 'stop') {
      statusIcon.classList.add('visible');
    }

    ensureVisible();
  };

  /**
   * Update the status bubble text with rotation animation
   * Shows checkmark, pauses, then rotates to new text
   * @param {string} text - The new status text
   */
  window.updateStatusBubble = function(text, theme = null, source = null) {
    if (source !== null && source !== undefined) {
      currentSource = normalizeSource(source);
    }
    logStatusText('update', text, currentSource);
    applyTheme(theme);
    if (!statusBubble.classList.contains('status-bubble--visible')) {
      window.showStatusBubble(text, theme);
      return;
    }

    if (isFinalExpanded || isTransitioning) return;
    isTransitioning = true;

    statusIcon.classList.add('visible');

    setTimeout(() => {
      statusText.classList.remove('rotating-in', 'rotating-out');
      void statusText.offsetWidth;
      statusText.classList.add('rotating-out');

      setTimeout(() => {
        statusIcon.classList.remove('visible');
        setText(text, true);
        statusText.classList.remove('rotating-out', 'rotating-in');
        void statusText.offsetWidth;
        statusText.classList.add('rotating-in');

        const onRotateInEnd = () => {
          statusText.classList.remove('rotating-in');
          statusText.removeEventListener('animationend', onRotateInEnd);
          isTransitioning = false;
        };

        statusText.addEventListener('animationend', onRotateInEnd);
      }, 250);
    }, 500);
  };

  /**
   * Complete the status bubble flow with delayed expansion + final response text.
   * @param {string} responseText - Final model response to display in expanded bubble
   * @param {object} options - Optional done text and delay
   */
  window.completeStatusBubble = function(responseText = '', options = {}) {
    const doneText = options.doneText || DEFAULT_DONE_TEXT;
    const delayMs = Number.isFinite(options.delayMs) ? options.delayMs : DEFAULT_DONE_DELAY;
    currentSource = normalizeSource(options.source ?? currentSource);
    applyTheme(options.theme);
    clearTimers();
    resetFinalState();
    isTransitioning = false;

    finalResponseText = typeof responseText === 'string' && responseText.trim()
      ? responseText.trim()
      : 'Task completed.';
    finalSource = currentSource;
    logStatusText('complete_done', doneText, finalSource);
    logStatusText('complete_response', finalResponseText, finalSource);

    ensureVisible();
    statusIcon.classList.add('visible');
    setText(doneText, false);

    completionTimeout = setTimeout(() => {
      completionTimeout = null;
      expandWithFinalText();
    }, Math.max(0, delayMs));
  };

  /**
   * Hide the status bubble
   * @param {number} delay - Optional delay before hiding (ms)
   */
  window.hideStatusBubble = function(delay = 0) {
    clearTimers();
    resetFinalState();

    hideTimeout = setTimeout(() => {
      statusIcon.classList.add('visible');

      setTimeout(() => {
        statusBubble.classList.add('status-bubble--closing');
        statusBubble.classList.remove('status-bubble--visible');

        setTimeout(() => {
          statusBubble.setAttribute('aria-hidden', 'true');
          statusBubble.classList.remove('status-bubble--closing');
          statusIcon.classList.remove('visible');
          if (window.restoreCommandBar) {
            window.restoreCommandBar();
          }
        }, 300);

        hideTimeout = null;
      }, 250);
    }, delay);
  };

  /**
   * Check if the status bubble is currently visible
   * @returns {boolean}
   */
  window.isStatusBubbleVisible = function() {
    return statusBubble.classList.contains('status-bubble--visible');
  };

  window.getStatusBubbleTheme = function() {
    if (!currentTheme) return null;
    return { ...currentTheme };
  };

  statusBubble.addEventListener('click', (event) => {
    if (!isFinalExpanded) return;
    if (event.target === statusDismiss) return;
    if (hasSelectionInsideStatusBubble()) return;
    event.stopPropagation();

    const text = finalResponseText;
    const theme = window.getStatusBubbleTheme ? window.getStatusBubbleTheme() : null;
    window.hideStatusBubble(0);
    if (window.overlayShowDirectResponse) {
      window.overlayShowDirectResponse(text, finalSource, theme);
    }
  });

  if (statusDismiss) {
    statusDismiss.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      window.hideStatusBubble(0);
    });
  }

  // Expose a function to trigger status bubble for testing
  window.triggerStatusBubbleTest = function(agentType) {
    const messages = {
      cua_vision: [
        'Analyzing screen...',
        'Looking for elements...',
        'Moving mouse to target...',
        'Clicking button...',
      ],
      cua_cli: [
        'Opening terminal...',
        'Running command...',
        'Processing output...',
      ],
      browser: [
        'Opening browser...',
        'Navigating to page...',
        'Filling form...',
        'Submitting...',
      ]
    };

    const agentMessages = messages[agentType] || messages.cua_cli;
    let index = 0;

    window.showStatusBubble(agentMessages[0]);

    const interval = setInterval(() => {
      index += 1;
      if (index < agentMessages.length) {
        window.updateStatusBubble(agentMessages[index]);
      } else {
        clearInterval(interval);
        window.completeStatusBubble(
          'Mocked completion response from agent. Click to restore center response.',
          { doneText: 'Task done', delayMs: 2000 }
        );
      }
    }, 1600);
  };
})();
