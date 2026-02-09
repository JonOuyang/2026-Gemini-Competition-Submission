import {
  createOverlayTextRoot,
  ensureOverlayTextBubble,
  ensureModelMeta,
  removeModelMeta
} from './dom_nodes/overlay_text.js';
import {
  createOverlayBoxRoot,
  updateOverlayBoxElement
} from './dom_nodes/overlay_box.js';

const canvas = document.getElementById('overlay');
const ctx = canvas.getContext('2d');
const textLayer = document.getElementById('text-layer');
const boxLayer = document.getElementById('box-layer');
const dots = new Map();
const boxes = new Map();
const texts = new Map();
const DIRECT_RESPONSE_ID = 'direct_response';
const DOT_RING_RADIUS = 31;
const DOT_RING_WIDTH = 2;
const DIRECT_RESPONSE_BOTTOM_MARGIN = 24;
const DIRECT_RESPONSE_MIN_MAX_HEIGHT = 140;
const OVERLAY_TEXT_VIEWPORT_MARGIN = 8;
const OVERLAY_TEXT_MIN_MAX_HEIGHT = 96;
let canvasBackgroundColor = null;
let lastHoverState = false;
let lastHitTestState = false;
let isOverlayTextSelectionDragging = false;
let overlayModelName = 'CLOVIS';
let lastDirectResponseTheme = null;

function applyDirectResponseHeightCap(el, bubble) {
  if (!el || !bubble) return;
  const rect = el.getBoundingClientRect();
  const top = Number.isFinite(rect.top) ? rect.top : parseFloat(el.style.top || '0');
  const available = Math.floor(window.innerHeight - top - DIRECT_RESPONSE_BOTTOM_MARGIN);
  const maxHeight = Math.max(DIRECT_RESPONSE_MIN_MAX_HEIGHT, available);
  bubble.style.maxHeight = `${maxHeight}px`;
  bubble.style.overflowY = 'auto';
  bubble.style.overflowX = 'hidden';
}

function applyGenericHeightCap(el, bubble, margin = OVERLAY_TEXT_VIEWPORT_MARGIN) {
  if (!el || !bubble) return;
  const available = Math.floor(window.innerHeight - (margin * 2));
  const maxHeight = Math.max(OVERLAY_TEXT_MIN_MAX_HEIGHT, available);
  if (bubble.offsetHeight > maxHeight) {
    bubble.style.maxHeight = `${maxHeight}px`;
    bubble.style.overflowY = 'auto';
    bubble.style.overflowX = 'hidden';
  } else {
    bubble.style.removeProperty('max-height');
    bubble.style.removeProperty('overflow-y');
    bubble.style.removeProperty('overflow-x');
  }
}

function clampOverlayTextToViewport(el, textId, margin = OVERLAY_TEXT_VIEWPORT_MARGIN) {
  if (!el) return;
  const bubble = el.querySelector('.ai-ar-panel');
  if (!bubble) return;

  if (textId !== DIRECT_RESPONSE_ID) {
    applyGenericHeightCap(el, bubble, margin);
  }

  const rect = el.getBoundingClientRect();
  let dx = 0;
  let dy = 0;

  if (rect.left < margin) {
    dx = margin - rect.left;
  } else if (rect.right > (window.innerWidth - margin)) {
    dx = (window.innerWidth - margin) - rect.right;
  }

  if (rect.top < margin) {
    dy = margin - rect.top;
  } else if (rect.bottom > (window.innerHeight - margin)) {
    dy = (window.innerHeight - margin) - rect.bottom;
  }

  if (dx === 0 && dy === 0) {
    return;
  }

  const currentLeft = parseFloat(el.style.left || '0');
  const currentTop = parseFloat(el.style.top || '0');
  if (!Number.isFinite(currentLeft) || !Number.isFinite(currentTop)) {
    return;
  }

  el.style.left = `${Math.round(currentLeft + dx)}px`;
  el.style.top = `${Math.round(currentTop + dy)}px`;
}

function clampAllTextsToViewport() {
  for (const entry of texts.values()) {
    if (!entry?.el) continue;
    clampOverlayTextToViewport(entry.el, entry.id);
  }
}

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  clampAllTextsToViewport();
  drawAll();
}

