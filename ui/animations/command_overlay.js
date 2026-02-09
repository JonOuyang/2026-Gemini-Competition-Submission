const commandOverlay = document.getElementById('command-overlay');
const commandInput = document.getElementById('command-input');
const commandSend = document.getElementById('command-send');
const commandLogo = document.getElementById('command-logo');
const commandLogoSpin = document.getElementById('command-logo-spin');
const commandBar = document.getElementById('command-bar');
const commandInputWrap = commandOverlay?.querySelector('.command-input-wrap');
const MAX_INPUT_HEIGHT = 180;
let overlayActive = false;
let overlayClosing = false;
let inputFocused = false;
let lastSubmittedText = '';
let lastSubmittedAt = 0;
let hideOverlayTimeout = null;
let logoSyncRaf = null;
let logoSyncUntil = 0;

function getElementTranslateY(el) {
  if (!el) return 0;
  const computed = window.getComputedStyle(el);
  const transform = computed?.transform;
  if (!transform || transform === 'none') {
    return 0;
  }

  // matrix(a, b, c, d, tx, ty)
  const matrix2d = transform.match(/^matrix\(([^)]+)\)$/);
  if (matrix2d) {
    const values = matrix2d[1].split(',').map((part) => Number(part.trim()));
    if (values.length === 6 && Number.isFinite(values[5])) {
      return values[5];
    }
  }

  // matrix3d(..., tx, ty, tz)
  const matrix3d = transform.match(/^matrix3d\(([^)]+)\)$/);
  if (matrix3d) {
    const values = matrix3d[1].split(',').map((part) => Number(part.trim()));
    if (values.length === 16 && Number.isFinite(values[13])) {
      return values[13];
    }
  }

  return 0;
}

function syncCommandLogoVerticalPosition() {
  if (!commandLogo || !commandInputWrap) return;
  let anchorRect = commandSend?.getBoundingClientRect();
  if (!anchorRect || !Number.isFinite(anchorRect.height) || anchorRect.height <= 0) {
    anchorRect = commandInputWrap.getBoundingClientRect();
  }
  if (!anchorRect || !Number.isFinite(anchorRect.top) || anchorRect.height <= 0) return;
  const anchorCenterY = anchorRect.top + (anchorRect.height / 2);
  const logoHeight = commandLogo.offsetHeight || 70;
  const translateY = getElementTranslateY(commandLogo);
  commandLogo.style.top = `${Math.round(anchorCenterY - (logoHeight / 2) - translateY)}px`;
}

function stopLogoSyncLoop() {
  if (logoSyncRaf !== null) {
    cancelAnimationFrame(logoSyncRaf);
    logoSyncRaf = null;
  }
  logoSyncUntil = 0;
}

function startLogoSyncLoop(durationMs = 1800) {
  stopLogoSyncLoop();
  logoSyncUntil = performance.now() + durationMs;

  const tick = () => {
    if (!overlayActive) {
      stopLogoSyncLoop();
      return;
    }
    syncCommandLogoVerticalPosition();
    if (performance.now() < logoSyncUntil) {
      logoSyncRaf = requestAnimationFrame(tick);
      return;
    }
    logoSyncRaf = null;
    syncCommandLogoVerticalPosition();
  };

  logoSyncRaf = requestAnimationFrame(tick);
}

function cacheDirectResponseAnchor() {
  const anchorEl = commandInputWrap || commandBar;
  if (!anchorEl) return;
  const rect = anchorEl.getBoundingClientRect();
  const width = commandInputWrap?.offsetWidth || commandBar?.offsetWidth || rect.width;
  window.overlayDirectResponseAnchor = {
    centerX: window.innerWidth * 0.5,
    // Final settled anchor under the centered bar (independent of in-flight intro animation).
    top: Math.round((window.innerHeight * 0.5) - 12),
    width
  };
}

function resizeInput() {
  if (!commandInput) return;
  commandInput.style.height = 'auto';
  const targetHeight = Math.min(MAX_INPUT_HEIGHT, commandInput.scrollHeight);
  commandInput.style.height = `${targetHeight}px`;
  if (overlayActive) {
    requestAnimationFrame(() => {
      syncCommandLogoVerticalPosition();
    });
  }
}

function setInputMode(enabled) {
  if (window.api?.setInputMode) {
    window.api.setInputMode(enabled);
  }
}

