// Prompt answers are plain text. The same renderer serves both discovery modes.
export function promptAnswersMarkup(profile, esc, preview = false) {
  const answers = (profile.prompts || []).slice(0, preview ? 1 : 3);
  if (!answers.length) return '';
  return `<${preview ? 'div' : 'section'} class="profile-prompts ${preview ? 'prompt-preview' : ''}" aria-label="Personality prompts">
    ${preview ? '' : '<h3>A little more about me</h3>'}
    ${answers.map(item => `<div class="prompt-answer"><strong>${esc(item.question)}</strong><p>${esc(item.answer)}</p></div>`).join('')}
    ${preview ? `<button type="button" class="text-button" data-action="view-profile" data-id="${esc(profile.id)}">Read profile${(profile.prompts || []).length > 1 ? ' & more answers' : ''}</button>` : ''}
  </${preview ? 'div' : 'section'}>`;
}

export function createPromptDraft(profile) {
  const items = (profile.prompts || []).map(({ prompt_id, answer }) => ({ prompt_id, answer }));
  return { items, saved: JSON.stringify(items), busy: false, error: '', savedNotice: false };
}

export class PromptManager {
  constructor(root, { draft, catalog, limits, api, onChange, onState, esc }) {
    Object.assign(this, { root, draft, catalog, limits, api, onChange, onState, esc });
    this.controller = new AbortController();
    this.destroyed = false;
    root.addEventListener('input', event => this.edit(event), { signal: this.controller.signal });
    root.addEventListener('change', event => this.edit(event), { signal: this.controller.signal });
    root.addEventListener('click', event => this.click(event), { signal: this.controller.signal });
    this.render();
  }

  destroy() { this.destroyed = true; this.controller.abort(); }
  dirty() { return JSON.stringify(this.draft.items) !== this.draft.saved; }

  updateStatus() {
    if (this.destroyed) return;
    const status = this.root.querySelector('.prompt-save-status');
    status.textContent = this.draft.busy ? 'Saving…' : this.dirty() ? 'Unsaved changes' : this.draft.savedNotice ? 'Answers saved.' : 'Up to three answers, entirely optional.';
    this.root.querySelector('[data-prompt-action="save"]').disabled = this.draft.busy || !this.dirty();
    const error = this.root.querySelector('.prompt-error');
    error.textContent = this.draft.error;
    error.classList.toggle('hidden', !this.draft.error);
  }

  render() {
    if (this.destroyed) return;
    const { esc, draft, limits } = this;
    this.root.setAttribute('aria-busy', String(draft.busy));
    this.root.innerHTML = `<div class="row between"><h3>Your personality prompts</h3><span class="muted">${draft.items.length} / ${limits.count}</span></div>
      <p class="prompt-help">Choose up to three questions and write your answers.</p>
      <p class="prompt-help">Answers appear inside your profile when someone opens it.</p>
      <div class="prompt-error error hidden" role="alert"></div>
      <div class="prompt-editor-list">${draft.items.map((item, index) => `<article class="prompt-editor-item" data-prompt-index="${index}">
        <label for="prompt-question-${index}">Question ${index + 1}</label>
        <select id="prompt-question-${index}" data-prompt-field="prompt_id" ${draft.busy ? 'disabled' : ''}>
          ${this.catalog.map(prompt => `<option value="${esc(prompt.id)}" ${item.prompt_id === prompt.id ? 'selected' : ''} ${draft.items.some((other, position) => position !== index && other.prompt_id === prompt.id) ? 'disabled' : ''}>${esc(prompt.question)}</option>`).join('')}
        </select>
        <label for="prompt-answer-${index}">Your answer ${index + 1}</label>
        <textarea id="prompt-answer-${index}" data-prompt-field="answer" maxlength="${limits.answer}" aria-describedby="prompt-count-${index}" placeholder="A little detail goes a long way…" ${draft.busy ? 'disabled' : ''}>${esc(item.answer)}</textarea>
        <small id="prompt-count-${index}" class="muted prompt-character-count">${Array.from(item.answer).length} / ${limits.answer} characters</small>
        <div class="row between wrap"><div class="row"><button type="button" class="btn secondary small" data-prompt-action="earlier" aria-label="Move answer ${index + 1} earlier" ${draft.busy || index === 0 ? 'disabled' : ''}>↑</button><button type="button" class="btn secondary small" data-prompt-action="later" aria-label="Move answer ${index + 1} later" ${draft.busy || index === draft.items.length - 1 ? 'disabled' : ''}>↓</button></div><button type="button" class="text-button prompt-remove" data-prompt-action="remove" aria-label="Remove answer ${index + 1}" ${draft.busy ? 'disabled' : ''}>Remove</button></div>
      </article>`).join('')}</div>
      ${draft.items.length < limits.count ? `<button type="button" class="btn secondary" data-prompt-action="add" ${draft.busy ? 'disabled' : ''}>Add a prompt</button>` : ''}
      <div class="prompt-save-row"><button type="button" class="btn" data-prompt-action="save">${draft.busy ? 'Saving…' : draft.error ? 'Retry saving answers' : 'Save answers'}</button><span class="prompt-save-status muted" role="status"></span></div>
      <p class="prompt-help">Prompt changes save separately from your profile text. Remove an answer and save to stop showing it. Unsent changes stay in this tab until refresh or sign-out.</p>`;
    this.updateStatus();
  }

