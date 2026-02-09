export function createOverlayBoxRoot(boxLayer, boxId) {
  const el = document.createElement('div');
  el.className = 'overlay-box overlay-box--animate';
  el.dataset.boxId = boxId;
  el.addEventListener('animationend', () => {
    el.classList.remove('overlay-box--animate');
  }, { once: true });

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('overlay-box__svg');
  svg.setAttribute('aria-hidden', 'true');
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.classList.add('overlay-box__rect');
  rect.setAttribute('x', '0');
  rect.setAttribute('y', '0');
  rect.setAttribute('pathLength', '1');
  svg.appendChild(rect);
  el.appendChild(svg);

  boxLayer.appendChild(el);
  return el;
}

export function updateOverlayBoxElement(el, box) {
  el.style.left = `${box.x}px`;
  el.style.top = `${box.y}px`;
  el.style.width = `${box.width}px`;
  el.style.height = `${box.height}px`;
  el.style.setProperty('--box-width', `${box.width}px`);
  el.style.setProperty('--box-height', `${box.height}px`);

  const strokeWidth = box.strokeWidth ?? 2;
  const stroke = box.stroke || '#00ffcc';
  el.style.setProperty('--box-stroke-width', `${Math.max(0, strokeWidth)}px`);
  el.style.setProperty('--box-stroke', stroke);
  el.style.color = stroke;
  el.style.borderWidth = '0';
  el.style.borderStyle = 'none';
  el.style.opacity = typeof box.opacity === 'number' ? `${box.opacity}` : '1';
  const baseRadius = box.radius ?? 24;
  const halfStroke = Math.max(0, strokeWidth) / 2;
  const radius = Math.max(
    0,
    Math.min(baseRadius - halfStroke, box.width / 2 - halfStroke, box.height / 2 - halfStroke)
  );
  el.style.borderRadius = '0';

  if (box.fill) {
    el.style.backgroundColor = box.fill;
  } else {
    el.style.removeProperty('background-color');
  }

  const rect = el.querySelector('.overlay-box__rect');
  if (!rect) return;
  rect.setAttribute('x', `${halfStroke}`);
  rect.setAttribute('y', `${halfStroke}`);
  rect.setAttribute('width', `${Math.max(1, box.width - strokeWidth)}`);
  rect.setAttribute('height', `${Math.max(1, box.height - strokeWidth)}`);
  rect.setAttribute('rx', `${radius}`);
  rect.setAttribute('ry', `${radius}`);
  rect.setAttribute('stroke', stroke);
  rect.setAttribute('stroke-width', `${Math.max(0, strokeWidth)}`);
  rect.setAttribute('fill', box.fill || 'none');
}