function showCommandOverlay() {
  if (!commandOverlay) return;
  if (overlayActive && !overlayClosing) return;

  // If the user re-summons quickly during fade-out, cancel close and reopen
  // immediately so animations and state don't get stuck between phases.
  if (overlayClosing) {
    overlayClosing = false;
    if (hideOverlayTimeout) {
      clearTimeout(hideOverlayTimeout);
      hideOverlayTimeout = null;
    }
    commandOverlay.classList.remove('closing');
    overlayActive = false;
  }

  overlayActive = true;
  overlayClosing = false;
  window.overlayInputActiveFlag = true;
  window.overlayInputFocusedFlag = false;
  // Force a fresh class transition so spawn/move animations reliably replay.
  commandOverlay.classList.remove('active');
  void commandOverlay.offsetWidth;
  commandOverlay.classList.remove('agent-active');
  commandOverlay.classList.remove('closing');
  commandOverlay.classList.add('active');
  if (commandBar) {
    commandBar.style.animation = '';
    commandBar.style.opacity = '';
    commandBar.style.transform = '';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.opacity = '';
    commandLogo.style.transform = '';
    commandLogo.style.pointerEvents = '';
    commandLogo.style.animation = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = '';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = '';
    commandInputWrap.style.transform = '';
    commandInputWrap.style.opacity = '';
    commandInputWrap.style.pointerEvents = '';
  }
  commandInput.value = '';
  resizeInput();
  setInputMode(false);
  startLogoSyncLoop(1800);
  setTimeout(() => commandInput.focus(), 20);
}

function collapseCommandBar() {
  if (commandOverlay) {
    commandOverlay.classList.add('agent-active');
  }
  if (commandBar) {
    commandBar.style.opacity = '0';
    commandBar.style.transform = 'translateY(20px)';
    commandBar.style.pointerEvents = 'none';
  }
  if (commandLogo) {
    commandLogo.style.animation = 'none';
    commandLogo.style.opacity = '0';
    commandLogo.style.transform = 'translateY(20px)';
    commandLogo.style.pointerEvents = 'none';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = 'none';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = 'none';
    commandInputWrap.style.opacity = '0';
    commandInputWrap.style.pointerEvents = 'none';
  }
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
}

function hideCommandOverlay() {
  if (!commandOverlay || !overlayActive || overlayClosing) return;
  overlayClosing = true;
  commandOverlay.classList.remove('agent-active');
  commandOverlay.classList.add('closing');
  commandInput.value = '';
  resizeInput();
  setInputMode(false);
  window.overlayInputActiveFlag = false;
  window.overlayInputFocusedFlag = false;
  if (window.overlaySend) {
    window.overlaySend({ command: 'overlay_hide', id: 'direct_response' });
  }
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
  stopLogoSyncLoop();
  if (hideOverlayTimeout) {
    clearTimeout(hideOverlayTimeout);
    hideOverlayTimeout = null;
  }
  hideOverlayTimeout = setTimeout(() => {
    overlayActive = false;
    overlayClosing = false;
    hideOverlayTimeout = null;
    commandOverlay.classList.remove('active');
    commandOverlay.classList.remove('closing');
  }, 1000);
}

function forceResetCommandOverlay() {
  if (hideOverlayTimeout) {
    clearTimeout(hideOverlayTimeout);
    hideOverlayTimeout = null;
  }

  stopLogoSyncLoop();
  overlayActive = false;
  overlayClosing = false;
  inputFocused = false;
  window.overlayInputActiveFlag = false;
  window.overlayInputFocusedFlag = false;

  if (commandInput) {
    commandInput.blur();
    commandInput.value = '';
  }
  resizeInput();
  setInputMode(false);

  if (commandOverlay) {
    commandOverlay.classList.remove('active');
    commandOverlay.classList.remove('closing');
    commandOverlay.classList.remove('agent-active');
  }

  if (commandBar) {
    commandBar.style.animation = '';
    commandBar.style.opacity = '';
    commandBar.style.transform = '';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.opacity = '';
    commandLogo.style.transform = '';
    commandLogo.style.pointerEvents = '';
    commandLogo.style.animation = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = '';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = '';
    commandInputWrap.style.transform = '';
    commandInputWrap.style.opacity = '';
    commandInputWrap.style.pointerEvents = '';
  }

  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
}

