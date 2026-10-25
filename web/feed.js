import { likeFeedback, revealNew, loadingCards } from './motion.js';
import { newMessageId } from './message-id.js';

// Drafts belong to the signed-in account, so navigation never discards a post.
export class Feed {
  constructor(root, { api, esc, icon, avatar, user, draft, onComment, onInbox, onLikes, onProfile, dialog, toast }) {
    Object.assign(this, { root, api, esc, icon, avatar, user, draft, onComment, onInbox, onLikes, onProfile, dialog, toast });
    this.student = new URL(location.href).searchParams.get('student') || '';
    this.posts = []; this.busy = false; this.dead = false; this.serial = 0;
    this.controller = new AbortController();
    root.innerHTML = `<div class="feed-layout"><div class="feed-column"><section class="panel post-composer" aria-label="Create a post"><div class="row">${avatar(user)}<h2>Create post</h2></div><form id="post-form"><label><span class="sr-only">What’s on your mind?</span><textarea name="body" maxlength="2000" rows="3" placeholder="What’s on your mind?">${esc(draft.body || '')}</textarea></label><div id="post-photo-preview"></div><div class="error hidden" id="post-error" role="alert"></div><div class="post-composer-tools"><label class="post-photo-picker">${icon('image')}<span>Photo</span><input type="file" accept="image/jpeg,image/png,image/webp" name="photo" aria-label="Add a photo to your post"></label><span class="post-audience">Campus</span><button class="btn" type="submit">Post</button></div><small class="muted">Posts and likes are visible to students who can view your profile. Comments go to your private inbox.</small></form></section><div class="feed-toolbar"><h2>${this.student ? 'Student posts' : 'Recent posts'}</h2><button class="text-button" data-feed-action="refresh">Refresh</button>${this.student ? '<a href="/feed" data-nav class="text-button">All posts</a>' : ''}</div><div id="post-list" aria-live="polite">${loadingCards('posts')}</div><div id="feed-pagination"></div></div><aside class="feed-aside panel"><h3>Your inbox</h3><p>Conversations and private comments.</p><a href="/chats" data-nav class="btn secondary">${icon('mail')}Open inbox</a><a href="/feed?student=${esc(user.id)}" data-nav class="text-button">My posts</a></aside></div>`;
    const signal = this.controller.signal;
    root.addEventListener('input', event => { if (event.target.name === 'body') { draft.body = event.target.value; draft.clientId = null; } }, { signal });
    root.addEventListener('change', event => { if (event.target.name === 'photo') this.selectPhoto(event.target.files[0]); }, { signal });
    root.addEventListener('click', event => this.click(event), { signal });
    root.addEventListener('submit', event => { if (event.target.id === 'post-form') { event.preventDefault(); event.stopPropagation(); this.publish(); } }, { signal });
    this.preview(); this.refresh();
  }
  node(selector) { return this.root.querySelector(selector); }
  error(message) { const node = this.node('#post-error'); if (node) { node.textContent = message; node.classList.toggle('hidden', !message); } }
  preview() {
    if (!this.node('#post-photo-preview')) return;
    this.node('#post-photo-preview').innerHTML = this.draft.preview ? `<div class="post-photo-preview"><img src="${this.esc(this.draft.preview)}" alt="Photo ready to post"><button type="button" class="btn secondary" data-feed-action="remove-photo">Remove photo</button></div>` : '';
  }
  async selectPhoto(file) {
    if (!file || this.busy) return;
    if (file.size > 8 * 1024 * 1024) { this.error('Choose a photo no larger than 8 MB.'); return; }
    this.busy = true;
    const submit = this.node('#post-form [type=submit]'); submit.disabled = true;
    try {
      await this.removePhoto();
      this.draft.file = file; this.draft.uploadId = newMessageId(); this.draft.clientId = null;
      this.draft.preview = URL.createObjectURL(file); this.preview(); this.error('');
    } finally { this.busy = false; submit.disabled = false; }
  }
  async removePhoto() {
    if (this.draft.photoId) {
      // Best effort cleanup; abandoned uploads also expire server-side.
      try { await this.api('/me/post-photos/' + this.draft.photoId, 'DELETE'); } catch {}
    }
    if (this.draft.preview) URL.revokeObjectURL(this.draft.preview);
    Object.assign(this.draft, { file: null, photoId: null, uploadId: null, preview: null, clientId: null });
    this.preview();
  }
  async publish() {
    if (this.busy) return;
    const body = this.draft.body?.trim() || '';
    if (!body && !this.draft.file && !this.draft.photoId) { this.error('Write something or add a photo.'); return; }
    this.busy = true; this.error('');
    const form = this.node('#post-form'); form.setAttribute('aria-busy','true');
    for (const node of form.elements) node.disabled = true;
    const submit = form.querySelector('[type=submit]'); submit.textContent = 'Posting…';
    this.draft.clientId ||= newMessageId();
    try {
      if (this.draft.file && !this.draft.photoId) {
        const uploaded = await this.api('/me/post-photos', 'POST', this.draft.file, { 'X-Upload-Id': this.draft.uploadId });
        this.draft.photoId = uploaded.photo_id;
      }
      await this.api('/posts', 'POST', { body, photo_id: this.draft.photoId || '', client_id: this.draft.clientId });
      if (this.draft.preview) URL.revokeObjectURL(this.draft.preview);
      Object.assign(this.draft, { body: '', file: null, photoId: null, preview: null, uploadId: null, clientId: null });
      if (!this.dead) { form.reset(); this.preview(); await this.refresh(); }
      this.toast('Post shared.');
    } catch (e) { if (!e.stale && !this.dead) this.error(e.message || 'Couldn’t post. Your draft is saved here. Try again.'); }
    finally { this.busy = false; form.setAttribute('aria-busy','false'); for (const node of form.elements) node.disabled = false; submit.textContent = 'Post'; }
  }
  card(p) {
    const { esc, icon, avatar } = this;
    return `<article class="panel feed-post" data-post-id="${p.id}"><header class="post-header"><button type="button" class="post-author" data-feed-action="profile" data-id="${p.id}">${avatar(p.author)}<span><strong>${esc(p.author.display_name)}</strong><small>${esc(p.author.program)}</small></span></button><div class="post-date"><time datetime="${new Date(p.created_at * 1000).toISOString()}">${esc(new Date(p.created_at * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }))}</time>${p.updated_at > p.created_at ? '<small>Edited</small>' : ''}</div><button type="button" class="icon-button" data-feed-action="options" data-id="${p.id}" aria-label="Post options">${icon('more')}</button></header>${p.body ? `<p class="post-body">${esc(p.body)}</p>` : ''}${p.photo_url ? `<button type="button" class="post-image-open" data-feed-action="photo" data-id="${p.id}" aria-label="Open post photo"><img class="post-image" src="${esc(p.photo_url)}" alt="Photo shared by ${esc(p.author.display_name)}" loading="lazy"></button>` : ''}<div class="post-reactions"><button type="button" data-feed-action="likes" data-id="${p.id}">${p.like_count} ${p.like_count === 1 ? 'like' : 'likes'}</button></div><footer class="post-actions"><button type="button" data-feed-action="like" data-id="${p.id}" aria-pressed="${p.liked}">${icon('heart')}<span>${p.liked ? 'Liked' : 'Like'}</span></button>${!p.mine ? `<button type="button" data-feed-action="comment" data-id="${p.id}" title="Send a private comment">${icon('comment')}<span>Comment</span></button><button type="button" data-feed-action="inbox" data-id="${p.id}">${icon('mail')}<span>Inbox</span></button>` : ''}</footer></article>`;
  }
  async refresh(append = false) {
    const serial = ++this.serial;
    try {
      const params = new URLSearchParams(); if (this.student) params.set('student', this.student);
      if (append && this.posts.length) params.set('before', this.posts.at(-1).id);
      const result = await this.api('/feed?' + params);
      if (this.dead || serial !== this.serial) return;
      this.posts = append ? [...this.posts, ...result.items] : result.items;
      // Keep the composer intact while refreshing the feed.
      this.node('#post-list').innerHTML = this.posts.length ? this.posts.map(p => this.card(p)).join('') : '<div class="empty"><h2>No posts yet</h2><p>Share a photo or something on your mind.</p></div>';
      revealNew(this.node('#post-list'),'.feed-post',{key:'data-post-id'});
      this.node('#feed-pagination').innerHTML = result.has_more ? '<button class="btn secondary" data-feed-action="more">More posts</button>' : '';
    } catch (e) {
      if (!e.stale && !this.dead) this.node('#feed-pagination').innerHTML = `<p role="alert">${this.esc(e.message)}</p><button class="text-button" data-feed-action="refresh">Try again</button>`;
    }
  }
  async click(event) {
    const button = event.target.closest('[data-feed-action]'); if (!button || this.busy) return;
    const action = button.dataset.feedAction, p = this.posts.find(p => String(p.id) === button.dataset.id);
    const restoreLikeFocus = action === 'like' && document.activeElement === button;
    try {
      if (action === 'refresh' || action === 'more') { button.disabled = true; await this.refresh(action === 'more'); }
      if (action === 'remove-photo') await this.removePhoto();
      if (!p) return;
      if (action === 'like') {
        button.disabled = true; button.setAttribute('aria-busy','true');
        const result = await this.api(`/posts/${p.id}/like`, 'PUT', { liked: !p.liked });
        Object.assign(p, result.post);
        if (!this.dead) {
          const focused = restoreLikeFocus && (document.activeElement === document.body || document.activeElement === button);
          button.closest('.feed-post').outerHTML = this.card(p);
          const next = this.node(`[data-post-id="${p.id}"] [data-feed-action="like"]`);
          if (p.liked) likeFeedback(next);
          if (focused) next?.focus({ preventScroll: true });
        }
      }
      if (action === 'likes') await this.onLikes(`/posts/${p.id}/likes`);
      if (action === 'profile') await this.onProfile(p.author.id);
      if (action === 'comment') await this.onComment(p.author.id, 'friend', p.id);
      if (action === 'inbox') await this.onInbox(p.author.id);
      if (action === 'photo') this.dialog('Post photo', `<img class="photo-lightbox" src="${this.esc(p.photo_url)}" alt="Photo shared by ${this.esc(p.author.display_name)}">`);
      if (action === 'options') {
        if (p.mine) {
          this.dialog('Edit post', `<form id="edit-post-form" class="stack" data-id="${p.id}"><div class="form-error error hidden" role="alert"></div><label>Post<textarea name="body" maxlength="2000">${this.esc(p.body)}</textarea></label><button type="submit" class="btn">Save changes</button></form><button type="button" class="text-button danger" data-action="delete-post-dialog" data-id="${p.id}">Delete post</button>`);
        } else this.dialog('Post options', `<button class="btn secondary" data-action="view-profile" data-profile-context="campus" data-id="${this.esc(p.author.id)}">View profile</button><button class="text-button" data-action="profile-safety-dialog" data-id="${this.esc(p.author.id)}">Safety & support</button>`);
      }
    } catch (e) { if (!e.stale) this.toast(e.message); }
    finally {
      if (button.isConnected) {
        button.disabled = false; button.removeAttribute('aria-busy');
        if (restoreLikeFocus && document.activeElement === document.body) button.focus({ preventScroll: true });
      }
    }
  }
  destroy() { this.dead = true; this.controller.abort(); }
}
