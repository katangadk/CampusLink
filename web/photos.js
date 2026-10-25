import { newMessageId } from './message-id.js';

export function avatarMarkup(profile, large, esc, initials) {
  const tone = [...(profile.username || 'a')].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 5;
  return `<span class="avatar ${large ? 'large' : ''} tone-${tone}" data-avatar-user="${esc(profile.id)}" data-photo-url="${esc(profile.main_photo_url || '')}" aria-hidden="true">
    <span class="avatar-fallback">${esc(initials(profile))}</span>
    ${profile.main_photo_url ? `<img class="avatar-photo" data-profile-photo src="${esc(profile.main_photo_url)}" alt="" loading="lazy" decoding="async">` : ''}
  </span>`;
}

export function photoGalleryMarkup(profile, esc) {
  return (profile.photos || []).length ? `<div class="profile-photo-gallery" aria-label="Profile photos">
    ${profile.photos.map((photo, index) => `<button type="button" class="gallery-photo-button" data-action="view-photo" data-url="${esc(photo.url)}" aria-label="Open photo ${index + 1} of ${esc(profile.display_name)}">
      <img data-profile-photo src="${esc(photo.url)}" alt="Photo ${index + 1} of ${esc(profile.display_name)}" loading="lazy" decoding="async">
    </button>`).join('')}
  </div>` : '';
}

export class PhotoManager {
  constructor(root, { getUser, api, onChange, esc }) {
    this.root = root;
    this.getUser = getUser;
    this.api = api;
    this.onChange = onChange;
    this.esc = esc;
    this.pending = null;
    this.replacing = null;
    this.busy = false;
    this.error = '';
    this.destroyed = false;
    this.controller = new AbortController();
    root.addEventListener('change', event => this.selectFile(event), { signal: this.controller.signal });
    root.addEventListener('click', event => this.click(event), { signal: this.controller.signal });
    this.render();
  }

  discard() {
    if (this.pending) URL.revokeObjectURL(this.pending.url);
    this.pending = null;
    this.replacing = null;
    this.error = '';
  }

  destroy() {
    this.destroyed = true;
    this.controller.abort();
    this.discard();
  }

  render() {
    if (this.destroyed) return;
    const esc = this.esc;
    const photos = this.getUser().photos || [];
    this.root.setAttribute('aria-busy', String(this.busy));
    this.root.innerHTML = `<div class="row between"><h3>Your photos</h3><span class="muted">${photos.length} / 4</span></div>
      <p class="photo-help">Photos are optional. Choose JPEG, PNG, or WebP, up to 8 MB and at least 200 × 200 pixels. The first photo is your main photo.</p>
      <div class="photo-error error ${this.error ? '' : 'hidden'}" role="alert">${esc(this.error)}</div>
      ${photos.length ? `<div class="photo-editor-grid">${photos.map((photo, index) => `<article class="photo-tile" data-photo-id="${esc(photo.id)}">
        <div class="photo-tile-image"><img data-profile-photo src="${esc(photo.url)}" alt="Your profile photo ${index + 1}">${index === 0 ? '<span class="photo-main-label">Main photo</span>' : ''}</div>
        <div class="photo-tile-controls">
          ${index > 0 ? `<button type="button" class="text-button" data-photo-action="main" data-id="${esc(photo.id)}" ${this.busy ? 'disabled' : ''}>Make main</button>` : '<span class="muted">Shown on your profile</span>'}
          <div class="photo-order-controls"><button type="button" class="btn secondary small" data-photo-action="earlier" data-id="${esc(photo.id)}" aria-label="Move photo ${index + 1} earlier" ${this.busy || index === 0 ? 'disabled' : ''}>←</button><button type="button" class="btn secondary small" data-photo-action="later" data-id="${esc(photo.id)}" aria-label="Move photo ${index + 1} later" ${this.busy || index === photos.length - 1 ? 'disabled' : ''}>→</button></div>
          <div class="row wrap"><button type="button" class="text-button" data-photo-action="replace" data-id="${esc(photo.id)}" ${this.busy ? 'disabled' : ''}>Replace</button><button type="button" class="text-button photo-remove" data-photo-action="remove" data-id="${esc(photo.id)}" ${this.busy ? 'disabled' : ''}>Remove</button></div>
        </div></article>`).join('')}</div>` : '<div class="photo-empty"><strong>Add a face to your profile.</strong><p>Your initials will appear until you choose a photo.</p></div>'}
      ${this.pending ? `<div class="photo-upload-preview"><img src="${esc(this.pending.url)}" alt="Selected photo preview"><div class="stack"><strong>${this.replacing ? 'Replace this photo' : 'New profile photo'}</strong><small class="muted">${esc(this.pending.file.name)}</small><p class="photo-help">Your upload will be resized and location metadata removed.</p><div class="row wrap"><button type="button" class="btn" data-photo-action="upload" ${this.busy ? 'disabled' : ''}>${this.busy ? 'Uploading…' : this.error ? 'Retry upload' : this.replacing ? 'Save replacement' : 'Upload photo'}</button><button type="button" class="btn secondary" data-photo-action="cancel" ${this.busy ? 'disabled' : ''}>Cancel</button></div></div></div>` : ''}
      ${!this.pending && (photos.length < 4 || this.replacing) ? `<label class="photo-file-picker">${this.replacing ? 'Choose replacement photo' : 'Choose a photo'}<input type="file" id="profile-photo-file" accept="image/jpeg,image/png,image/webp" ${this.busy ? 'disabled' : ''}></label>` : ''}
      ${this.replacing && !this.pending ? '<button type="button" class="text-button" data-photo-action="cancel">Cancel replacement</button>' : ''}
      <p class="photo-help">Photo changes save separately from your profile text. Your visibility and blocking settings also apply to photos.</p>`;
  }

