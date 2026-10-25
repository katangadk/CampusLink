// Motion is feedback only: persistence and navigation never wait for it.
const seen = new WeakMap();
export const motionAllowed = () => !document.hidden && !matchMedia('(prefers-reduced-motion: reduce)').matches;

function play(element, effect, step = 0) {
  if (!element || !motionAllowed() || element.classList.contains(effect)) return;
  element.dataset.motionStep = String(Math.min(step, 4));
  element.classList.add(effect);
  let timer;
  const clear = () => {
    element.classList.remove(effect);
    delete element.dataset.motionStep;
    element.removeEventListener('animationend', clear);
    element.removeEventListener('animationcancel', clear);
    clearTimeout(timer);
  };
  element.addEventListener('animationend', clear);
  element.addEventListener('animationcancel', clear);
  timer = setTimeout(clear, 650);
}

export function likeFeedback(button) { play(button?.querySelector('svg'), 'motion-heart'); }

export function revealNew(root, selector, { key, initial = true, enabled = true, effect = 'motion-enter', limit = 6 } = {}) {
  if (!root) return;
  const first = !seen.has(root), known = seen.get(root) || new Set();
  let step = 0;
  for (const node of root.querySelectorAll(selector)) {
    const id = node.getAttribute(key);
    if (!id) continue;
    if (!known.has(id) && (!first || initial) && enabled && step < limit) play(node, effect, step++);
    known.add(id);
  }
  while (known.size > 1024) known.delete(known.values().next().value);
  seen.set(root, known);
}

export function loadingCards(kind = 'profiles') {
  const posts = kind === 'posts', label = posts ? 'Loading posts…' : 'Loading profiles…';
  const card = `<div class="skeleton-card" aria-hidden="true"><div class="skeleton skeleton-photo"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div><div class="skeleton skeleton-actions"></div></div>`;
  return `<div class="loading-cards ${posts ? 'loading-posts' : ''}" role="status" aria-label="${label}" aria-busy="true"><span class="loading-label" aria-hidden="true">${label}</span><div class="skeleton-grid">${card.repeat(posts ? 1 : 3)}</div></div>`;
}
