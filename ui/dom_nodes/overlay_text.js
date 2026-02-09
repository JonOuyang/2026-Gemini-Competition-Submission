export function createOverlayTextRoot(textLayer, textId, onDblClick) {
  const el = document.createElement('div');
  el.className = 'overlay-text';
  el.dataset.textId = textId;
  if (onDblClick) {
    el.addEventListener('dblclick', onDblClick);
  }
  textLayer.appendChild(el);
  const { bubble, textEl } = ensureOverlayTextBubble(el);
  return { el, bubble, textEl };
}

export function ensureOverlayTextBubble(root) {
  let bubble = root.querySelector('.ai-ar-panel');
  if (!bubble) {
    bubble = document.createElement('div');
    bubble.className = 'ai-ar-panel';
    const textEl = document.createElement('div');
    textEl.className = 'ai-ar-text';
    bubble.appendChild(textEl);
    root.replaceChildren(bubble);
  }
  const textEl = bubble.querySelector('.ai-ar-text');
  return { bubble, textEl };
}

export function ensureModelMeta(bubble) {
  let meta = bubble.querySelector('.ai-model-meta');
  if (!meta) {
    meta = document.createElement('div');
    meta.className = 'ai-model-meta';
    const nameEl = document.createElement('div');
    nameEl.className = 'ai-model-name';
    const lineEl = document.createElement('div');
    lineEl.className = 'ai-model-divider';
    meta.appendChild(nameEl);
    meta.appendChild(lineEl);
    bubble.insertBefore(meta, bubble.firstChild);
  }
  const nameEl = meta.querySelector('.ai-model-name');
  return { meta, nameEl };
}

export function removeModelMeta(bubble) {
  const meta = bubble.querySelector('.ai-model-meta');
  if (meta) {
    meta.remove();
  }
}