  selectFile(event) {
    if (event.target.id !== 'profile-photo-file' || this.busy) return;
    const file = event.target.files[0];
    if (!file) return;
    if (!file.size || file.size > 8 * 1024 * 1024) {
      this.error = 'Choose an image no larger than 8 MB.';
      this.render();
      return;
    }
    if (file.type && !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      this.error = 'Choose a JPEG, PNG, or WebP photo.';
      this.render();
      return;
    }
    if (this.pending) URL.revokeObjectURL(this.pending.url);
    this.pending = { file, url: URL.createObjectURL(file), key: newMessageId() };
    this.error = '';
    this.render();
  }

  async click(event) {
    const button = event.target.closest('[data-photo-action]');
    if (!button || this.busy) return;
    const { photoAction: action, id } = button.dataset;
    if (action === 'cancel') { this.discard(); this.render(); return; }
    if (action === 'replace') {
      this.discard(); this.replacing = id; this.render();
      this.root.querySelector('#profile-photo-file')?.click();
      return;
    }
    if (action === 'upload' && !this.pending) return;
    this.busy = true;
    this.error = '';
    this.render();
    try {
      let result;
      if (action === 'upload') {
        const path = this.replacing ? `/me/photos/${this.replacing}` : '/me/photos';
        result = await this.api(path, this.replacing ? 'PUT' : 'POST', this.pending.file, { 'X-Upload-Id': this.pending.key });
      } else if (action === 'main') {
        result = await this.api(`/me/photos/${id}/main`, 'POST', {});
      } else if (action === 'remove') {
        result = await this.api(`/me/photos/${id}`, 'DELETE');
      } else if (action === 'earlier' || action === 'later') {
        const ids = (this.getUser().photos || []).map(photo => photo.id);
        const from = ids.indexOf(id), to = from + (action === 'earlier' ? -1 : 1);
        if (from < 0 || to < 0 || to >= ids.length) return;
        [ids[from], ids[to]] = [ids[to], ids[from]];
        result = await this.api('/me/photos/order', 'PATCH', { photo_ids: ids });
      }
      if (result) {
        await this.onChange(result);
        this.discard();
      }
    } catch (error) {
      if (!error.stale) this.error = error.message || 'Upload failed. You can retry the same photo.';
    } finally {
      this.busy = false;
      this.render();
      if (!this.destroyed && this.error) this.root.querySelector('.photo-error')?.scrollIntoView({ block: 'nearest' });
    }
  }
}