function drawAll() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (canvasBackgroundColor) {
    ctx.fillStyle = canvasBackgroundColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  for (const dot of dots.values()) {
    let lineTarget = dot.lineTo;
    if (dot.lineTargetTextId) {
      const textEntry = texts.get(dot.lineTargetTextId);
      if (textEntry?.el) {
        const bubble = textEntry.el.querySelector('.ai-ar-panel');
        const rect = (bubble || textEntry.el).getBoundingClientRect();
        lineTarget = {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        };
      }
    }
    if (lineTarget) {
      ctx.beginPath();
      ctx.strokeStyle = dot.lineColor || '#ffffff';
      ctx.lineWidth = dot.lineWidth || 2;
      ctx.moveTo(dot.x, dot.y);
      ctx.lineTo(lineTarget.x, lineTarget.y);
      ctx.stroke();
    }

    const ringRadius = dot.ringRadius || DOT_RING_RADIUS;
    const ringColor = dot.ringColor || dot.color || '#66B7FF';
    ctx.beginPath();
    ctx.strokeStyle = ringColor;
    ctx.lineWidth = DOT_RING_WIDTH;
    ctx.arc(dot.x, dot.y, ringRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.fillStyle = dot.dotColor || '#ffffff';
    ctx.arc(dot.x, dot.y, dot.radius, 0, Math.PI * 2);
    ctx.fill();
  }

}

function getTranslateAxis(value, axis) {
  if (axis === 'x') {
    if (value === 'center') return '-50%';
    if (value === 'right') return '-100%';
    return '0%';
  }

  if (value === 'middle') return '-50%';
  if (value === 'bottom') return '-100%';
  return '0%';
}

function getDirectResponseWidth(baseWidth) {
  const base = Number.isFinite(baseWidth) && Number(baseWidth) > 0
    ? Number(baseWidth)
    : 460;
  const maxAllowed = Math.round(window.innerWidth * 0.94);
  return Math.max(280, Math.min(maxAllowed, Math.round(base)));
}

function updateTextElement(el, text) {
  if (text.id === DIRECT_RESPONSE_ID) {
    el.classList.add('direct-response');
    const inputWrap = document.querySelector('.command-input-wrap');
    const commandBar = document.getElementById('command-bar');
    const savedAnchor = window.overlayDirectResponseAnchor;
    const baseWidth = Number.isFinite(savedAnchor?.width)
      ? savedAnchor.width
      : (inputWrap?.offsetWidth || commandBar?.offsetWidth || 460);
    const width = getDirectResponseWidth(baseWidth);
    const centerX = Number.isFinite(savedAnchor?.centerX)
      ? savedAnchor.centerX
      : (window.innerWidth * 0.5);
    const top = Number.isFinite(savedAnchor?.top)
      ? savedAnchor.top
      : Math.round((window.innerHeight * 0.5) - 12);
    el.style.left = `${centerX}px`;
    el.style.top = `${top}px`;
    el.dataset.lockedWidth = `${width}px`;
    el.style.width = `${width}px`;
    el.style.maxWidth = `${width}px`;
    el.style.setProperty('--text-translate-x', '-50%');
    el.style.setProperty('--text-translate-y', '0%');
    el.style.transform = 'translate(-50%, 0%)';
  } else {
    el.classList.remove('direct-response');
    el.style.left = `${text.x}px`;
    el.style.top = `${text.y}px`;
    el.style.removeProperty('transform');
    el.style.removeProperty('width');
    el.style.removeProperty('max-width');
  }

  const fontSize = text.fontSize || 16;
  const fontFamily = text.fontFamily || '"SF Pro Display", Inter, system-ui, -apple-system, sans-serif';

  const { bubble, textEl } = ensureOverlayTextBubble(el);

  const accentGlow = toRgba(text.color, 0.28);
  bubble.style.setProperty('--accent-glow', accentGlow);

  if (text.theme) {
    bubble.style.setProperty('--bubble-bg', text.theme.panelBg || '');
    bubble.style.setProperty('--bubble-border', text.theme.panelBorder || '');
    bubble.style.setProperty('--bubble-text', text.theme.text || '');
    bubble.style.setProperty('--bubble-label', text.theme.label || '');
    bubble.style.setProperty('--bubble-meta', text.theme.meta || '');
    bubble.style.setProperty('--bubble-divider', text.theme.divider || '');
    bubble.style.setProperty('--bubble-thinking', text.theme.thinking || '');
    bubble.style.setProperty('--bubble-shimmer', text.theme.shimmer || '');
    if (text.theme.panelBg) {
      bubble.style.background = `radial-gradient(140% 140% at 100% 100%, ${accentGlow}, rgba(0, 0, 0, 0) 60%), ${text.theme.panelBg}`;
    }
    if (text.theme.panelBorder) {
      bubble.style.borderColor = text.theme.panelBorder;
    }
    if (!bubble.dataset.themeLogged) {
      bubble.dataset.themeLogged = 'true';
    }
  } else {
    bubble.dataset.themeLogged = '';
  }

  if (text.id === DIRECT_RESPONSE_ID) {
    const { nameEl } = ensureModelMeta(bubble);
    if (nameEl) {
      nameEl.textContent = overlayModelName;
    }
  } else {
    removeModelMeta(bubble);
  }

  if (text.id === DIRECT_RESPONSE_ID && el.dataset.lockedWidth && el.dataset.lockedWidth !== 'unset') {
    bubble.style.width = '100%';
    bubble.style.maxWidth = '100%';
    applyDirectResponseHeightCap(el, bubble);
  } else {
    bubble.style.removeProperty('width');
    bubble.style.removeProperty('max-width');
    bubble.style.removeProperty('max-height');
    bubble.style.removeProperty('overflow-y');
    bubble.style.removeProperty('overflow-x');
  }

  textEl.style.fontSize = `${fontSize}px`;
  textEl.style.fontFamily = fontFamily;
  textEl.textContent = text.text ?? '';
  bubble.classList.remove('ai-meta-visible');
  if (text.id === DIRECT_RESPONSE_ID) {
    textEl.style.textAlign = 'left';
    textEl.style.width = '100%';
  } else {
    textEl.style.removeProperty('text-align');
    textEl.style.removeProperty('width');
  }
  if (el.classList.contains('ai-thinking')) {
    textEl.dataset.text = text.text ?? '';
  } else {
    delete textEl.dataset.text;
  }

  if (text.id !== DIRECT_RESPONSE_ID) {
    const align = text.align || 'left';
    const baseline = text.baseline || 'top';
    el.style.setProperty('--text-translate-x', getTranslateAxis(align, 'x'));
    el.style.setProperty('--text-translate-y', getTranslateAxis(baseline, 'y'));
  }
  clampOverlayTextToViewport(el, text.id);
  drawAll();
}

function toRgba(color, alpha) {
  const fallback = `rgba(135, 206, 235, ${alpha})`;
  if (!color || typeof color !== 'string') return fallback;
  const value = color.trim();
  if (value.startsWith('#')) {
    let hex = value.slice(1);
    if (hex.length === 3) {
      hex = hex.split('').map((c) => c + c).join('');
    }
    if (hex.length !== 6) return fallback;
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  const rgbaMatch = value.match(/^rgba?\((\s*\d+\s*),(\s*\d+\s*),(\s*\d+\s*)(?:,\s*[\d.]+\s*)?\)$/i);
  if (rgbaMatch) {
    const r = rgbaMatch[1].trim();
    const g = rgbaMatch[2].trim();
    const b = rgbaMatch[3].trim();
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  return fallback;
}

function clearFlush(entry) {
  if (entry?.flushTimer) {
    window.clearInterval(entry.flushTimer);
    entry.flushTimer = null;
  }
}

function startFlush(entry, fullText) {
  if (!entry?.el) return;
  clearFlush(entry);
  const bubble = entry.el.querySelector('.ai-ar-panel');
  const textEl = bubble?.querySelector('.ai-ar-text');
  if (!textEl) return;
  bubble?.classList.remove('ai-meta-visible');
  textEl.textContent = '';

  const tokens = fullText.match(/\S+|\s+/g) || [];
  let index = 0;
  const step = () => {
    if (!entry.el) return;
    if (index >= tokens.length) {
      clearFlush(entry);
      bubble?.classList.add('ai-meta-visible');
      return;
    }
    textEl.textContent += tokens[index];
    index += 1;
    clampOverlayTextToViewport(entry.el, entry.id);
    drawAll();
  };
  step();
  entry.flushTimer = window.setInterval(step, 12);
}

function fadeOutText(id, el) {
  if (!el) return;
  const entry = texts.get(id);
  if (entry) {
    clearFlush(entry);
  }
  el.classList.remove('overlay-text--visible');
  el.classList.add('overlay-text--closing');
  window.setTimeout(() => {
    if (texts.get(id)?.el === el) {
      el.remove();
      texts.delete(id);
    }
  }, 500);
}

function checkHit(x, y) {
  for (const dot of dots.values()) {
    const dx = x - dot.x;
    const dy = y - dot.y;
    if ((dx * dx + dy * dy) <= dot.radius * dot.radius) {
      return { type: 'dot', id: dot.id };
    }
  }

  for (const entry of boxes.values()) {
    const box = entry?.data;
    if (!box) continue;
    const withinX = x >= box.x && x <= (box.x + box.width);
    const withinY = y >= box.y && y <= (box.y + box.height);
    if (withinX && withinY) {
      return { type: 'box', id: box.id };
    }
  }
  return null;
}

function isOverOverlayElement(x, y) {
  if (isOverlayTextSelectionDragging) {
    return true;
  }

  if (checkHit(x, y)) return true;

  const inputWrap = document.querySelector('.command-input-wrap');
  if (inputWrap) {
    const rect = inputWrap.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return true;
    }
  }

  for (const entry of texts.values()) {
    if (!entry?.el) continue;
    const rect = entry.el.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return true;
    }
  }

  const statusBubble = document.getElementById('status-bubble');
  if (statusBubble && statusBubble.getAttribute('aria-hidden') !== 'true') {
    const rect = statusBubble.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return true;
    }
  }

  const cursorStatus = document.getElementById('cursor-status');
  if (cursorStatus && cursorStatus.getAttribute('aria-hidden') !== 'true') {
    const rect = cursorStatus.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return true;
    }
  }

  return false;
}

