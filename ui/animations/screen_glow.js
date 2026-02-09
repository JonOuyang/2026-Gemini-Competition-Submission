const screenGlow = document.getElementById('screen-glow');

function showScreenGlow() {
  if (!screenGlow) return;
  screenGlow.classList.remove('closing');
  screenGlow.classList.remove('active');
  void screenGlow.offsetWidth;
  screenGlow.classList.add('active');
}

function hideScreenGlow() {
  if (!screenGlow) return;
  screenGlow.classList.remove('active');
  screenGlow.classList.add('closing');
}

window.hideScreenGlow = hideScreenGlow;

if (window.api?.onOverlayImage) {
  window.api.onOverlayImage(() => {
    showScreenGlow();
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    hideScreenGlow();
  }
});
