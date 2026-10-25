// Loaded before the stylesheets so the saved theme is applied before paint.
(() => {
  const key = 'campuslink-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => value === 'dark' || value === 'light' ? value : null;
  let choice = null;
  try { choice = valid(localStorage.getItem(key)); } catch { /* Storage can be disabled. */ }

  function apply() {
    const theme = choice || (system.matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#15111b' : '#43283f');
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      button.title = `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`;
    });
  }

  apply();
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-theme-toggle]')) return;
    choice = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(key, choice); } catch { /* Retain the choice in this page. */ }
    apply();
  });
  const systemChanged = () => { if (!choice) apply(); };
  if (system.addEventListener) system.addEventListener('change', systemChanged);
  else system.addListener(systemChanged);
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    choice = valid(event.newValue);
    apply();
  });
})();