function upsertDot(dot) {
  dots.set(dot.id, dot);
  drawAll();
}

function removeDot(id) {
  dots.delete(id);
  drawAll();
}

function upsertBox(box) {
  let entry = boxes.get(box.id);
  if (!entry) {
    const el = createOverlayBoxRoot(boxLayer, box.id);
    entry = { id: box.id, el };
    boxes.set(box.id, entry);
  }
  entry.data = box;
  updateOverlayBoxElement(entry.el, box);
}

function removeBox(id) {
  const entry = boxes.get(id);
  if (entry?.el) {
    entry.el.remove();
  }
  boxes.delete(id);
}

function upsertText(text) {
  let entry = texts.get(text.id);
  if (!entry) {
    const { el } = createOverlayTextRoot(textLayer, text.id, (event) => {
      // Keep native double-click word selection working.
      // Use Alt+double-click as the explicit dismiss gesture.
      if (!event.altKey) return;
      event.stopPropagation();
      fadeOutText(text.id, el);
    });
    entry = { id: text.id, el };
    texts.set(text.id, entry);
    requestAnimationFrame(() => {
      el.classList.add('overlay-text--visible');
    });
  } else if (entry.el.classList.contains('overlay-text--closing')) {
    entry.el.classList.remove('overlay-text--closing');
  }

  entry.data = { ...text };
  if (text.id === DIRECT_RESPONSE_ID && text.theme && typeof text.theme === 'object') {
    lastDirectResponseTheme = { ...text.theme };
  }
  updateTextElement(entry.el, text);

  if (entry.el.classList.contains('ai-thinking') && text.text !== 'Gemini is thinking...') {
    entry.el.classList.remove('ai-thinking');
    entry.el.classList.add('ai-reveal');
    const textEl = entry.el.querySelector('.ai-ar-text');
    if (textEl) {
      delete textEl.dataset.text;
    }
    window.setTimeout(() => {
      entry.el?.classList.remove('ai-reveal');
    }, 450);
  }

  if (text.id === DIRECT_RESPONSE_ID && text.text && text.text !== 'Gemini is thinking...') {
    if (entry.lastText !== text.text) {
      entry.lastText = text.text;
      startFlush(entry, text.text);
    }
  }
}

