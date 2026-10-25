// Suggestions only fill a draft. The ordinary composer owns sending and retry.
export class ConversationStarters {
  constructor(root, { api, conversationId, expanded, signature, onToggle, onPick, esc }) {
    Object.assign(this, { root, api, conversationId, expanded, signature, onToggle, onPick, esc });
    this.items = null;
    this.loading = false;
    this.error = '';
    this.notice = '';
    this.serial = 0;
    this.destroyed = false;
    this.controller = new AbortController();
    root.addEventListener('click', event => this.click(event), { signal: this.controller.signal });
    if (expanded) this.load();
    else this.render();
  }

  destroy() {
    this.destroyed = true;
    this.serial++;
    this.items = null;
    this.controller.abort();
    this.root.replaceChildren();
    this.root.hidden = true;
  }

  render() {
    if (this.destroyed) return;
    const focused = this.root.contains(document.activeElement) ? document.activeElement : null;
    const focusIndex = focused?.dataset.starterIndex;
    const focusAction = focused?.dataset.starterAction;
    const esc = this.esc;
    this.root.hidden = false;
    this.root.setAttribute('aria-busy', String(this.loading));
    this.root.innerHTML = `<button type="button" class="starter-toggle" data-starter-action="toggle" aria-expanded="${this.expanded}" aria-controls="starter-choices"><span>Conversation starters</span><span aria-hidden="true">${this.expanded ? '−' : '+'}</span></button>
      ${this.expanded ? `<div id="starter-choices" class="starter-choices">
        <p class="starter-help">Choose one, make it yours, then press Send.</p>
        ${this.loading ? '<p class="starter-help" role="status">Finding a first line…</p>' : ''}
        ${this.error ? `<div class="starter-error" role="alert"><p>${esc(this.error)}</p><button type="button" class="text-button" data-starter-action="retry">Retry suggestions</button></div>` : ''}
        <div class="starter-list">${(this.items || []).map((item, index) => `<button type="button" class="starter-choice" data-starter-index="${index}"><small>${esc(item.context)}</small><span>${esc(item.text)}</span></button>`).join('')}</div>
        <p class="starter-notice" role="status">${esc(this.notice)}</p>
      </div>` : ''}`;
    if (focused) {
      const target = focusIndex !== undefined ? this.root.querySelector(`[data-starter-index="${focusIndex}"]`) : this.root.querySelector(`[data-starter-action="${focusAction}"]`);
      (target || this.root.querySelector('[data-starter-action="toggle"]'))?.focus();
    }
  }

  async load() {
    const serial = ++this.serial;
    this.loading = true;
    this.error = '';
    this.items = null;
    this.render();
    try {
      const result = await this.api(`/chats/${this.conversationId}/starters`);
      if (this.destroyed || serial !== this.serial) return;
      this.items = result.items;
    } catch (error) {
      if (this.destroyed || error.stale || serial !== this.serial) return;
      if ([401, 403, 404].includes(error.status)) { this.destroy(); return; }
      this.error = 'Suggestions could not load. You can retry or write your own message.';
    } finally {
      if (!this.destroyed && serial === this.serial) { this.loading = false; this.render(); }
    }
  }

  refresh(signature) {
    if (this.destroyed || signature === this.signature) return;
    this.signature = signature;
    this.items = null;
    this.notice = '';
    if (this.expanded) this.load();
    else { this.serial++; this.loading = false; this.render(); }
  }

  click(event) {
    const action = event.target.closest('[data-starter-action]')?.dataset.starterAction;
    if (action === 'toggle') {
      this.expanded = !this.expanded;
      this.onToggle(this.expanded);
      if (this.expanded && !this.items && !this.loading) this.load();
      else this.render();
      return;
    }
    if (action === 'retry') { if (!this.loading) this.load(); return; }
    const button = event.target.closest('[data-starter-index]');
    if (!button || this.loading) return;
    const item = this.items?.[Number(button.dataset.starterIndex)];
    if (!item) return;
    this.notice = this.onPick(item.text) || 'Added to your draft. Edit it and press Send when ready.';
    const notice = this.root.querySelector('.starter-notice');
    if (notice) notice.textContent = this.notice;
  }
}
