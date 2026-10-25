export const DISCOVERY_MODES = ['dating', 'for-you', 'friend', 'study'];
export const CONNECTION_VIEWS = ['received', 'sent', 'friend', 'study'];

export function routeView(url) {
  const params = url.searchParams;
  return {
    discovery: DISCOVERY_MODES.includes(params.get('mode')) ? params.get('mode') : 'dating',
    connections: CONNECTION_VIEWS.includes(params.get('view')) ? params.get('view') : 'received',
  };
}

export function focusPage(hash = location.hash) {
  let target;
  try { target = hash && document.getElementById(decodeURIComponent(hash.slice(1))); } catch {}
  target ||= document.getElementById('main');
  if (!target) return;
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
  if (hash) target.scrollIntoView({ block: 'start' });
}