function removeText(id) {
  const entry = texts.get(id);
  if (!entry) return;
  clearFlush(entry);
  entry.el.remove();
  texts.delete(id);
  if (id === DIRECT_RESPONSE_ID) {
    lastDirectResponseTheme = null;
  }
}

function clearAll() {
  dots.clear();
  for (const entry of boxes.values()) {
    entry?.el?.remove();
  }
  boxes.clear();
  texts.clear();
  lastDirectResponseTheme = null;
  boxLayer?.replaceChildren();
  textLayer.replaceChildren();
  drawAll();
}

function showStopStatusBubble() {
  if (!window.showStatusBubble) return;
  window.showStatusBubble('Gemini has stopped responding', {
    icon: 'stop',
    statusBg: 'rgba(64, 16, 16, 0.96)',
    statusBorder: 'rgba(255, 120, 120, 0.32)',
    statusText: 'rgba(255, 235, 235, 0.98)',
    statusShimmer: 'rgba(255, 120, 120, 0.55)',
    statusCheck: 'rgba(255, 120, 120, 0.9)'
  });
}

function showThinkingAt(x, y, theme = null) {
  const resolvedTheme = (theme && typeof theme === 'object')
    ? { ...theme }
    : null;
  upsertText({
    id: DIRECT_RESPONSE_ID,
    x,
    y,
    text: 'Gemini is thinking...',
    color: resolvedTheme?.accent || '#8BE9FD',
    theme: resolvedTheme || undefined,
    align: 'left',
    baseline: 'top'
  });
  const entry = texts.get(DIRECT_RESPONSE_ID);
  if (entry?.el) {
    entry.el.dataset.lockedPos = 'true';
    entry.el.classList.add('ai-thinking');
    entry.el.dataset.lockedWidth = 'unset';
    const inputWrap = document.querySelector('.command-input-wrap');
    if (inputWrap) {
      entry.el.dataset.lockedWidth = `${inputWrap.offsetWidth}px`;
    }
    const textEl = entry.el.querySelector('.ai-ar-text');
    if (textEl) {
      textEl.dataset.text = 'Gemini is thinking...';
    }
  }

  // Route the same text through the server so it gets the exact same
  // adaptive light/dark theme assignment path as normal draw_text payloads.
  sendMessage({
    command: 'draw_text',
    id: DIRECT_RESPONSE_ID,
    x,
    y,
    text: 'Gemini is thinking...',
    align: 'left',
    baseline: 'top',
    source: 'overlay',
  });
}