  edit(event) {
    if (this.draft.busy) return;
    const field = event.target.dataset.promptField;
    const item = event.target.closest('[data-prompt-index]');
    if (!field || !item) return;
    this.draft.items[Number(item.dataset.promptIndex)][field] = event.target.value;
    this.draft.error = '';
    this.draft.savedNotice = false;
    if (field === 'prompt_id') {
      const index = item.dataset.promptIndex;
      this.render();
      this.root.querySelector(`#prompt-question-${index}`)?.focus();
    }
    else {
      item.querySelector('.prompt-character-count').textContent = `${Array.from(event.target.value).length} / ${this.limits.answer} characters`;
      this.updateStatus();
    }
  }

  async click(event) {
    const button = event.target.closest('[data-prompt-action]');
    if (!button || this.draft.busy) return;
    const action = button.dataset.promptAction;
    if (action === 'save') { await this.save(); return; }
    const items = this.draft.items;
    let focusIndex = Number(button.closest('[data-prompt-index]')?.dataset.promptIndex || 0);
    if (action === 'add') {
      if (items.length >= this.limits.count) return;
      const next = this.catalog.find(prompt => !items.some(item => item.prompt_id === prompt.id));
      if (!next) return;
      items.push({ prompt_id: next.id, answer: '' });
      focusIndex = items.length - 1;
    } else if (action === 'remove') {
      items.splice(focusIndex, 1);
      focusIndex = Math.min(focusIndex, items.length - 1);
    } else if (action === 'earlier' || action === 'later') {
      const to = focusIndex + (action === 'earlier' ? -1 : 1);
      if (to < 0 || to >= items.length) return;
      [items[focusIndex], items[to]] = [items[to], items[focusIndex]];
      focusIndex = to;
    }
    this.draft.error = '';
    this.draft.savedNotice = false;
    this.render();
    this.root.querySelector(focusIndex < 0 ? '[data-prompt-action="add"]' : `#prompt-answer-${focusIndex}`)?.focus();
  }

  async save() {
    if (!this.dirty()) return;
    const invalid = this.draft.items.findIndex(item => !item.answer.trim() || Array.from(item.answer.trim()).length > this.limits.answer);
    if (invalid >= 0) {
      this.draft.error = `Answer ${invalid + 1} needs 1–${this.limits.answer} characters. You can remove the prompt instead.`;
      this.render();
      this.root.querySelector(`#prompt-answer-${invalid}`)?.focus();
      return;
    }
    const submitted = this.draft.items.map(item => ({ prompt_id: item.prompt_id, answer: item.answer.trim() }));
    this.draft.busy = true;
    this.draft.error = '';
    this.render();
    try {
      const result = await this.api('/me/prompts', 'PUT', { prompts: submitted });
      this.draft.items = result.user.prompts.map(({ prompt_id, answer }) => ({ prompt_id, answer }));
      this.draft.saved = JSON.stringify(this.draft.items);
      this.draft.savedNotice = true;
      this.onChange(result);
    } catch (error) {
      if (!error.stale) this.draft.error = error.message || 'Answers could not be saved. Your draft is ready to retry.';
    } finally {
      this.draft.busy = false;
      if (this.destroyed) this.onState();
      else this.render();
    }
  }
}
