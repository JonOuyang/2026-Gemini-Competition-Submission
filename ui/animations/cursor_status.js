/**
 * Cursor Status - near-cursor status indicator
 */

(function() {
  const cursorStatus = document.getElementById('cursor-status');
  const cursorText = document.getElementById('cursor-status-text');

  let isVisible = false;
  let lastX = 0;
  let lastY = 0;
  let rafPending = false;
  let currentSource = 'unknown';

  const OFFSET_X = 14;
  const OFFSET_Y = 18;
  const EDGE_PADDING = 6;
  const normalizeSource = (source) =>
    (typeof source === 'string' && source.trim()) ? source.trim() : 'unknown';
  const logCursorText = (channel, text, source = currentSource) => {
    if (channel === 'update') return;
    const safeText = typeof text === 'string' ? text : String(text ?? '');
    console.log(`[renderer][ui_cursor][${normalizeSource(source)}][${channel}] ${safeText}`);
  };

  const clampPosition = (x, y) => {
    const rect = cursorStatus.getBoundingClientRect();
    let nextX = x + OFFSET_X;
    let nextY = y + OFFSET_Y;
    const forceLeft = x >= window.innerWidth * 0.85;

    if (forceLeft || nextX + rect.width > window.innerWidth - EDGE_PADDING) {
      nextX = x - rect.width - OFFSET_X;
    }
    if (nextY + rect.height > window.innerHeight - EDGE_PADDING) {
      nextY = y - rect.height - OFFSET_Y;
    }

    if (nextX < EDGE_PADDING) nextX = EDGE_PADDING;
    if (nextY < EDGE_PADDING) nextY = EDGE_PADDING;

    return { x: Math.round(nextX), y: Math.round(nextY) };
  };

  const positionBubble = () => {
    rafPending = false;
    if (!isVisible) return;
    const { x, y } = clampPosition(lastX, lastY);
    cursorStatus.style.transform = `translate3d(${x}px, ${y}px, 0)`;
  };

  const requestPosition = () => {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(positionBubble);
  };

  window.setCursorStatusPosition = function(x, y) {
    lastX = x;
    lastY = y;
    if (!isVisible) return;
    requestPosition();
  };

  const applyTheme = (theme) => {
    if (!theme) return;
    cursorStatus.style.setProperty('--cursor-bg', theme.cursorBg || '');
    cursorStatus.style.setProperty('--cursor-border', theme.cursorBorder || '');
    cursorStatus.style.setProperty('--cursor-text', theme.cursorText || '');
    cursorStatus.style.setProperty('--cursor-shimmer', theme.cursorShimmer || '');
  };

  window.showCursorStatus = function(text = 'Working...', theme = null, source = 'unknown') {
    currentSource = normalizeSource(source);
    logCursorText('show', text, currentSource);
    applyTheme(theme);
    cursorText.textContent = text;
    cursorText.setAttribute('data-text', text);
    cursorText.classList.add('cursor-status-text--shimmer');
    cursorStatus.setAttribute('aria-hidden', 'false');
    cursorStatus.classList.remove('cursor-status--closing');
    cursorStatus.classList.add('cursor-status--visible');
    isVisible = true;
    requestPosition();
  };

  window.updateCursorStatus = function(text, theme = null, source = null) {
    if (source !== null && source !== undefined) {
      currentSource = normalizeSource(source);
    }
    logCursorText('update', text, currentSource);
    applyTheme(theme);
    if (!isVisible) {
      window.showCursorStatus(text);
      return;
    }
    cursorText.textContent = text;
    cursorText.setAttribute('data-text', text);
  };

  window.hideCursorStatus = function() {
    if (!isVisible) return;
    cursorStatus.classList.add('cursor-status--closing');
    cursorStatus.classList.remove('cursor-status--visible');
    isVisible = false;
    setTimeout(() => {
      cursorStatus.setAttribute('aria-hidden', 'true');
      cursorStatus.classList.remove('cursor-status--closing');
      cursorStatus.style.transform = 'translate3d(-9999px, -9999px, 0)';
      cursorText.classList.remove('cursor-status-text--shimmer');
    }, 200);
  };
})();