window.overlayShowThinking = showThinkingAt;
window.overlayShowDirectResponse = function(text, source = 'unknown', theme = null) {
  const value = typeof text === 'string' ? text.trim() : '';
  if (!value) return;
  console.log(`[renderer][ui_text][${source}][direct_response] ${value}`);
  const resolvedTheme = (lastDirectResponseTheme && typeof lastDirectResponseTheme === 'object')
    ? { ...lastDirectResponseTheme }
    : ((theme && typeof theme === 'object') ? { ...theme } : null);
  if (window.restoreCommandBar) {
    window.restoreCommandBar();
  }
  requestAnimationFrame(() => {
    upsertText({
      id: DIRECT_RESPONSE_ID,
      x: Math.round(window.innerWidth * 0.5),
      y: Math.round(window.innerHeight * 0.5) + 42,
      text: value,
      color: resolvedTheme?.accent || '#8BE9FD',
      theme: resolvedTheme || undefined,
      align: 'left',
      baseline: 'top'
    });
    const entry = texts.get(DIRECT_RESPONSE_ID);
    if (entry?.el) {
      entry.el.classList.remove('ai-thinking');
    }
  });
};

console.log('[renderer] boot', { width: window.innerWidth, height: window.innerHeight });

let socket;
let reconnectDelay = 500;
let reconnectTimer = null;
let lastSocketLogTime = 0;

async function getSocketTarget() {
  const fallback = { host: '127.0.0.1', port: 8765 };
  try {
    if (!window.api?.getServerConfig) {
      return fallback;
    }
    const config = await window.api.getServerConfig();
    const host = typeof config?.host === 'string' && config.host.trim() ? config.host.trim() : fallback.host;
    const portValue = Number(config?.port);
    const port = Number.isInteger(portValue) && portValue > 0 ? portValue : fallback.port;
    return { host, port };
  } catch (error) {
    return fallback;
  }
}

function logSocketEvent(message) {
  const now = Date.now();
  if (now - lastSocketLogTime < 2000) {
    return;
  }
  lastSocketLogTime = now;
  console.log(message);
}

