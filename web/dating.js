// Dating remains a distinct, explicitly activated experience within Discover.
export function datingWelcome(user, { icon, demoAccounts=true }) {
  return `<section class="dating-welcome panel" aria-labelledby="dating-welcome-title">
    <h2 id="dating-welcome-title">Dating</h2>
    <p>Meet other students who have turned on Dating. Likes are public. A mutual like opens a chat, or you can send a private comment for them to accept.</p>
    <button class="btn" data-action="dating-settings">${icon('heart')}Set up Dating</button>
    <p class="dating-footnote">18+ · Optional · Your profile appears after you opt in.</p>
    <button class="text-button" data-action="dating-guide">How Dating works</button>
    <small class="muted">${demoAccounts?'Local':'Private'} test build · Profiles and adult declarations are unverified.</small>
  </section>`;
}

export function datingSettingsForm(user, { icon, esc, check, formError, demoAccounts=true }) {
  if (!user.adult_eligible) {
    return `<form id="dating-eligibility-form" class="stack">
      ${formError()}<h3>Set up 18+ test access</h3>
      <p>Dating is unavailable until adult eligibility is established. For this ${demoAccounts?'local':'private'} test build, you can declare adult test eligibility on your own fictional account.</p>
      <label>Date of birth (private)<input type="date" name="dob" autocomplete="bday" value="${esc(user.dob || '')}" required></label>
      ${check('adult_test_agreement', 'I confirm this test profile is for someone aged 18 or older and understand this is self-declared local test access.', false)}
      <div class="notice">This does not verify your age, student status, or identity. Dating still needs your separate opt-in and preferences on the next step.</div>
      <button class="btn" type="submit">Continue to Dating preferences ${icon('arrow')}</button>
    </form>${demoAccounts?'<button class="text-button" data-action="dating-test-accounts">Use a fictional adult test account instead</button>':''}`;
  }
  return `<form id="dating-form" class="stack">
    ${formError()}
    <p>Choose who you’d like to meet. Your dating preferences stay private.</p>
    ${check('dating_enabled', 'I explicitly opt in to Dating (18+)', user.dating_enabled)}
    <label>Your gender<select name="gender">
      ${[['', 'Choose'], ['woman', 'Woman'], ['man', 'Man'], ['nonbinary', 'Nonbinary']].map(([value, label]) => `<option value="${value}" ${user.gender === value ? 'selected' : ''}>${label}</option>`).join('')}
    </select></label>
    <fieldset><legend>Interested in</legend>
      ${[['woman', 'Women'], ['man', 'Men'], ['nonbinary', 'Nonbinary people']].map(([value, label]) => `<label class="check"><input type="checkbox" name="dating_genders" value="${value}" ${user.dating_genders.includes(value) ? 'checked' : ''}>${label}</label>`).join('')}
    </fieldset>
    <div class="field-grid">
      <label>Minimum age<input type="number" name="dating_min" value="${user.dating_min}" min="18" max="100" required></label>
      <label>Maximum age<input type="number" name="dating_max" value="${user.dating_max}" min="18" max="100" required></label>
    </div>
    <fieldset class="dating-intention-settings"><legend>Your dating intention <span class="muted">(optional)</span></legend>
      <label>What are you looking for?<select name="dating_intention">
        <option value="">Leave unset / remove my choice</option>
        ${intentionOptions(user.dating_intention, esc)}
      </select></label>
      ${check('show_dating_intention', 'Display my intention on my Dating profile', user.show_dating_intention)}
      <p class="dating-footnote">Shown only to eligible students in Dating when you choose to display it. Hidden intentions are not used by the intention filter. Friends and Study never show this choice.</p>
    </fieldset>
    ${!user.discoverable ? '<p class="notice">Your campus discoverability is off. Other students cannot find or match with you until you enable it in Profile.</p>' : ''}
    <p class="notice">Turning Dating off ends your existing matches and closes their chats. Turning it back on does not restore them.</p>
    <small class="muted">18+ local test access · Identity and age are unverified.</small>
    <button class="btn" type="submit">Save and explore Dating ${icon('arrow')}</button>
  </form>`;
}

// Set from the server-owned catalog at startup so editor and filter labels agree.
let intentions = [];
export function setIntentionCatalog(catalog) { intentions = catalog; }
export function intentionOptions(selected, esc) {
  return intentions.map(item => `<option value="${esc(item.id)}" ${selected === item.id ? 'selected' : ''}>${esc(item.label)}</option>`).join('');
}
export function datingIntentionMarkup(profile, esc) {
  return profile.dating_intention_label ? `<div class="dating-intention"><small>Dating intention</small><strong>${esc(profile.dating_intention_label)}</strong></div>` : '';
}

export function datingProfileCard(profile, { icon, esc, avatar }) {
  return `<article class="student-card dating-card compact-card" data-profile-id="${esc(profile.id)}">
    <div class="dating-photo"><button type="button" class="dating-photo-open" data-action="view-profile" data-id="${esc(profile.id)}" aria-label="View ${esc(profile.display_name)}’s profile"><span class="photo-cover-initials" aria-hidden="true">${esc(profile.display_name.split(/\s+/).map(s => s[0]).slice(0,2).join(''))}</span>${profile.main_photo_url ? `<img data-profile-photo src="${esc(profile.main_photo_url)}" alt="${esc(profile.display_name)}’s profile photo" loading="lazy" decoding="async">` : ''}<span class="photo-profile-hint">View profile ${icon('arrow')}</span></button><button class="icon-button dating-photo-options" data-action="student-menu" data-id="${esc(profile.id)}" aria-label="Options for ${esc(profile.display_name)}">${icon('more')}</button></div>
    <div><button class="name-button" data-action="view-profile" data-id="${esc(profile.id)}"><h3>${esc(profile.display_name)}${profile.age ? `, ${profile.age}` : ''}</h3></button>
      <p class="academic">${esc(profile.program || '')}</p>
      <button type="button" class="public-like-count" data-action="public-profile-likes" data-id="${esc(profile.id)}">${profile.like_count||0} ${(profile.like_count||0)===1?'like':'likes'}</button>
    </div>
    <div class="profile-social-actions" aria-label="Profile actions">
      <button type="button" data-action="like" data-id="${esc(profile.id)}" data-kind="dating" aria-label="Like ${esc(profile.display_name)} publicly" aria-pressed="${!!profile.liked&&!!profile.dating_liked}">${icon('heart')}Like</button>
      <button type="button" data-action="private-comment" data-id="${esc(profile.id)}" data-kind="dating" title="Send a private comment">${icon('comment')}Comment</button>
      <button type="button" data-action="profile-inbox" data-id="${esc(profile.id)}" data-kind="dating">${icon('mail')}Inbox</button>
    </div>
  </article>`;
}