function sendCommand() {
  if (!overlayActive) return;
  const text = commandInput.value.trim();
  if (!text) {
    hideCommandOverlay();
    return;
  }

  const now = Date.now();
  if (text === lastSubmittedText && (now - lastSubmittedAt) < 1200) {
    return;
  }
  lastSubmittedText = text;
  lastSubmittedAt = now;

  if (window.hideStatusBubble && window.isStatusBubbleVisible?.()) {
    window.hideStatusBubble(0);
  }

  cacheDirectResponseAnchor();
  const thinkingAnchor = window.overlayDirectResponseAnchor || {};
  const thinkingX = Number.isFinite(thinkingAnchor.centerX)
    ? thinkingAnchor.centerX
    : Math.round(window.innerWidth * 0.5);
  const thinkingY = Number.isFinite(thinkingAnchor.top)
    ? thinkingAnchor.top
    : Math.round((window.innerHeight * 0.5) - 12);

  // Ensure immediate visual feedback on submit before any backend round-trip.
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
  if (window.overlayShowThinking) {
    window.overlayShowThinking(thinkingX, thinkingY);
  }

  if (window.overlaySend) {
    window.overlaySend({
      event: 'overlay_input',
      text,
      requestId: `overlay_${now}_${Math.random().toString(16).slice(2, 8)}`
    });
  }
  if (window.hideScreenGlow) {
    window.hideScreenGlow();
  }
}

// Function to restore command bar visibility (called when agent finishes)
function restoreCommandBar() {
  const commandBar = document.getElementById('command-bar');
  const commandLogo = document.getElementById('command-logo');
  // Ignore late restore calls while the input overlay is actively shown,
  // unless it is currently collapsed by agent mode.
  if (overlayActive && !commandOverlay?.classList.contains('agent-active')) {
    return;
  }
  if (commandBar) {
    commandOverlay?.classList.remove('agent-active');
    commandBar.style.animation = 'none';
    commandBar.style.opacity = '1';
    commandBar.style.transform = 'translate3d(-50%, calc(-50% - 20px), 0)';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.animation = 'none';
    commandLogo.style.opacity = '1';
    commandLogo.style.transform = 'translate3d(calc(-50% - 235px), calc(-50% - 43px), 0) scale(0.45)';
    commandLogo.style.pointerEvents = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = 'none';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = 'none';
    commandInputWrap.style.transform = 'translate3d(0, -50%, 0) scaleX(1) scaleY(1)';
    commandInputWrap.style.opacity = '1';
    commandInputWrap.style.pointerEvents = '';
  }
  requestAnimationFrame(() => {
    syncCommandLogoVerticalPosition();
    if (overlayActive) {
      // Keep logo centered while restore transitions settle.
      startLogoSyncLoop(700);
    }
  });
}

window.restoreCommandBar = restoreCommandBar;
window.overlayShowCommandOverlay = showCommandOverlay;
window.overlayCollapseCommandBar = collapseCommandBar;
window.overlayForceResetCommandOverlay = forceResetCommandOverlay;

commandInput?.addEventListener('input', resizeInput);
commandInput?.addEventListener('focus', () => {
  inputFocused = true;
  window.overlayInputFocusedFlag = true;
  setInputMode(true);
});
commandInput?.addEventListener('blur', () => {
  inputFocused = false;
  window.overlayInputFocusedFlag = false;
  setInputMode(false);
});
commandSend?.addEventListener('click', () => sendCommand());
commandInput?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    sendCommand();
  }
});

document.addEventListener('keydown', (event) => {
  if (!overlayActive) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    hideCommandOverlay();
  }
});

window.addEventListener('resize', () => {
  if (!overlayActive) return;
  syncCommandLogoVerticalPosition();
});

if (window.api?.onOverlayImage) {
  window.api.onOverlayImage(() => {
    // Capture screenshot BEFORE showing overlay
    if (window.overlaySend) {
      window.overlaySend({ event: 'capture_screenshot' });
    }
    // Small delay to ensure screenshot is taken before overlay appears
    setTimeout(() => {
      showCommandOverlay();
    }, 50);
  });
}

window.overlayHideCommandOverlay = hideCommandOverlay;

resizeInput();