function sendMessage(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(payload));
  return true;
}

window.overlaySend = sendMessage;
window.overlayHideResponse = () => removeText(DIRECT_RESPONSE_ID);

function isOverlayInputActive() {
  return window.overlayInputFocusedFlag === true;
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    void connectSocket();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 1.5, 5000);
}

async function connectSocket() {
  const target = await getSocketTarget();
  const wsUrl = `ws://${target.host}:${target.port}`;
  socket = new WebSocket(wsUrl);
  socket.addEventListener('open', () => {
    logSocketEvent(`[renderer] websocket open (${wsUrl})`);
    reconnectDelay = 500;
    sendMessage({
      event: 'viewport',
      width: window.innerWidth,
      height: window.innerHeight
    });
  });
  socket.addEventListener('error', () => {
    logSocketEvent(`[renderer] websocket error (${wsUrl})`);
  });
  socket.addEventListener('close', () => {
    logSocketEvent(`[renderer] websocket closed (${wsUrl})`);
    scheduleReconnect();
  });

  socket.addEventListener('message', (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      return;
    }

  if (payload.command === 'draw_dot') {
      console.log('[renderer] draw_dot', payload.id);
      upsertDot({
        id: payload.id,
        x: payload.x,
        y: payload.y,
        radius: payload.radius || 6,
        color: payload.color,
        dotColor: payload.dotColor || '#ffffff',
        ringColor: payload.ringColor || payload.color || '#66B7FF',
        ringRadius: payload.ringRadius,
        lineTo: payload.lineTo,
        lineTargetTextId: payload.lineTargetTextId,
        lineColor: payload.lineColor,
        lineWidth: payload.lineWidth
      });
  } else if (payload.command === 'draw_box') {
    upsertBox({
      id: payload.id,
      x: payload.x,
      y: payload.y,
      width: payload.width,
      height: payload.height,
      stroke: payload.stroke,
      strokeWidth: payload.strokeWidth,
      fill: payload.fill,
      opacity: payload.opacity
    });
    } else if (payload.command === 'draw_text') {
      if (typeof payload.text === 'string') {
        const source = payload.source || 'unknown';
        console.log(`[renderer][ui_text][${source}][draw_text][${payload.id || 'unknown'}] ${payload.text}`);
      }
      upsertText({
        id: payload.id,
        x: payload.x,
        y: payload.y,
        text: payload.text,
        color: payload.color,
        fontSize: payload.fontSize,
        fontFamily: payload.fontFamily,
        align: payload.align,
        baseline: payload.baseline,
        theme: payload.theme
      });
    } else if (payload.command === 'remove_dot') {
      removeDot(payload.id);
    } else if (payload.command === 'remove_box') {
      removeBox(payload.id);
    } else if (payload.command === 'remove_text') {
      removeText(payload.id);
    } else if (payload.command === 'overlay_hide') {
      if (window.overlayHideCommandOverlay) {
        window.overlayHideCommandOverlay();
      }
      if (payload.id) {
        removeText(payload.id);
      }
    } else if (payload.command === 'show_command_overlay') {
      if (window.overlayShowCommandOverlay) {
        window.overlayShowCommandOverlay();
      }
    } else if (payload.command === 'clear') {
      clearAll();
    } else if (payload.command === 'set_background') {
      const value = typeof payload.color === 'string' ? payload.color.trim() : '';
      canvasBackgroundColor = value || null;
      drawAll();
    } else if (payload.command === 'set_model_name') {
      if (payload.name) {
        overlayModelName = payload.name;
      }
    } else if (payload.command === 'show_status_bubble') {
      if (window.showStatusBubble) {
        window.showStatusBubble(payload.text || 'Working...', payload.theme, payload.source);
      }
    } else if (payload.command === 'update_status_bubble') {
      if (window.updateStatusBubble) {
        window.updateStatusBubble(payload.text || 'Working...', payload.theme, payload.source);
      }
    } else if (payload.command === 'complete_status_bubble') {
      if (window.completeStatusBubble) {
        window.completeStatusBubble(payload.responseText || payload.text || '', {
          doneText: payload.doneText,
          delayMs: payload.delayMs ?? payload.delay,
          theme: payload.theme,
          source: payload.source
        });
      }
    } else if (payload.command === 'hide_status_bubble') {
      if (window.hideStatusBubble) {
        window.hideStatusBubble(payload.delay || 0);
      }
    } else if (payload.command === 'show_cursor_status') {
      if (window.showCursorStatus) {
        window.showCursorStatus(payload.text || 'Working...', payload.theme, payload.source);
      }
    } else if (payload.command === 'update_cursor_status') {
      if (window.updateCursorStatus) {
        window.updateCursorStatus(payload.text || 'Working...', payload.theme, payload.source);
      }
    } else if (payload.command === 'hide_cursor_status') {
      if (window.hideCursorStatus) {
        window.hideCursorStatus();
      }
    } else if (payload.command === 'set_cursor_status_position') {
      if (window.setCursorStatusPosition) {
        window.setCursorStatusPosition(payload.x || 0, payload.y || 0);
      }
    }
  });
}

