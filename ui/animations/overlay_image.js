const OVERLAY_DURATION_MS = 1000;
const overlayImage = document.getElementById('overlay-image');
let hideTimer = null;

function showOverlayImage() {
  if (!overlayImage) return;
  overlayImage.classList.remove('active');
  void overlayImage.offsetWidth;
  overlayImage.classList.add('active');

  if (hideTimer) {
    clearTimeout(hideTimer);
  }
  hideTimer = setTimeout(() => {
    overlayImage.classList.remove('active');
    hideTimer = null;
  }, OVERLAY_DURATION_MS);
}

document.addEventListener('keydown', (event) => {
  if (event.repeat) return;
  if (event.code !== 'Space') return;
  if (event.metaKey && event.shiftKey) {
    showOverlayImage();
  }
});

if (window.api?.onOverlayImage) {
  window.api.onOverlayImage(() => {
    showOverlayImage();
  });
}