void connectSocket();

function isSelectableOverlayTextTarget(target) {
  if (!(target instanceof Element)) return false;
  return !!target.closest('.ai-ar-text, #status-bubble-text');
}

document.addEventListener('mousedown', (event) => {
  if (event.button !== 0) return;
  if (!isSelectableOverlayTextTarget(event.target)) return;
  isOverlayTextSelectionDragging = true;
  if (window.api?.setWindowInteractive) {
    window.api.setWindowInteractive(true);
  }
}, true);

document.addEventListener('mouseup', (event) => {
  if (!isOverlayTextSelectionDragging) return;
  isOverlayTextSelectionDragging = false;

  const x = typeof event.clientX === 'number' ? event.clientX : 0;
  const y = typeof event.clientY === 'number' ? event.clientY : 0;
  const isOver = isOverOverlayElement(x, y);

  if (platform === 'win32') {
    if (isOver !== lastHoverState) {
      lastHoverState = isOver;
      window.api.setWindowInteractive(isOver);
    }
  } else if (isOver !== lastHitTestState) {
    lastHitTestState = isOver;
    window.api.reportHitTest(isOver);
  }
}, true);

canvas.addEventListener('click', (event) => {
  const hit = checkHit(event.clientX, event.clientY);
  if (!hit) return;
  sendMessage({ event: 'click', id: hit.id, type: hit.type });
});

window.addEventListener('resize', () => {
  resizeCanvas();
  for (const entry of texts.values()) {
    if (entry?.el && entry.data) {
      updateTextElement(entry.el, entry.data);
    }
  }
  sendMessage({
    event: 'viewport',
    width: window.innerWidth,
    height: window.innerHeight
  });
});

const platform = window.api.getPlatform();
if (platform === 'win32') {
  window.addEventListener('mousemove', (event) => {
    if (window.setCursorStatusPosition) {
      window.setCursorStatusPosition(event.clientX, event.clientY);
    }
    const isOver = isOverOverlayElement(event.clientX, event.clientY);
    if (isOver === lastHoverState) return;
    lastHoverState = isOver;
    window.api.setWindowInteractive(isOver);
  });
} else {
  window.api.onCursorPosition((point) => {
    if (window.setCursorStatusPosition) {
      window.setCursorStatusPosition(point.x, point.y);
    }
    const isOver = isOverOverlayElement(point.x, point.y);
    if (isOver === lastHitTestState) return;
    lastHitTestState = isOver;
    window.api.reportHitTest(isOver);
  });
}

window.api.onResetConfigure(() => {
  clearAll();
  sendMessage({ event: 'reset' });
});

if (window.api?.onClearOverlay) {
  window.api.onClearOverlay(() => {
    clearAll();
  });
}

if (window.api?.onStopAll) {
  window.api.onStopAll(() => {
    showStopStatusBubble();
    if (window.overlayHideResponse) {
      window.overlayHideResponse();
    }
    if (window.overlayForceResetCommandOverlay) {
      window.overlayForceResetCommandOverlay();
    } else if (window.overlayHideCommandOverlay) {
      window.overlayHideCommandOverlay();
    }
    if (window.hideScreenGlow) {
      window.hideScreenGlow();
    }
    if (window.hideCursorStatus) {
      window.hideCursorStatus();
    }
    clearAll();
    window.setTimeout(() => {
      if (window.hideStatusBubble) {
        window.hideStatusBubble(0);
      }
    }, 2240);
    sendMessage({ event: 'stop_all' });
  });
}

resizeCanvas();
