import { likeFeedback, revealNew, loadingCards } from './motion.js';
import { Feed } from './feed.js';
import { newMessageId } from './message-id.js';
import { datingWelcome, datingSettingsForm, datingProfileCard, setIntentionCatalog, intentionOptions, datingIntentionMarkup } from './dating.js';
import { PhotoManager, avatarMarkup, photoGalleryMarkup } from './photos.js';
import { PromptManager, createPromptDraft, promptAnswersMarkup } from './prompts.js';
import { ConversationStarters } from './starters.js';
import { OperatorConsole } from './operator.js';
import { routeView, focusPage, DISCOVERY_MODES, CONNECTION_VIEWS } from './navigation.js';

const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = (v='') => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
 moon:'<path d="M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
 compass:'<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5Z"/>',
 people:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9M15 3.2a4 4 0 0 1 0 7.6"/><circle cx="9" cy="7" r="4"/>',
 chat:'<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-4-.9L3 21l1.9-5.5a9 9 0 0 1-.9-4A8.5 8.5 0 0 1 12.5 3h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2"/>',
 book:'<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2Zm20 0h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7Z"/>',
 heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
 spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
 search:'<circle cx="10.5" cy="10.5" r="7.5"/><path d="m16 16 5 5"/>',
 filter:'<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="2" fill="white"/><circle cx="16" cy="17" r="2" fill="white"/>',
 bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
 shield:'<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z"/><path d="m8 12 3 3 5-6"/>',
 arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 back:'<path d="M19 12H5m6-6-6 6 6 6"/>',
 more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>',
 send:'<path d="m22 2-7 20-4-9-9-4Zm0 0L11 13"/>',
 lock:'<rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/>',
 logout:'<path d="M9 21H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5m7 14 5-5-5-5M9 12h12"/>',
 flag:'<path d="M4 22V3s4-3 8 0 8 0 8 0v12s-4 3-8 0-8 0-8 0"/>',
 block:'<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
 settings:'<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
 mail:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 5 10 8L22 5"/>',
 image:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
 comment:'<path d="M21 15a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3Z"/><path d="M7 8h10M7 12h7"/>',
 feed:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M7 7h10M7 11h10M7 15h5"/>'
};
const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.spark}</svg>`;
const brand = () => '<a class="brand" href="/" data-nav><img src="/assets/logo.svg" alt="">CampusLink<span aria-hidden="true" class="muted">.</span></a>';
const themeToggle = () => {const dark=document.documentElement.dataset.theme==='dark';return `<button type="button" class="icon-button theme-toggle" data-theme-toggle aria-label="Dark theme" aria-pressed="${dark}" title="Switch to ${dark?'light':'dark'} theme"><span class="theme-icon-moon">${icon('moon')}</span><span class="theme-icon-sun">${icon('sun')}</span></button>`;};
const isStaging = () => state.catalog.mode==='staging';
const needsApproval = () => !!state.user&&!!(state.user.verification?.approval_required??state.catalog.approval_required)&&state.user.verification?.membership?.status!=='approved';
const needsStudentVerification = () => !!state.user&&state.catalog.eligibility_mode==='external'&&!state.user.verification?.student_verified;
const stagingBadge = () => isStaging()?'<span class="staging-label">'+(state.catalog.eligibility_mode==='external'?'Pilot':'Preview')+'</span>':'';
const testProfileLabel = (profile) => state.catalog.eligibility_mode==='external'?(profile?.verified?'Student status checked':'Verification pending'):(isStaging()?'Test profile · Unverified':'Local test · Unverified');
const publicHeader = () => `<div class="public-header">${brand()}${stagingBadge()}${themeToggle()}</div>`;
const labels = {friend:'Friends',study:'Study',dating:'Dating'};
const state = {user:null,csrf:'',catalog:{interests:[]},connections:[],chats:[],notifications:[],requests:[],postDraft:{},delivered:new Map(),read:new Map(),mode:'dating',chatFilter:'all',connectionFilter:'dating',connectionLoaded:false,connectionLoading:false,connectionError:'',chatLoaded:false,chatLoading:false,chatError:'',selected:null,messages:[],older:false,query:'',program:'',interest:'',year:0,intention:'',page:1,students:[],hasMore:false,filtersOpen:false,live:false,searchSerial:0,drafts:new Map(),outbox:new Map(),starterOpen:new Map()};
let feedManager, readTimer, operatorConsole;
let source, toastTimer, searchTimer, refreshTimer, photoManager, promptManager, starterManager, refreshing=false;
const app = $('#app');
const path = () => location.pathname;
const initials = p => (p.display_name||'?').split(/\s+/).slice(0,2).map(s=>s[0]).join('').toUpperCase();
const avatar = (p,large=false) => avatarMarkup(p,large,esc,initials);
const category = k => `<span class="pill ${esc(k)}">${icon(k==='study'?'book':k==='dating'?'heart':'people')}${labels[k]}</span>`;
const stamp = t => new Date(t*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Africa/Lusaka'});
const empty = (name,title,copy,action='') => `<div class="empty">${icon(name)}<h2>${esc(title)}</h2><p>${esc(copy)}</p>${action}</div>`;

async function api(url,method='GET',data,extraHeaders={}){
  const authEpoch=state.authEpoch||0;
  const binary=data instanceof Blob;
  const response = await fetch('/api'+url,{method,headers:{...(data!==undefined?{'Content-Type':binary?(data.type||'application/octet-stream'):'application/json'}:{}),...extraHeaders,...(method!=='GET'?{'X-CSRF-Token':state.csrf}:{})},body:data!==undefined?(binary?data:JSON.stringify(data)):undefined,credentials:'same-origin'});
  const result = await response.json();
  if(authEpoch!==(state.authEpoch||0)){const e=new Error('Session changed.');e.stale=true;throw e;}
  if(!response.ok){const e=new Error(typeof result.detail==='string'?result.detail:'Please check your details and try again.');e.status=response.status;throw e;}
  return result;
}
function toast(message,kind=''){clearTimeout(toastTimer);const region=$('#toast');region.replaceChildren();if(kind==='like'){const badge=document.createElement('span');badge.className='toast-icon';badge.setAttribute('aria-hidden','true');badge.innerHTML=icon('heart');region.append(badge);}region.append(document.createTextNode(message));region.classList.add('visible');toastTimer=setTimeout(()=>region.classList.remove('visible'),5000);}
function showError(error,form){if(error.stale)return;if(form){const region=$('.form-error',form);if(region){region.textContent=error.message;region.classList.remove('hidden');return;}}toast(error.message||'Connection unavailable. Please try again.');}
function go(url,replace=false){
 if($('#dialog').open)$('#dialog').close();
 history[replace?'replaceState':'pushState']({},'',url);renderRoute();window.scrollTo(0,0);focusPage();
 if(state.user&&['/matches','/connections'].includes(path()))refreshData();
}
function resetDiscovery(mode='dating'){state.mode=mode;state.query='';state.program='';state.interest='';state.year=0;state.intention='';state.page=1;}

function setUser(result){if(state.user?.id!==result.user.id){state.authEpoch=(state.authEpoch||0)+1;state.mode='dating';state.query='';state.program='';state.interest='';state.year=0;state.intention='';state.page=1;state.selected=null;state.messages=[];state.chats=[];state.connections=[];state.notifications=[];state.students=[];state.drafts.clear();state.outbox.clear();state.starterOpen.clear();state.promptDraft=null;resetSocial();state.connectionLoaded=false;state.chatLoaded=false;state.connectionError='';state.chatError='';}state.user=result.user;state.csrf=result.csrf||result.user.csrf||state.csrf;}
function signout(){source?.close();source=null;state.authEpoch=(state.authEpoch||0)+1;state.user=null;state.promptDraft=null;resetSocial();state.csrf='';state.live=false;state.selected=null;state.messages=[];state.drafts.clear();state.outbox.clear();state.starterOpen.clear();state.chats=[];state.connections=[];state.notifications=[];go('/login');}
function dialog(title,body){$('#dialog').innerHTML=`<div class="dialog-heading"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-button" data-action="close-dialog" aria-label="Close dialog">${icon('close')}</button></div><div class="dialog-body">${body}</div>`;if(!$('#dialog').open)$('#dialog').showModal();const datingForm=$('#dating-form');if(datingForm)syncIntentionControl(datingForm);}
function interestOptions(selected=[]){return `<div class="interest-options">${state.catalog.interests.map(i=>`<label class="interest-option"><input type="checkbox" name="interests" value="${esc(i)}" ${selected.includes(i)?'checked':''}><span>${esc(i)}</span></label>`).join('')}</div>`;}
function check(name,label,value){return `<label class="check"><input type="checkbox" name="${name}" ${value?'checked':''}><span>${label}</span></label>`;}
function formError(){return '<div class="form-error error hidden" role="alert"></div>';}

function resetSocial(){if(state.postDraft?.preview)URL.revokeObjectURL(state.postDraft.preview);state.postDraft={};state.requests=[];state.requestError='';state.requestLoaded=false;state.delivered.clear();state.read.clear();}
function profileSocialActions(p,context='campus',detail=false){
 const own=p.id===state.user?.id,kind=context==='dating'?'dating':'friend';
 return `<div class="${detail?'profile-public-likes':'profile-social-actions'}"><button type="button" class="public-like-count" data-action="public-profile-likes" data-id="${esc(p.id)}">${p.like_count||0} ${(p.like_count||0)===1?'like':'likes'}</button>${!own?`${detail?`<button type="button" class="btn secondary" data-action="like" data-kind="${context==='dating'?'dating':'campus'}" data-id="${esc(p.id)}" aria-pressed="${!!p.liked&&(context!=='dating'||!!p.dating_liked)}">${icon('heart')}${p.liked?'Liked':'Like'}</button>`:''}<button type="button" data-action="private-comment" data-kind="${kind}" data-id="${esc(p.id)}" title="Send a private comment">${icon('comment')}Comment</button><button type="button" data-action="profile-inbox" data-kind="${kind}" data-id="${esc(p.id)}">${icon('mail')}Inbox</button>`:''}<a class="text-button" href="/feed?student=${esc(p.id)}" data-nav>Posts</a></div>`;
}
async function showLikes(url){const r=await api(url);dialog('Likes',r.items.length?r.items.map(p=>`<button type="button" class="like-person" data-action="view-profile" data-profile-context="campus" data-id="${esc(p.id)}">${avatar(p)}<span><strong>${esc(p.display_name)}</strong><br><small class="muted">${esc(p.program)}</small></span></button>`).join(''):'<p>No likes yet.</p>');}
async function privateComment(uid,kind='friend',postId=null,title='Private comment'){
 const result=await api(`/profiles/${uid}?context=${kind==='dating'?'dating':'campus'}`),p=result.profile;
 dialog(title,`<form id="private-comment-form" class="stack" data-target="${esc(uid)}" data-kind="${esc(kind)}" data-post-id="${postId||''}" data-client-id="${newMessageId()}">${formError()}<div class="row">${avatar(p)}<strong>${esc(p.display_name)}</strong></div><p class="private-comment-note">Only ${esc(p.display_name)} can see your comment. If you haven’t connected yet, they can accept or decline it in their inbox.</p><label>Your message<textarea name="body" required maxlength="1000" rows="4" placeholder="Write a private comment…"></textarea></label><button class="btn" type="submit">Send comment</button></form>`);
}
async function profileInbox(uid,kind='friend'){
 await refreshData();const chat=state.chats.find(c=>c.profile.id===uid);
 if(chat){state.selected=chat.id;go('/chats');return;}
 await privateComment(uid,kind,null,'Message request');
}
function renderRequests(){
 const root=$('#message-requests');if(!root)return;
 const key=JSON.stringify([state.requests,state.requestError,state.requestLoaded]);if(root.dataset.key===key)return;root.dataset.key=key;
 const open=!!$('details[open]',root),received=state.requests.filter(r=>r.direction==='received');
 root.innerHTML=(state.requestError?'<div class="notice" role="alert"><p>Message requests could not refresh.</p><button class="text-button" data-action="retry-data">Retry</button></div>':'')+(state.requests.length?`<details class="message-requests" ${open?'open':''}><summary><span>Message requests</span><span class="badge">${received.length}</span></summary>${state.requests.map(r=>`<article class="request-card"><div class="row">${avatar(r.profile)}<strong>${esc(r.profile.display_name)}</strong></div><p>${esc(r.body)}</p><small class="muted">${r.direction==='sent'?'Sent · Waiting for acceptance':'Private comment'}${r.post_id?' · In response to a post':''}</small>${r.direction==='received'?`<div class="row"><button class="btn small" data-action="request-decision" data-command="accept" data-id="${esc(r.id)}">Accept & chat</button><button class="btn secondary small" data-action="request-decision" data-command="decline" data-id="${esc(r.id)}">Decline</button><button class="text-button" data-action="profile-safety-dialog" data-id="${esc(r.profile.id)}">Safety & support</button></div>`:''}</article>`).join('')}</details>`:'');
}
async function showProfile(id,context='campus'){const r=await api(`/profiles/${id}?context=${encodeURIComponent(context)}`),p=r.profile;dialog(p.display_name,`<div class="row">${avatar(p,true)}<div><strong>@${esc(p.username)}</strong><p>${esc(p.program)} · Year ${p.year}</p><span class="test-label">${testProfileLabel(p)}</span></div></div>${datingIntentionMarkup(p,esc)}${photoGalleryMarkup(p,esc)}<p>${esc(p.bio)}</p>${promptAnswersMarkup(p,esc)}<div class="tags">${p.interests.map(i=>`<span class="tag">${esc(i)}</span>`).join('')}</div>${p.subjects?`<p><strong>Subjects:</strong> ${esc(p.subjects)}</p>`:''}${p.skills?`<p><strong>Skills:</strong> ${esc(p.skills)}</p>`:''}${p.study_goals?`<p><strong>Study goals:</strong> ${esc(p.study_goals)}</p>`:''}${profileSocialActions(p,context==='dating'?'dating':'campus',true)}${safetyDisclosure(p)}`);}
function feedPage(){
 $('#main').innerHTML=`${pageHeading('Feed','')}<div id="feed-root"></div>`;
 feedManager=new Feed($('#feed-root'),{api,esc,icon,avatar,user:state.user,draft:state.postDraft,onComment:privateComment,onInbox:profileInbox,onLikes:showLikes,onProfile:id=>showProfile(id,'campus'),dialog,toast});
}

function landing(){
  app.innerHTML=`<main id="main" class="landing"><nav class="landing-nav" aria-label="Welcome">${brand()}<div class="landing-actions">${themeToggle()}<a href="${state.user?'/discover':'/login'}" data-nav class="btn secondary">${state.user?'Open CampusLink':'Sign in'} ${icon('arrow')}</a></div></nav>
    <section class="landing-hero"><div><div class="eyebrow">CampusLink</div><h1>Meet students.<br>Make connections.</h1><p>Meet people across programs, share photos and start a conversation.</p><div class="row wrap"><a class="btn" href="${state.user?'/discover':'/signup'}" data-nav>Get started ${icon('arrow')}</a><a class="btn secondary" href="#how-it-works">How it works</a></div></div>
    <div class="hero-visual" aria-label="Discover, match, then chat"><div class="eyebrow">Discover, connect, chat</div><div class="connection-illustration">${icon('compass')}<div><strong>Discover students</strong><small>People from across your campus.</small></div></div><div class="connection-illustration">${icon('people')}<div><strong>Connect</strong><small>Like a profile or send a private comment.</small></div></div><div class="connection-illustration">${icon('chat')}<div><strong>Start talking</strong><small>Accept a request or open a match.</small></div></div></div></section>
    <section id="how-it-works"><div class="eyebrow">Meet people across programs</div><h2>Dating, friends and study partners.</h2><div class="landing-grid"><article class="panel">${icon('heart')}<h3>Dating</h3><p>Turn on Dating to meet other adults. Likes are public; comments stay private.</p></article><article class="panel">${icon('people')}<h3>Friends</h3><p>Meet people through shared interests. Send a request and start chatting when it’s accepted.</p></article><article class="panel">${icon('book')}<h3>Study partners</h3><p>Friendship and study connections are here too. Find a partner through your program, subjects, and learning goals.</p></article></div></section>
    <section class="landing-safety">${icon('shield')}<div><h3>You choose who can contact you.</h3><p>You control discoverability. Connections are mutual, and blocking and reporting are always within reach.</p></div></section><div class="notice">${isStaging()?'Preview build':'Local development build'} · Fictional test accounts are unverified. CampusLink is an independent student-built project, not an official ZUT service. Student verification must be established before public launch.</div><footer class="landing-footer"><span>CampusLink</span><span><a href="/privacy" data-nav>Draft privacy notice</a> &nbsp;·&nbsp; <a href="/terms" data-nav>Draft terms</a> · <a href="/support" data-nav>Support</a></span></footer></main>`;
}

function authPage(signup=false){
 const external=state.catalog.eligibility_mode==='external';
  app.innerHTML=`<main id="main" class="auth-page"><aside class="auth-story">${publicHeader()}<div class="hero-copy"><div class="eyebrow">Meet people across programs</div><h1>Meet people on campus.</h1><p>Discover students, share updates and keep your conversations in one place.</p><div class="orbit-art" aria-hidden="true"><span></span><span></span>${icon('spark')}</div></div><small class="muted">An independent student-built project in Zambia.</small></aside>
    <section class="auth-form"><div><div class="eyebrow">Welcome to CampusLink</div><h1>${signup?'Create your account':'Sign in'}</h1><p>${signup?(external?'Create an account, then complete membership approval and eligibility checks.':(isStaging()?'Create a fictional account for this preview.':'Create a local test account to explore CampusLink.')):'Sign in and pick up the conversation.'}</p><form id="auth-form" data-signup="${signup}">${formError()}${signup?'<div class="field-grid"><label>Display name<input name="display_name" autocomplete="nickname" required maxlength="60"></label><label>Username<input name="username" autocomplete="username" required minlength="3" maxlength="24" pattern="[a-zA-Z0-9_]{3,24}"></label></div>':''}<label>Email address<input name="email" type="email" autocomplete="email" required maxlength="254" placeholder="you@example.com"></label><label>Password<input name="password" type="password" autocomplete="${signup?'new-password':'current-password'}" required minlength="${signup?12:1}" maxlength="128" placeholder="${signup?'At least 12 characters':'Your password'}"></label>${signup?`<label class="check"><input type="checkbox" name="agreement" required><span>I agree to the <a href="/terms" data-nav>draft terms</a> and <a href="/privacy" data-nav>privacy notice</a>. ${external?'Membership approval and eligibility checks are required.':'I understand this is a test build.'}</span></label>`:(state.catalog.recovery_available?'<a href="/forgot-password" data-nav>Forgot your password?</a>':'<p class="notice">Password recovery is unavailable until a secure email provider is configured. You can change your password while signed in.</p>')}<button class="btn" type="submit">${signup?(external?'Create account':'Create test account'):'Sign in'} ${icon('arrow')}</button></form><p class="switch-auth">${signup?'Already have an account?':'New to CampusLink?'} <a href="${signup?'/login':'/signup'}" data-nav>${signup?'Sign in':'Create an account'}</a></p>${external?'<div class="notice"><strong>Pilot preview.</strong> Membership is reviewed by the operator. Student and adult eligibility require separate checks.</div>':isStaging()?'<div class="notice"><strong>Preview build.</strong> Create your own fictional test account. Student identity and age are unverified.</div>':'<div class="notice"><strong>Local testing only.</strong> Fictional accounts, real persisted connections and messages. <button class="text-button" data-action="test-accounts">View test accounts</button></div>'}</div></section></main>`;
}

function legal(kind){
 const privacy=kind==='privacy';
 app.innerHTML=`<main id="main" class="legal">${publicHeader()}<h1>Draft ${privacy?'privacy notice':'terms of use'}</h1><p class="notice">Draft for product development and legal review. This build is for restricted testing. These documents have not been reviewed for public launch or compliance with Zambian law.</p>${privacy?`
 <h2>What this build stores</h2><p>CampusLink stores your email, a salted password hash, display name, username, academic information, chosen interests, preferences, optional personality prompt answers, public profile likes, campus posts and photos, post likes, private comment requests, delivery/read cursors, connections, messages, reports, and session records in a private SQLite database, along with membership decisions, operator audit records, private app feedback and email/verification metadata. Birth dates are private and do not establish verified adult eligibility. Optional profile photos are processed into resized JPEGs with embedded metadata removed and stored privately in the same database. Authenticated photo access follows profile visibility and blocking rules.</p>
 <h2>Who can see your information</h2><p>Eligible students can see discoverable public profiles. Public responses exclude email, birth dates, dating preferences, and session data. Optional dating intentions appear only in authorized Dating views when the owner chooses to display them; friendship and study views omit them. Hidden intentions are not used by the Dating intention filter. Turning off discovery removes you from new recommendations, search, and new requests; existing accepted connections can still view your profile. Dating profiles appear only to mutually eligible, opted-in adults. New profile likes and the people who liked a profile are visible to eligible campus viewers. Earlier private Dating likes remain private. Posts and their likes follow campus visibility and block rules. Comments are private inbox requests, visible only to sender and recipient. Accepted comments become messages in the resulting conversation. No music is included.</p>
 <h2>Messages and consent</h2><p>Only participants in an active accepted connection or eligible mutual dating match can read or send chat messages. Before connecting, a student can send one private comment request; only its recipient can accept or decline it. Delivery and read receipts share acknowledgement state with the other conversation participant. A read receipt is sent when the conversation is visible and scrolled to the latest messages. Messages are stored on the server and are not end-to-end encrypted. Removing a connection, blocking, unmatching, or disabling dating stops access to that conversation for both participants. Disabling dating ends existing matches; enabling it again does not restore them. A newly accepted friendship or study request between the same pair can restore their retained conversation history after fresh consent.</p>
 <h2>Retention and deletion</h2><p>Removed conversations remain in the database until account deletion. Expired sessions and email tokens are pruned hourly; live refresh events expire after 24 hours, read notifications after 30 days, and completed mail-job metadata after 7 days. When automatic backups are enabled, one consistent copy is taken every 24 hours and the latest three scheduled copies are retained by default. The operator may keep protected copies outside the server and must record their deletion dates. Deleting either participant permanently deletes their relationships and associated conversation history for both participants. Reports retain their reason, detail, and audit trail, with deleted account and message references removed. Do not enter sensitive identifying information in reports. Deletion removes live account data immediately; earlier backups retain it until those copies expire or are deleted. An old backup must be reconciled with subsequent deletion requests before its restored data is used. A reviewed policy for reports, audit records and external backup copies is still required before public launch.</p>
 <h2>Control and safety</h2><p>You can change discoverability and notifications, block students, report profiles or messages, review your submitted reports, revoke other sessions, deactivate, or delete your account. Authorized moderators can review reports and selected reported messages. The operator can review membership applications, private app feedback and service health, and can export the database after password confirmation. Operator actions are audited. Deactivated accounts require operator assistance to reactivate. When configured, email is used for confirmation and password recovery. There are no promotional emails, push notifications or location tracking.</p>
 <h2>Before a public launch</h2><p>The operator must establish student and adult verification, review applicable Zambian data protection obligations, provide an operator contact and support process, configure secure recovery, establish retention periods, and review this notice with qualified counsel.</p>`:`
 <h2>An independent student project</h2><p>CampusLink is an independent student-built discovery and connection platform, starting with ZUT. It is not an official institutional service and claims no institutional endorsement. All supplied accounts are fictional, unverified development fixtures.</p>
 <h2>Respect the people you meet</h2><p>No harassment, impersonation, spam, discrimination, exploitation, or sharing another person’s private information. Use blocking and reporting when needed. Requests require acceptance; dating requires explicit opt-in and established adult eligibility.</p>
 <h2>Your account and choices</h2><p>Keep your password private. You control your profile and discoverability. Use a display name you are comfortable sharing. Do not submit student numbers, identity documents, university credentials, or sensitive personal information to this local test build.</p>
 <h2>Moderation and availability</h2><p>Authorized moderators can review reports, resolve or dismiss them, and suspend accounts. Actions are audited. This local development build has no production availability guarantee or staffed support service.</p>
 <h2>Age and verification</h2><p>This local build supports adult fixtures and explicit self-declared 18+ test access on created accounts. A private birth date, local test acknowledgement, and separate Dating opt-in are required for created accounts. This does not verify age, student status, or identity. Owner membership approval does not verify email ownership or age. Email confirmation and optional external student and 18+ checks are separate. External checks stay unavailable until the operator configures a supported live provider; results must match this account and the approved institution. Identity documents are submitted directly to the provider, never uploaded to CampusLink. CampusLink retains provider references, check status, an identity fingerprint and expiry dates; a checked birth date remains private.</p>`}<p>${state.catalog.service?.operator_name?'Operator: '+esc(state.catalog.service.operator_name)+'. ':''}${state.catalog.service?.support_email?'Contact: <a href="mailto:'+encodeURIComponent(state.catalog.service.support_email)+'">'+esc(state.catalog.service.support_email)+'</a>. ':''}<a href="/support" data-nav>Help and support</a></p><p><a href="${state.user?'/profile':'/'}" data-nav>← Back to CampusLink</a></p></main>`;
}

function recoveryPage(reset=false){
 if(reset&&location.hash){state.resetToken=location.hash.slice(1);history.replaceState({},'','/reset-password');}
 app.innerHTML=`<main id="main" class="onboarding">${publicHeader()}<h1>${reset?'Choose a new password.':'Let’s get you back in.'}</h1><p>${reset?'This link can be used once and expires after 30 minutes.':'If your email belongs to an active account, you’ll receive a private reset link.'}</p><form id="${reset?'reset-form':'recover-form'}" class="panel stack">${formError()}${reset?'<label>New password<input type="password" name="new_password" autocomplete="new-password" required minlength="12" maxlength="128"></label>':'<label>Email address<input name="email" type="email" autocomplete="email" required maxlength="254"></label>'}${!reset&&!state.catalog.recovery_available?'<p class="notice">Recovery is unavailable until the operator configures a secure email provider.</p>':`<button class="btn" type="submit">${reset?'Reset password':'Request reset link'}</button>`}<a href="/login" data-nav>Back to sign in</a></form></main>`;
}

async function downloadOperatorBackup(password){
 const response=await fetch('/api/operator/backup-download',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({password})});
 if(!response.ok){const result=await response.json();throw new Error(result.detail||'Backup download failed.');}
 const file=await response.blob(),url=URL.createObjectURL(file),link=document.createElement('a');
 link.href=url;link.download='campuslink-backup.sqlite3';link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 return response.headers.get('X-Backup-SHA256');
}

function approvalPage(){
 const membership=state.user.verification?.membership||{},rejected=membership.status==='rejected';
 app.innerHTML=`<main class="onboarding" id="main">${publicHeader()}<section class="panel stack"><h1>${rejected?'Membership not approved':'Waiting for campus approval'}</h1><p>${rejected?'The operator has not approved this account for campus access. You can contact support if you believe this is a mistake.':'Your account is ready for the operator to review. Once approved, you can discover members and connect.'}</p><p>${esc(state.user.email)}</p><button class="btn" data-action="check-membership">Check approval status</button><a href="/profile" data-nav>Edit my profile</a><a href="/verification" data-nav>Email and eligibility</a><a href="/support" data-nav>Contact support</a>${state.user.operator?'<a class="btn secondary" href="/operator" data-nav>Operator console</a>':''}<button class="text-button" data-action="logout">Sign out</button></section></main>`;
}
async function verificationPage(){
 app.innerHTML=`<main class="onboarding" id="main">${publicHeader()}<p role="status">Loading your verification status…</p></main>`;
 try{
  const v=await api('/verification');if(path()!=='/verification')return;
  const provider=state.catalog.verification_provider||{},enabled=!!provider.configured;
  const status=key=>({approved:'Approved',pending:'In progress',rejected:'Not approved',expired:'Expired',failed:'Could not finish',not_started:'Not started'}[v[key]?.status]||'Not started');
  const check=(kind,title)=>`<section class="panel stack"><h2>${title}</h2><p>${esc(status(kind))}</p><form id="provider-${kind}-form" data-provider-kind="${kind}" class="stack">${formError()}<label class="check"><input name="consent" type="checkbox" required><span>I agree to continue with ${esc(provider.name||'the verification partner')} for this check. Information is submitted directly to that provider. <a href="https://www.sheerid.com/privacy-policy/" target="_blank" rel="noopener">Provider privacy notice</a></span></label><button class="btn" type="submit" ${enabled&&v.email_confirmed&&(!v.approval_required||v.membership?.status==='approved')&&(kind==='student'||v.student_verified)?'':'disabled'}>Continue ${title.toLowerCase()}</button><button class="btn secondary" type="button" data-action="provider-refresh" data-kind="${kind}" ${enabled?'':'disabled'}>Check verification status</button></form></section>`;
  app.innerHTML=`<main class="onboarding" id="main">${publicHeader()}<h1>Email and eligibility</h1><section class="panel stack"><h2>Your email</h2><p>${esc(state.user.email)} · ${v.email_confirmed?'Confirmed':'Not confirmed'}</p>${!v.email_confirmed?`<button class="btn" data-action="confirm-email-request" ${state.catalog.email_verification_available?'':'disabled'}>Send confirmation link</button>${!state.catalog.email_verification_available?'<p>Email confirmation is not available yet. Contact the operator for help.</p>':''}`:''}<h2>Campus membership</h2><p>${esc(v.membership?.status||'pending')} · Approval is managed by the CampusLink operator.</p><p>Membership approval and a confirmed email do not verify age. The separate checks below must finish before this account can claim checked student or adult status.</p>${!enabled?'<p>External verification is not available yet. The operator needs to finish the provider setup.</p>':''}${v.mode==='preview'?'<p>This preview uses clearly labelled test eligibility. External checks are not required for test profiles.</p>':''}</section>${check('student','Student status')}${check('adult','18+ eligibility')}<p><a href="/profile" data-nav>Back to my profile</a> · <a href="/support" data-nav>Support</a></p></main>`;
 }catch(error){if(!error.stale)showError(error);}
}
function confirmEmailPage(){
 if(location.hash){state.emailToken=location.hash.slice(1);history.replaceState({},'','/verify-email');}
 app.innerHTML=`<main class="onboarding" id="main">${publicHeader()}<h1>Confirm your email</h1><form id="verify-email-form" class="panel stack">${formError()}<p>Confirm the email address for the account that requested this link.</p><button class="btn" type="submit" ${state.emailToken?'':'disabled'}>Confirm email</button>${!state.emailToken?'<p>This page needs a confirmation link from your inbox.</p>':''}<a href="/login" data-nav>Sign in</a></form></main>`;
}

function supportPage(){
 const service=state.catalog.service||{},email=service.support_email;
 app.innerHTML=`<main class="legal" id="main">${publicHeader()}<h1>Help and support</h1>${service.operator_name?`<p>CampusLink is operated by ${esc(service.operator_name)}.</p>`:''}<h2>Contact</h2>${email?`<p><a href="mailto:${encodeURIComponent(email)}">${esc(email)}</a></p>`:'<p>A support email has not been configured yet.</p>'}<h2>Report a problem</h2><p>For a person or message, open Safety & support in the conversation and choose Report. For an app problem or suggestion, use Send feedback in Profile.</p>${state.user?'<button class="btn" data-action="pilot-feedback">Send feedback</button>':'<p><a href="/login" data-nav>Sign in to send feedback</a></p>'}<p><a href="/privacy" data-nav>Privacy notice</a> · <a href="/terms" data-nav>Terms</a> · <a href="/" data-nav>CampusLink</a></p></main>`;
}
async function feedbackDialog(){
 const previous=await api('/feedback/mine');
 dialog('Feedback',`<form id="feedback-form" class="stack">${formError()}<p>Tell the CampusLink operator what happened. Include the steps you took, but leave out passwords, identity documents and private conversations.</p><label>Category<select name="category"><option value="bug">Something is broken</option><option value="usability">Something is hard to use</option><option value="suggestion">Suggestion</option></select></label><label>Your feedback<textarea name="body" required minlength="10" maxlength="2000" rows="5"></textarea></label><button class="btn" type="submit">Send feedback</button></form>${previous.items.length?`<details><summary>Your recent feedback</summary>${previous.items.slice(0,5).map(item=>`<p><strong>${esc(item.status)}</strong> · ${esc(item.body)}</p>`).join('')}</details>`:''}`);
}

function onboarding(){
 const u=state.user,step=Math.min(u.onboarding_step,5);
 const titles=['Your profile','Your studies','Your interests','Connection preferences','Privacy settings','Review your profile'];
 const descriptions=['Your display name can be a name you feel comfortable sharing.','Find people learning the same things, or something completely different.','Pick a few interests. You can change them anytime.','Friends and study partners are independent choices.','You decide whether new people can find your profile.','A few shared interests can be the start of a good connection.'];
 const fields=[
 `<label>Display name<input name="display_name" value="${esc(u.display_name)}" required maxlength="60"></label><label>Username<input name="username" value="${esc(u.username)}" required minlength="3" maxlength="24"></label><label>A little about you <span class="muted">(optional)</span><textarea name="bio" maxlength="500" placeholder="What would you like people to know?">${esc(u.bio)}</textarea></label><section id="photo-manager"></section>`,
 `<label>Institution<input value="Zambia University College of Technology" readonly><small class="muted">CampusLink currently starts with ZUT.</small></label><div class="field-grid"><label>Academic program<input name="program" value="${esc(u.program)}" required maxlength="100" placeholder="e.g. Computer Science"></label><label>Year of study<select name="year">${Array.from({length:7},(_,i)=>`<option ${u.year===i+1?'selected':''}>${i+1}</option>`).join('')}</select></label></div><label>Subjects <span class="muted">(optional, comma separated)</span><input name="subjects" value="${esc(u.subjects)}" maxlength="300" placeholder="Algorithms, Economics…"></label><label>Skills <span class="muted">(optional)</span><input name="skills" value="${esc(u.skills)}" maxlength="300" placeholder="Python, Research…"></label><label>Study goals <span class="muted">(optional)</span><input name="study_goals" value="${esc(u.study_goals)}" maxlength="300" placeholder="Exam preparation, Project collaboration…"></label>`,
 interestOptions(u.interests),
 `${check('friend_goal','Make friends through shared interests',u.friend_goal)}${check('study_goal','Find one-to-one study partners',u.study_goal)}<div class="notice">${icon('heart')} Dating is optional and separate. It requires established adult eligibility and explicit activation in Profile. It is never enabled automatically.</div>`,
 `${check('discoverable','Let eligible students discover my profile and send connection requests',u.discoverable)}${check('notifications_enabled','Show in-app notifications for my connections and messages',u.notifications_enabled)}<div class="notice">You can always block or report a student. Existing accepted connections can still view your profile when discovery is off.</div>`,
 `<div class="row">${avatar(u,true)}<div><h2>${esc(u.display_name)}</h2><p>@${esc(u.username)} · ${esc(u.program)}</p></div></div><div class="tags">${u.interests.map(i=>`<span class="tag">${esc(i)}</span>`).join('')||'<p>No interests selected. Add them later in Profile.</p>'}</div><div class="notice">${testProfileLabel(u)}. ${state.catalog.eligibility_mode==='external'?'Complete the required checks in Email and eligibility after membership approval.':'Student status and age are unverified in this preview.'}</div>`
 ];
 app.innerHTML=`<main id="main" class="onboarding">${publicHeader()}<div class="row between"><span class="eyebrow">Set up your profile</span><small class="muted">Step ${step+1} of 6</small></div><div class="progress" aria-label="Step ${step+1} of 6">${Array.from({length:6},(_,i)=>`<span class="${i<=step?'complete':''}"></span>`).join('')}</div><h1>${titles[step]}</h1><p>${descriptions[step]}</p><form id="onboarding-form" data-step="${step}" class="panel stack">${formError()}${fields[step]}<div class="onboarding-actions">${step?'<button type="submit" name="back" value="1" class="btn secondary" formnovalidate>Back</button>':'<span></span>'}<button class="btn" type="submit">${step===5?'Open Discover':'Continue'} ${icon('arrow')}</button></div></form></main>`;
 if(step===0)mountPhotoManager();
}

function shell(destination){
 const unread=state.chats.reduce((n,c)=>n+c.unread,0),notificationCount=state.notifications.filter(n=>!n.read).length;
 const nav=[['feed','feed','Feed',0],['discover','compass','Discover',0],['matches','heart','Matches',0],['chats','chat','Inbox',unread],['profile','user','Profile',0]];
 app.innerHTML=`<div class="shell"><aside class="sidebar">${brand()}<nav class="nav" aria-label="Main navigation">${nav.map(([url,i,label,count])=>`<a href="/${url}" data-nav ${destination===url?'aria-current="page"':''} class="${destination===url?'active':''}">${icon(i)}<span>${label}</span>${count?`<span class="badge" data-badge="${url}">${count}</span>`:`<span class="badge hidden" data-badge="${url}"></span>`}</a>`).join('')}</nav><div class="sidebar-bottom"><a href="/profile" data-nav class="sidebar-user">${avatar(state.user)}<span class="grow"><strong>${esc(state.user.display_name)}</strong><small>@${esc(state.user.username)}</small></span>${icon('settings')}</a></div></aside>
 <div class="workspace"><header class="topbar"><div class="context"><strong>CampusLink</strong>${stagingBadge()}</div><div class="topbar-actions"><span class="connection-status offline hidden" id="live-status" role="status">Reconnecting…</span><a class="icon-button inbox-widget" href="/chats" data-nav aria-label="Inbox">${icon('mail')}<span class="badge ${unread?'':'hidden'}" data-badge="chats">${unread||''}</span></a>${themeToggle()}<button class="icon-button" data-action="notifications" aria-label="Notifications${notificationCount?`, ${notificationCount} unread`:''}">${icon('bell')}<span id="notification-badge" class="badge ${notificationCount?'':'hidden'}">${notificationCount||''}</span></button><a href="/profile" data-nav aria-label="Your profile">${avatar(state.user)}</a></div></header><main class="page" id="main" tabindex="-1"></main></div></div>`;
}

function pageHeading(title,copy,extra=''){return `<div class="page-heading"><div><h1>${title}</h1><p>${copy}</p></div>${extra}</div>`;}
function discoveryPage(){
 state.searchSerial++;
 const dating=state.mode==='dating', ready=state.user.dating_enabled&&state.user.adult_eligible;
 const tabs=[['dating','heart','Dating'],['for-you','spark','For you'],['friend','people','Friends'],['study','book','Study partners']];
 $('#main').innerHTML=`${pageHeading(dating?'Dating':'Discover',dating?'Meet students across programs.':'Find students who share your interests.')}
  <div class="tabs" role="tablist" aria-label="Discovery categories">${tabs.map(([mode,i,label])=>`<button id="discovery-tab-${mode}" aria-controls="discovery-panel" role="tab" tabindex="${state.mode===mode?'0':'-1'}" aria-selected="${state.mode===mode}" class="${state.mode===mode?'active':''}" data-action="discover-mode" data-mode="${mode}">${icon(i)}${label}</button>`).join('')}</div>
  <section id="discovery-panel" role="tabpanel" aria-labelledby="discovery-tab-${state.mode}" tabindex="0">${dating&&!ready?datingWelcome(state.user,{icon,demoAccounts:!isStaging()}):`<div class="discovery-layout"><div>
   ${dating?`<div class="dating-toolbar"><span class="muted">Likes are public · Comments are private</span><div class="row wrap"><button class="btn secondary small" data-action="view-dating-matches">${icon('heart')}My matches</button><button class="btn secondary small" data-action="dating-settings">${icon('settings')}Preferences</button></div></div>`:`<div class="dating-entry"><span>${icon('heart')}Dating</span><button class="text-button" data-action="discover-mode" data-mode="dating">Explore Dating ${icon('arrow')}</button><a href="/connections" data-nav class="text-button" data-request-link>Requests & connections <span class="badge hidden" data-badge="requests" aria-hidden="true"></span></a></div>`}
   <div class="searchbar"><label class="search-input"><span class="sr-only">Search students</span>${icon('search')}<input type="search" id="student-search" value="${esc(state.query)}" placeholder="Search by name, username, program, or interest" maxlength="100" autocomplete="off"></label><button class="btn secondary" data-action="toggle-filters" aria-expanded="${state.filtersOpen}" aria-controls="search-filters">${icon('filter')}<span>Filters</span></button></div>
   <div id="search-filters" class="filters ${state.filtersOpen?'':'hidden'}"><label>Program<input id="filter-program" value="${esc(state.program)}" placeholder="Any program" maxlength="100"></label><label>Interest<select id="filter-interest"><option value="">All interests</option>${state.catalog.interests.map(i=>`<option ${state.interest===i?'selected':''}>${esc(i)}</option>`).join('')}</select></label><label>Year<select id="filter-year"><option value="0">Any year</option>${Array.from({length:7},(_,i)=>`<option value="${i+1}" ${state.year===i+1?'selected':''}>Year ${i+1}</option>`).join('')}</select></label>${dating?`<label>Dating intention<select id="filter-intention"><option value="">Any intention (including unset)</option>${intentionOptions(state.intention,esc)}</select><small class="muted">Choose one to show only students who display that intention.</small></label>`:''}<button class="text-button" data-action="clear-filters">Clear search & filters</button></div>

   <div id="discovery-results" aria-live="polite">${loadingCards()}</div>
  </div></div>`}</section>`;
 updateBadges();if(!dating||ready)loadStudents();
}

function profilePhotoButton(p,context='general',large=false){return `<button type="button" class="profile-photo-button" data-action="view-profile" data-id="${esc(p.id)}" data-profile-context="${esc(context)}" aria-label="View ${esc(p.display_name)}’s profile">${avatar(p,large)}</button>`;}
function studentCard(p){
 if(p.available_kinds.includes('dating'))return datingProfileCard(p,{icon,esc,avatar});
 const kinds=p.available_kinds,context=state.mode==='study'?'study':'general';
 return `<article class="student-card compact-card" data-profile-id="${esc(p.id)}"><div class="dating-photo"><button type="button" class="dating-photo-open" data-action="view-profile" data-id="${esc(p.id)}" data-profile-context="${context}" aria-label="View ${esc(p.display_name)}’s profile"><span class="photo-cover-initials" aria-hidden="true">${esc(initials(p))}</span>${p.main_photo_url?`<img data-profile-photo src="${esc(p.main_photo_url)}" alt="${esc(p.display_name)}’s profile photo" loading="lazy" decoding="async">`:''}<span class="photo-profile-hint">View profile ${icon('arrow')}</span></button><button class="icon-button dating-photo-options" data-action="student-menu" data-id="${esc(p.id)}" aria-label="Options for ${esc(p.display_name)}">${icon('more')}</button></div><div><button class="name-button" data-action="view-profile" data-id="${esc(p.id)}" data-profile-context="${context}"><h3>${esc(p.display_name)}</h3></button><p class="academic">${esc(p.program)}</p></div><div class="card-actions">${kinds.map(k=>`<button class="btn ${k==='study'&&kinds.length>1?'secondary':''}" data-action="connect" data-id="${esc(p.id)}" data-kind="${k}">${icon(k==='study'?'book':'plus')}${k==='study'?'Study together':'Connect'}</button>`).join('')}<button class="icon-button" data-action="dismiss" data-id="${esc(p.id)}" data-kind="${kinds.join(',')}" aria-label="Dismiss ${esc(p.display_name)}">${icon('close')}</button></div>${profileSocialActions(p,'campus',false)}</article>`;
}
async function loadStudents(append=false){
 const serial=++state.searchSerial; const region=$('#discovery-results');if(!region||(state.mode==='dating'&&(!state.user?.dating_enabled||!state.user?.adult_eligible)))return;
 try{const params=new URLSearchParams({mode:state.mode,q:state.query,program:state.program,interest:state.interest,year:state.year,page:append?state.page+1:1});if(state.mode==='dating'&&state.intention)params.set('intention',state.intention);const r=await api('/discover?'+params);if(serial!==state.searchSerial||path()!=='/discover')return;state.students=append?[...state.students,...r.items]:r.items;state.page=r.page;state.hasMore=r.has_more;
 region.innerHTML=state.students.length?`<div class="profile-grid">${state.students.map(studentCard).join('')}</div>${r.has_more?'<div class="load-more"><button class="btn secondary" data-action="more-students">Discover more</button></div>':''}`:state.mode==='dating'?empty('heart','No more profiles for now.','Only opted-in adults with reciprocal preferences appear here. Try broader filters or preferences. You can also check your matches or inbox.','<div class="row wrap"><button class="btn secondary" data-action="clear-filters">Clear filters</button><button class="btn secondary" data-action="dating-settings">Dating preferences</button><button class="btn secondary" data-action="view-dating-matches">My matches</button></div>'):empty('compass','A little quiet here.','Try another interest or program, clear your filters, or return when more people have joined. Accepted connections and pending requests are in Connections.','<button class="btn secondary" data-action="clear-filters">Clear search & filters</button>');
 revealNew(region,'.student-card',{key:'data-profile-id'});
 }catch(e){if(e.stale||serial!==state.searchSerial)return;region.innerHTML=empty('compass','Discovery is unavailable.',e.message,'<button class="btn secondary" data-action="retry-discovery">Try again</button>');}
}

function connectionAreas(){
 const received=state.connections.filter(c=>c.status==='pending'&&c.direction==='received').length;
 return `<nav class="connection-areas" aria-label="Connection areas"><a href="/matches" data-nav ${path()==='/matches'?'aria-current="page"':''}>${icon('heart')}Dating matches</a><a href="/connections" data-nav data-request-link ${path()==='/connections'?'aria-current="page"':''}>${icon('people')}Friends & study <span class="badge ${received?'':'hidden'}" data-badge="requests" aria-hidden="true">${received||''}</span></a></nav>`;
}
function connectionsPage(){
 const dating=path()==='/matches';
 $('#main').innerHTML=`${pageHeading(dating?'Matches':'Friends & study','')}${connectionAreas()}
 ${dating?'':`<div class="tabs" role="tablist" aria-label="Friendship and study views">${[['received','Received'],['sent','Sent'],['friend','Friends'],['study','Study']].map(([f,t])=>`<button id="connection-tab-${f}" role="tab" tabindex="${state.connectionFilter===f?'0':'-1'}" aria-selected="${state.connectionFilter===f}" aria-controls="connection-results" class="${state.connectionFilter===f?'active':''}" data-action="connection-filter" data-filter="${f}">${t}</button>`).join('')}</div>`}
 <div id="connection-results" aria-live="polite" ${dating?'aria-label="Dating matches"':`role="tabpanel" tabindex="0" aria-labelledby="connection-tab-${state.connectionFilter}"`}></div>`;
 renderConnections();updateBadges();
}
function connectionCard(c){
 return `<article class="connection-card" data-connection-id="${esc(c.id)}">${profilePhotoButton(c.profile,c.kind)}<div class="grow"><button class="name-button" data-action="view-profile" data-id="${esc(c.profile.id)}" data-profile-context="${esc(c.kind)}"><h3>${esc(c.profile.display_name)}</h3></button><p>${esc(c.profile.program)} · @${esc(c.profile.username)}</p><span class="test-label">${testProfileLabel(c.profile)}</span></div>${category(c.kind)}<div class="actions">${c.status==='accepted'?`<button class="btn small" data-action="open-chat" data-id="${c.id}">${icon('chat')}Message</button><button class="btn secondary small" data-action="remove-connection" data-id="${c.id}">${c.kind==='dating'?'Unmatch':'Remove'}</button>`:c.direction==='received'?`<button class="btn small" data-action="connection-action" data-command="accept" data-id="${c.id}">Accept</button><button class="btn secondary small" data-action="connection-action" data-command="decline" data-id="${c.id}">Decline</button>`:`<button class="btn secondary small" data-action="connection-action" data-command="cancel" data-id="${c.id}">Cancel request</button>`}</div></article>`;
}
function connectionEmpty(f){
 if(f==='dating')return empty('heart',state.user.dating_enabled?'No matches yet.':'Your matches start here.',state.user.dating_enabled?'Like someone in Discover. When you both choose each other, your match appears here.':'Activate Dating and choose your preferences to discover eligible adults. A mutual like opens your chat.',`<a class="btn" href="/dating" data-nav>${state.user.dating_enabled?'Explore Dating':'Set up Dating'} ${icon('heart')}</a>`);
 const content={received:['No requests just yet.','Friendship and study requests appear here. You decide who can connect.'],sent:['No requests on their way.','Send a friendship or study request to someone you would like to meet.'],friend:['No friends yet.','Accepted friendship requests appear here.'],study:['Find your next study partner.','Accepted study connections appear here.']};
 const [title,copy]=content[f];
 return empty('people',title,copy,`<a class="btn secondary" href="/discover?mode=${f==='study'?'study':'friend'}" data-nav>${f==='study'?'Discover study partners':'Discover friends'} ${icon('arrow')}</a>`);
}
function renderConnections(){
 const region=$('#connection-results');if(!region)return;
 const f=state.connectionFilter,items=state.connections.filter(c=>['received','sent'].includes(f)?c.kind!=='dating'&&c.status==='pending'&&c.direction===f:c.status==='accepted'&&c.kind===f);
 const key=JSON.stringify([f,items,state.connectionLoaded,state.connectionLoading&&!state.connectionLoaded,state.connectionError]);
 region.setAttribute('aria-busy',String(state.connectionLoading));if(region._renderKey===key)return;region._renderKey=key;
 const retry='<button class="btn secondary" data-action="retry-data">Retry</button>';
 if(!state.connectionLoaded){region.innerHTML=state.connectionError?empty('compass',`Couldn’t load ${f==='dating'?'matches':'connections'}.`,'Check your connection and try again.',retry):`<p class="loading" role="status">Loading ${f==='dating'?'matches':'connections'}…</p>`;return;}
 region.innerHTML=`${state.connectionError?`<div class="refresh-error notice" role="alert"><p>Couldn’t refresh your connections. The last loaded list is shown.</p>${retry}</div>`:''}${items.length?`<div class="connection-list">${items.map(connectionCard).join('')}</div>`:connectionEmpty(f)}`;
 revealNew(region,'.connection-card',{key:'data-connection-id'});
}

function syncChatViewport(){
 const view=window.visualViewport;
 document.documentElement.style.setProperty('--chat-height',`${view?.height||window.innerHeight}px`);
 document.documentElement.style.setProperty('--chat-top',`${view?.offsetTop||0}px`);
 updateChatFooter();
}
function updateChatFooter(){const pane=$('#chat-pane'),composer=$('#composer');if(pane&&composer)pane.style.setProperty('--chat-footer-height',`${composer.getBoundingClientRect().height+($('#chat-safety')?.getBoundingClientRect().height||0)}px`);}
function resizeComposer(){const input=$('#message-input');if(!input)return;input.style.height='auto';const height=input.scrollHeight+2;input.style.height=Math.min(height,120)+'px';input.style.overflowY=height>120?'auto':'hidden';updateChatFooter();}
window.visualViewport?.addEventListener('resize',syncChatViewport);
window.visualViewport?.addEventListener('scroll',syncChatViewport);
window.addEventListener('resize',syncChatViewport);
function safetyActions(profile,inChat=false){return `<div class="safety-actions"><button type="button" class="btn secondary" data-action="${inChat?'report-conversation':'report-profile'}" data-id="${esc(profile.id)}">${icon('flag')}Report</button><button type="button" class="btn secondary" data-action="confirm-block-dialog" data-id="${esc(profile.id)}">${icon('block')}Block</button></div>`;}
function safetyDisclosure(profile,inChat=false){if(profile.id===state.user?.id)return '';return `<details ${inChat?'id="chat-safety"':''} class="${inChat?'chat-safety':'profile-safety'}"><summary>${icon('shield')}<span>Safety & support</span><span class="safety-chevron" aria-hidden="true">+</span></summary>${safetyActions(profile,inChat)}</details>`;}
function openChatSafety(){const details=$('#chat-safety'),log=$('#messages');if(!details)return;details.dataset.stick=String(!!log&&log.scrollHeight-log.scrollTop-log.clientHeight<60);details.open=true;$('summary',details)?.focus();updateChatFooter();}
function reportDialog(uid,inChat=false){
 const chat=inChat?state.chats.find(c=>c.id===state.selected&&c.profile.id===uid):null;
 if(inChat&&!chat){toast('This conversation is no longer available.');return;}
 const messages=chat?state.messages.filter(m=>m.relationship_id===chat.id&&m.sender_id===uid).slice().reverse():[];
 const choices=messages.map(m=>{const preview=Array.from(m.body.replace(/\s+/g,' ')),text=preview.slice(0,85).join('')+(preview.length>85?'…':'');return `<option value="${m.id}">${esc(stamp(m.created_at))} · ${esc(text)}</option>`;}).join('');
 dialog(inChat?'Report this conversation':'Report a profile',`<form id="report-form" class="stack" data-target="${esc(uid)}">${formError()}<p>Your report is visible only to authorized moderators. The reported student cannot see who reported them.</p>${chat?`<label>What would you like to report?<select name="message_id"><option value="">Profile or conversation</option>${choices}</select></label>`:''}<label>Reason<select name="reason"><option value="harassment">Harassment</option><option value="impersonation">Impersonation</option><option value="spam">Spam</option><option value="inappropriate">Inappropriate behavior</option><option value="other">Other</option></select></label><label>What happened? <span class="muted">(optional)</span><textarea name="detail" maxlength="2000" placeholder="Add context. Do not include sensitive personal information."></textarea></label><button class="btn" type="submit">Submit report</button></form>`);
}
function chatsPage(){
 $('#main').classList.add('chat-screen');
 $('#main').innerHTML=`${pageHeading('Inbox','')}<div class="chat-layout ${state.selected?'has-selection':''}"><aside class="inbox"><div class="inbox-title"><h3>Conversations</h3></div><div class="tabs">${[['all','All'],['friend','Friends'],['study','Study'],['dating','Dating']].map(([k,t])=>`<button data-action="chat-filter" data-filter="${k}" class="${state.chatFilter===k?'active':''}" aria-pressed="${state.chatFilter===k}">${t}</button>`).join('')}</div><div id="message-requests"></div><div id="inbox-list"></div></aside><section class="chat-pane" id="chat-pane" aria-label="Conversation"></section></div>`;
 renderInbox();openConversation(state.selected,false);
}
function renderInbox(){
 renderRequests();const region=$('#inbox-list');if(!region)return;if(!state.chatLoaded){region.innerHTML=state.chatError?'<div class="chat-placeholder" role="alert"><p>Couldn’t load your chats.</p><button class="btn secondary" data-action="retry-data">Retry</button></div>':'<p class="loading" role="status">Loading chats…</p>';return;}const list=state.chats.filter(c=>state.chatFilter==='all'||c.kind===state.chatFilter);const renderKey=JSON.stringify([state.selected,state.chatFilter,list,state.chatError]);if(region._renderKey===renderKey)return;region._renderKey=renderKey;const content=list.length?list.map(c=>`<button class="conversation-item ${state.selected===c.id?'selected':''}" data-action="select-chat" data-id="${c.id}" aria-label="${esc(c.profile.display_name)}, ${labels[c.kind]}${c.unread?`, ${c.unread} unread`:''}">${avatar(c.profile)}<div class="grow"><strong>${esc(c.profile.display_name)}</strong><p>${esc(c.last_message?.body||'Your connection is ready. Say hello!')}</p><span class="kind">${labels[c.kind]}</span></div>${c.unread?`<span class="badge">${c.unread}</span>`:''}</button>`).join(''):'<div class="chat-placeholder"><p>Your mutual dating matches and accepted connections appear here.</p><a class="text-button" href="/matches" data-nav>See dating matches</a><a class="text-button" href="/connections" data-nav>Friends & study</a></div>';region.innerHTML=(state.chatError?'<div class="notice refresh-error" role="alert"><p>Couldn’t refresh chats. The last loaded inbox is shown.</p><button class="text-button" data-action="retry-data">Retry</button></div>':'')+content;}
async function openConversation(id,load=true){
 const pane=$('#chat-pane');if(!pane)return;
 starterManager?.destroy();starterManager=null;
 state.selected=id;const chat=state.chats.find(c=>c.id===id);$('.chat-layout')?.classList.toggle('has-selection',!!chat);document.body.classList.toggle('conversation-open',!!chat);syncChatViewport();renderInbox();
 if(!chat){state.selected=null;state.messages=[];pane.innerHTML=`<div class="chat-placeholder">${icon('chat')}<h2>Your messages</h2><p>Choose a conversation or check your message requests.</p></div>`;return;}
 pane.innerHTML=`<header class="chat-header" data-chat-kind="${esc(chat.kind)}"><button class="icon-button back-chat" data-action="back-inbox" aria-label="Back to conversations">${icon('back')}</button><button type="button" class="chat-profile" data-action="view-profile" data-id="${esc(chat.profile.id)}" data-profile-context="${esc(chat.kind)}" aria-label="View ${esc(chat.profile.display_name)}’s profile">${avatar(chat.profile)}<span><strong>${esc(chat.profile.display_name)}</strong><small>View profile</small></span></button><button class="icon-button" data-action="student-menu" data-id="${esc(chat.profile.id)}" aria-label="Conversation options">${icon('more')}</button></header>${chat.kind==='dating'?'<section id="conversation-starters" class="conversation-starters" aria-label="Conversation starters" hidden></section>':''}<div class="messages" id="messages" role="log" aria-label="Messages" aria-live="polite"><div class="loading">Opening conversation…</div></div><button type="button" id="new-message-jump" class="new-message-jump" data-action="jump-latest" hidden>New messages ↓</button><form id="composer" class="composer"><label class="grow"><span class="sr-only">Message ${esc(chat.profile.display_name)}</span><textarea name="body" id="message-input" required maxlength="4000" rows="1" placeholder="Message…">${esc(state.drafts.get(id)||'')}</textarea></label><button class="btn" type="submit" aria-label="Send message">${icon('send')}</button></form>${safetyDisclosure(chat.profile,true)}`;
 resizeComposer();
 const safety=$('#chat-safety');
 safety?.addEventListener('click',event=>{if(event.target.closest('summary')){const log=$('#messages');safety.dataset.stick=String(log.scrollHeight-log.scrollTop-log.clientHeight<60);}});
 safety?.addEventListener('toggle',()=>{updateChatFooter();if(safety.dataset.stick==='true'){const log=$('#messages');if(log)log.scrollTop=log.scrollHeight;}});
 $('#messages').addEventListener('scroll',()=>{const log=$('#messages');if(log&&log.scrollHeight-log.scrollTop-log.clientHeight<60){$('#new-message-jump').hidden=true;clearTimeout(readTimer);readTimer=setTimeout(()=>markRead().catch(()=>{}),150);}},{passive:true});
 if(load||!state.messages.length||state.messages[0]?.relationship_id!==id)state.messages=[];
 try{const result=await api(`/chats/${id}/messages`);if(state.selected!==id||path()!=='/chats')return;chat.receipts=result.receipts;state.messages=result.items;state.older=result.has_more;renderMessages(true);mountStarters(chat);await acknowledgeConversation(id);}catch(e){if(e.stale)return;if(e.status===401){signout();return;}if(state.selected===id){
  const denied=[403,404].includes(e.status);starterManager?.destroy();starterManager=null;
  $('#messages').dataset.renderKey='';
  $('#messages').innerHTML=empty('lock',denied?'Conversation unavailable.':'Couldn’t load messages.',denied?e.message:'Check your connection and retry.',denied?'<a class="btn secondary" href="/matches" data-nav>See matches</a>':'<button class="btn secondary" data-action="retry-conversation">Retry messages</button>');
  $('#composer').classList.add('hidden');
 }}
}
function starterSignature(chat){return JSON.stringify([state.user?.interests,chat.profile.interests,chat.profile.prompts]);}
function mountStarters(chat){
 const root=$('#conversation-starters');if(!root||chat.kind!=='dating')return;
 const rid=chat.id;
 starterManager?.destroy();
 starterManager=new ConversationStarters(root,{api,conversationId:rid,expanded:state.starterOpen.get(rid)??false,signature:starterSignature(chat),esc,
  onToggle:expanded=>state.starterOpen.set(rid,expanded),
  onPick:text=>{
   const input=$('#message-input');
   if(state.selected!==rid||!state.chats.some(c=>c.id===rid&&c.kind==='dating')||!input||input.closest('form').classList.contains('hidden'))return 'This conversation is no longer available.';
   if(state.outbox.has(rid))return 'Retry your unsent message before choosing another starter.';
   if(input.value.trim()){input.focus();return 'Your draft is safe. Clear the message box first to choose another starter.';}
   input.value=text;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();resizeComposer();
   return '';
  }});
}
function messageDay(timestamp){return new Date(timestamp*1000).toLocaleDateString('en-CA',{timeZone:'Africa/Lusaka',year:'numeric',month:'2-digit',day:'2-digit'});}
function messageTime(timestamp){return new Date(timestamp*1000).toLocaleTimeString(undefined,{timeZone:'Africa/Lusaka',hour:'2-digit',minute:'2-digit'});}
function messageDateLabel(timestamp){const day=messageDay(timestamp);if(day===messageDay(Date.now()/1000))return 'Today';if(day===messageDay(Date.now()/1000-86400))return 'Yesterday';return new Date(timestamp*1000).toLocaleDateString(undefined,{timeZone:'Africa/Lusaka',day:'numeric',month:'short',year:'numeric'});}
function sameMessageGroup(a,b){return !!a&&!!b&&a.sender_id===b.sender_id&&Math.abs(a.created_at-b.created_at)<300&&messageDay(a.created_at)===messageDay(b.created_at);}
function renderMessages(scroll=false){
 const region=$('#messages');if(!region)return;
 const nearBottom=region.scrollHeight-region.scrollTop-region.clientHeight<90,previousTop=region.scrollTop;
 const chat=state.chats.find(c=>c.id===state.selected),pending=state.outbox.get(state.selected),showPending=pending&&!state.messages.some(m=>m.client_id===pending.client_id&&m.sender_id===state.user.id);
 const send=$('#composer button[type=submit]');if(send){send.disabled=pending?.status==='sending';send.setAttribute('aria-busy',String(send.disabled));}
 const renderKey=JSON.stringify([chat?.receipts,state.messages.map(m=>m.id),chat?.profile.main_photo_url,showPending?pending.client_id:null,showPending?pending.status:null,state.older]);
 if(region.dataset.renderKey===renderKey){if(scroll)region.scrollTop=region.scrollHeight;return;}
 const previousLast=region.dataset.lastMessage;
 region.dataset.renderKey=renderKey;region.dataset.lastMessage=String(state.messages.at(-1)?.id||'');
 const jump=$('#new-message-jump');if(jump){if(scroll||nearBottom)jump.hidden=true;else if(previousLast&&previousLast!==region.dataset.lastMessage)jump.hidden=false;}
 const rows=state.messages.map((m,index)=>{
  const own=m.sender_id===state.user.id,previous=state.messages[index-1],next=state.messages[index+1];
  const grouped=sameMessageGroup(previous,m),last=!sameMessageGroup(m,next);
  const separator=!previous||messageDay(previous.created_at)!==messageDay(m.created_at)?`<div class="message-date"><span>${esc(messageDateLabel(m.created_at))}</span></div>`:'';
  return `${separator}<div class="message ${own?'own':'incoming'} ${grouped?'is-grouped':''} ${last?'group-end':''}" data-message-id="${m.id}" data-motion-key="${esc(m.sender_id+':'+m.client_id)}">${!own?`<div class="message-avatar">${last&&chat?profilePhotoButton(chat.profile,chat.kind):''}</div>`:''}<div class="message-content"><div class="bubble">${esc(m.body)}</div><div class="message-meta">${last?`<time datetime="${new Date(m.created_at*1000).toISOString()}" title="${esc(stamp(m.created_at))}">${esc(messageTime(m.created_at))}</time>${own?`<span class="message-status">${messageStatus(m.id,chat)}</span>`:''}`:''}</div></div></div>`;
 }).join('');
 region.innerHTML=`${state.older?'<div class="row center"><button class="text-button" data-action="older-messages">Load older messages</button></div>':''}${rows||'<div class="conversation-empty"><p>Say hello</p><span>Send your first message.</span></div>'}${showPending?`<div class="message own pending-message" data-motion-key="${esc(state.user.id+':'+pending.client_id)}"><div class="message-content"><div class="bubble">${esc(pending.body)}</div><div class="message-meta">${pending.status==='failed'?'<button class="text-button" data-action="retry-message">Send failed · Retry</button>':'Sending…'}</div></div></div>`:''}`;
 revealNew(region,'.message',{key:'data-motion-key',initial:false,enabled:scroll||nearBottom,effect:'motion-message',limit:4});
 if(scroll||nearBottom)region.scrollTop=region.scrollHeight;else region.scrollTop=previousTop;
}
function receivedMid(){for(let i=state.messages.length-1;i>=0;i--)if(state.messages[i].sender_id!==state.user.id)return state.messages[i].id;return 0;}
async function acknowledgeConversation(rid){if(state.selected!==rid)return;const mid=receivedMid();await markRead();if(state.selected===rid)await acknowledgeDelivery(rid,mid);}
function messageStatus(mid,chat){return mid<=(chat?.receipts?.read||0)?'Read':mid<=(chat?.receipts?.delivered||0)?'Delivered':'Sent';}
async function acknowledgeDelivery(rid,mid){
 if(!mid||mid<=(state.delivered.get(rid)||0))return;
 await api(`/chats/${rid}/delivered`,'POST',{message_id:mid});state.delivered.set(rid,Math.max(mid,state.delivered.get(rid)||0));
}
async function markRead(){
 const rid=state.selected,log=$('#messages');
 if(!rid||!state.messages.length||document.hidden||$('#dialog').open||!log||log.scrollHeight-log.scrollTop-log.clientHeight>60)return;
 const mid=receivedMid();
 if(!mid||mid<=(state.read.get(rid)||0))return;
 await api(`/chats/${rid}/read`,'POST',{message_id:mid});state.read.set(rid,Math.max(mid,state.read.get(rid)||0));state.delivered.set(rid,Math.max(mid,state.delivered.get(rid)||0));
 const chat=state.chats.find(c=>c.id===rid);if(chat){chat.unread=0;updateBadges();renderInbox();}
}
async function syncMessages(){
 const rid=state.selected;if(!rid||!$('#messages'))return;
 if(!state.chats.some(c=>c.id===rid)){state.selected=null;state.messages=[];toast('This conversation is no longer active.');chatsPage();return;}
 try{let after=state.messages.at(-1)?.id||0,more=true;while(more){const r=await api(`/chats/${rid}/messages${after?'?after='+after:''}`);if(rid!==state.selected||path()!=='/chats')return;const active=state.chats.find(c=>c.id===rid);if(active)active.receipts=r.receipts;const known=new Set(state.messages.map(m=>m.id));state.messages.push(...r.items.filter(m=>!known.has(m.id)));more=after&&r.has_more;if(!after)state.older=r.has_more;after=state.messages.at(-1)?.id||0;}const pending=state.outbox.get(rid);if(pending&&state.messages.some(m=>m.client_id===pending.client_id&&m.sender_id===state.user.id)){state.outbox.delete(rid);if(state.drafts.get(rid)===pending.body){state.drafts.delete(rid);if($('#message-input')?.value===pending.body){$('#message-input').value='';resizeComposer();}}}$('#composer')?.classList.remove('hidden');renderMessages();const activeChat=state.chats.find(c=>c.id===rid);if(activeChat?.kind==='dating'&&!starterManager)mountStarters(activeChat);await acknowledgeConversation(rid);}catch(e){if([403,404].includes(e.status)){state.selected=null;state.messages=[];await refreshData();chatsPage();}else showError(e);}
}
async function sendMessage(retry=false){
 const rid=state.selected;if(!rid)return;const old=state.outbox.get(rid);
 if(old?.status==='sending')return;
 const body=retry?old?.body:$('#message-input')?.value.trim();if(!body)return;
 const pending=old&&old.body===body?old:{client_id:newMessageId(),body};pending.status='sending';state.outbox.set(rid,pending);renderMessages(true);
 try{const r=await api(`/chats/${rid}/messages`,'POST',{body,client_id:pending.client_id});state.outbox.delete(rid);if(state.drafts.get(rid)?.trim()===body){state.drafts.delete(rid);if(rid===state.selected&&$('#message-input')?.value.trim()===body)$('#message-input').value='';}if(rid===state.selected){if(!state.messages.some(m=>m.id===r.message.id))state.messages.push(r.message);renderMessages(true);}resizeComposer();await refreshData();}
 catch(e){if(e.stale)return;pending.status='failed';state.outbox.set(rid,pending);if(rid===state.selected)renderMessages(true);showError(e);}
}

function profilePage(){
 const u=state.user;
 $('#main').innerHTML=`${pageHeading('Profile','Manage your photos and details.')}<nav class="profile-edit-nav" aria-label="Edit profile sections"><a href="#photo-manager" data-profile-section class="btn secondary small">Photos</a><a href="#prompt-manager" data-profile-section class="btn secondary small">Prompts</a><button type="button" class="btn secondary small" data-action="dating-settings">Dating preferences & intention</button><a href="#profile-details" data-profile-section class="btn secondary small">Profile & studies</a><a href="#profile-visibility" data-profile-section class="btn secondary small">Visibility</a></nav><div class="profile-layout"><div class="profile-main"><section class="panel profile-public-likes" aria-label="Public profile activity"><button type="button" class="btn secondary" data-action="public-profile-likes" data-id="${esc(u.id)}">${icon('heart')}Profile likes</button><a class="btn secondary" href="/feed?student=${esc(u.id)}" data-nav>My posts</a></section><section id="photo-manager" class="panel" tabindex="-1"></section><section id="prompt-manager" class="panel" tabindex="-1"></section><section id="profile-details" class="panel" tabindex="-1"><form id="profile-form" class="profile-form">${formError()}<div class="row">${avatar(u,true)}<div><h2>${esc(u.display_name)}</h2><span class="test-label">${testProfileLabel(u)}</span></div></div><div class="field-grid"><label>Display name<input name="display_name" value="${esc(u.display_name)}" maxlength="60" required></label><label>Username<input name="username" value="${esc(u.username)}" minlength="3" maxlength="24" required></label></div><label>About you<textarea name="bio" maxlength="500">${esc(u.bio)}</textarea></label><h3 class="section-label">Your studies</h3><div class="field-grid"><label>Program<input name="program" value="${esc(u.program)}" maxlength="100"></label><label>Year<select name="year">${Array.from({length:7},(_,i)=>`<option ${u.year===i+1?'selected':''}>${i+1}</option>`).join('')}</select></label></div><label>Subjects <span class="muted">(comma separated)</span><input name="subjects" value="${esc(u.subjects)}" maxlength="300"></label><label>Skills <span class="muted">(comma separated)</span><input name="skills" value="${esc(u.skills)}" maxlength="300"></label><label>Learning goals <span class="muted">(comma separated)</span><input name="study_goals" value="${esc(u.study_goals)}" maxlength="300"></label><h3 class="section-label">Your interests</h3>${interestOptions(u.interests)}<h3 id="profile-visibility" class="section-label" tabindex="-1">Visibility & connections</h3>${check('friend_goal','Open to friendship requests',u.friend_goal)}${check('study_goal','Open to study partner requests',u.study_goal)}${check('discoverable','Show my profile in discovery and student search',u.discoverable)}<small class="muted">Existing accepted connections can still view your profile when discovery is off.</small>${check('notifications_enabled','Enable in-app connection and message notifications',u.notifications_enabled)}<button type="submit" class="btn">Save changes ${icon('check')}</button></form></section></div><aside class="stack"><section class="panel"><h3>Your account</h3><p class="muted">${esc(u.email)}</p><div class="settings-list"><button data-action="dating-settings">${icon('heart')}Dating settings</button><button data-action="security">${icon('lock')}Account security</button><a class="text-button" href="/verification" data-nav>Email and eligibility</a><button data-action="blocked-users">${icon('block')}Blocked students</button><button data-action="my-reports">${icon('flag')}Reports & support</button>${u.role==='moderator'?'<button data-action="moderation">'+icon('shield')+'Moderation queue</button>':''}<button data-action="pilot-feedback">${icon('comment')}Send feedback</button>${u.operator?'<button data-action="operator-console">'+icon('settings')+'Operator console</button>':''}<button data-action="logout">${icon('logout')}Sign out</button><button data-action="account-dialog" data-command="deactivate">${icon('user')}Deactivate account</button><button class="danger" data-action="account-dialog" data-command="delete">${icon('close')}Delete account</button></div></section><div class="notice">CampusLink is independent of ZUT. ${state.catalog.eligibility_mode==='external'?'Student and 18+ checks are managed in Email and eligibility.':'Student eligibility is not verified in this preview.'}<br><a href="/privacy" data-nav>Draft privacy notice</a> · <a href="/terms" data-nav>Draft terms</a> · <a href="/support" data-nav>Support</a></div></aside></div>`;
 mountPhotoManager();
 mountPromptManager();
}

function refreshAvatars(){
 const profiles=new Map([state.user,...state.connections.map(c=>c.profile),...state.chats.map(c=>c.profile)].filter(Boolean).map(p=>[p.id,p]));
 for(const node of $$('[data-avatar-user]')){const profile=profiles.get(node.dataset.avatarUser);if(profile&&node.dataset.photoUrl!==(profile.main_photo_url||'')){const large=node.classList.contains('large');node.outerHTML=avatar(profile,large);}}
}
function mountPhotoManager(){
 photoManager?.destroy();
 const root=$('#photo-manager');if(!root)return;
 if(needsApproval()){root.innerHTML='<p class="notice">You can add photos after the operator approves your membership. Return to Profile once approved.</p>';return;}
 photoManager=new PhotoManager(root,{getUser:()=>state.user,api,esc,onChange:async result=>{if(!state.user||state.user.id!==result.user.id)return;state.user={...state.user,photos:result.user.photos,main_photo_url:result.user.main_photo_url};refreshAvatars();photoManager?.render();toast('Photo changes saved.');}});
}
function mountPromptManager(){
 promptManager?.destroy();
 const root=$('#prompt-manager');if(!root)return;
 state.promptDraft ||= createPromptDraft(state.user);
 promptManager=new PromptManager(root,{draft:state.promptDraft,catalog:state.catalog.prompts,limits:state.catalog.prompt_limits,api,esc,
  onChange:result=>{if(!state.user||state.user.id!==result.user.id)return;state.user={...state.user,prompts:result.user.prompts};toast('Personality answers saved.');},
  onState:()=>promptManager?.render()});
}
async function refreshData(){
 if(!state.user||refreshing)return;refreshing=true;
 const epoch=state.authEpoch||0;
 state.connectionLoading=true;state.chatLoading=true;
 if(['/matches','/connections'].includes(path()))renderConnections();
 if(path()==='/chats')renderInbox();
 try{
  const results=await Promise.allSettled([api('/connections'),api('/chats'),api('/notifications'),api('/message-requests'),api('/me')]);
  if(epoch!==(state.authEpoch||0))return;
  if(results.some(r=>r.status==='rejected'&&r.reason.status===401)){signout();return;}
  if(results[4].status==='fulfilled')setUser(results[4].value);
  if(needsApproval()){source?.close();source=null;state.chats=[];state.connections=[];state.students=[];state.messages=[];state.selected=null;if(!['/profile','/operator','/verification','/approval'].includes(path()))go('/approval',true);return;}
  if(needsStudentVerification()){source?.close();source=null;state.chats=[];state.connections=[];state.students=[];state.messages=[];state.selected=null;if(!['/profile','/operator','/verification'].includes(path()))go('/verification',true);return;}
  if(path()==='/approval'){connectEvents();go('/discover',true);}
  if(!source)connectEvents();
  const [c,h,n,r]=results;
  if(c.status==='fulfilled'){state.connections=c.value.items;state.connectionLoaded=true;state.connectionError='';}
  else if(!c.reason.stale)state.connectionError='Connections could not refresh.';
  if(h.status==='fulfilled'){state.chats=h.value.items;state.chatLoaded=true;state.chatError='';}
  else if(!h.reason.stale)state.chatError='Chats could not refresh.';
  if(n.status==='fulfilled')state.notifications=n.value.items;
  if(r.status==='fulfilled'){state.requests=r.value.items;state.requestLoaded=true;state.requestError='';}else if(!r.reason.stale)state.requestError='Message requests could not refresh.';


  refreshAvatars();updateBadges();
  if(path()==='/chats'){
   renderInbox();
   if(h.status==='fulfilled'){
    const chat=state.chats.find(c=>c.id===state.selected);
    if(chat?.kind==='dating')starterManager?.refresh(starterSignature(chat));else{starterManager?.destroy();starterManager=null;}
    await syncMessages();
   }
  }
  if(h.status==='fulfilled')await Promise.allSettled(h.value.items.filter(c=>c.last_message&&c.last_message.sender_id!==state.user.id).map(c=>acknowledgeDelivery(c.id,c.last_message.id)));
 }finally{
  refreshing=false;
  if(epoch===(state.authEpoch||0)){
   state.connectionLoading=false;state.chatLoading=false;
   if(['/matches','/connections'].includes(path()))renderConnections();
   if(path()==='/chats')renderInbox();
  }
 }
}
function updateBadges(){
 const requests=state.connections.filter(c=>c.status==='pending'&&c.direction==='received'&&c.kind!=='dating').length;
 const counts={requests,chats:state.chats.reduce((n,c)=>n+c.unread,0)+state.requests.filter(r=>r.direction==='received').length};
 for(const [key,value] of Object.entries(counts))for(const badge of $$(`[data-badge="${key}"]`)){badge.textContent=value;badge.classList.toggle('hidden',!value);}
 for(const link of $$('[data-request-link]'))link.setAttribute('aria-label',`Friends and study${requests?`, ${requests} pending request${requests===1?'':'s'}`:''}`);
 const badge=$('#notification-badge'),count=state.notifications.filter(n=>!n.read).length;
 if(badge){badge.textContent=count;badge.classList.toggle('hidden',!count);badge.parentElement.setAttribute('aria-label',`Notifications${count?`, ${count} unread`:''}`);}
}
function liveStatus(value){state.live=value;const el=$('#live-status');if(el){el.classList.toggle('hidden',value);el.textContent='Reconnecting…';}}
function connectEvents(){
 if(needsApproval()||needsStudentVerification()){source?.close();source=null;return;}
 source?.close();source=new EventSource('/api/events');source.addEventListener('ready',()=>{liveStatus(true);refreshData();if(path()==='/discover')loadStudents();});source.addEventListener('refresh',()=>{clearTimeout(refreshTimer);refreshTimer=setTimeout(async()=>{await refreshData();if(path()==='/discover')loadStudents();},150);});source.addEventListener('membership',()=>{source?.close();source=null;refreshData();});source.addEventListener('expired',()=>{toast('Your session ended. Please sign in again.');signout();});source.onerror=()=>liveStatus(false);
}

async function renderRoute(){
 feedManager?.destroy();feedManager=null;
 operatorConsole?.destroy();operatorConsole=null;
 document.body.classList.remove('conversation-open');
 photoManager?.destroy();photoManager=null;
 promptManager?.destroy();promptManager=null;
 starterManager?.destroy();starterManager=null;
 let route=path();if(route==='/dating'){resetDiscovery();route='/discover';history.replaceState({},'','/discover');}const view=routeView(new URL(location.href));if(route==='/discover'&&state.mode!==view.discovery)resetDiscovery(view.discovery);if(route==='/matches')state.connectionFilter='dating';if(route==='/connections')state.connectionFilter=view.connections;document.title=`CampusLink · ${{'/feed':'Feed','/discover':'Discover','/connections':'Friends & study','/matches':'Matches','/chats':'Inbox','/profile':'Profile','/login':'Sign in','/signup':'Get started','/onboarding':'Your introduction'}[route]||'Find your people'}`;
 if(route==='/privacy'||route==='/terms'){legal(route.slice(1));return;}
 if(route==='/support'){supportPage();return;}
 if(route==='/verify-email'){confirmEmailPage();return;}
 if(route==='/forgot-password'||route==='/reset-password'){recoveryPage(route==='/reset-password');return;}
 if(route==='/'){landing();return;}
 if(route==='/login'||route==='/signup'){if(state.user){go(state.user.onboarding_step<6?'/onboarding':'/discover',true);return;}authPage(route==='/signup');return;}
 if(!state.user){go('/login',true);return;}
 if((state.user.onboarding_step<6&&!(route==='/operator'&&state.user.operator))||route==='/onboarding'){if(state.user.onboarding_step===6){go('/discover',true);return;}if(route!=='/onboarding')history.replaceState({},'','/onboarding');onboarding();return;}
 if(needsApproval()&&!['/profile','/operator','/verification','/approval'].includes(route)){go('/approval',true);return;}
 if(needsStudentVerification()&&!['/profile','/operator','/verification','/approval'].includes(route)){go('/verification',true);return;}
 if(route==='/approval'){if(needsApproval())approvalPage();else go('/discover',true);return;}
 if(route==='/verification'){await verificationPage();return;}
 if(!['/feed','/discover','/matches','/connections','/chats','/profile','/operator'].includes(route)){app.innerHTML=`<main class="legal" id="main">${publicHeader()}${empty('compass','This page isn’t here.','Head back to your campus circle.','<a href="/discover" data-nav class="btn">Open Discover</a>')}</main>`;return;}
 shell(route==='/connections'?'matches':route.slice(1));if(route==='/feed')feedPage();if(route==='/discover')discoveryPage();if(route==='/connections'||route==='/matches')connectionsPage();if(route==='/chats')chatsPage();if(route==='/profile')profilePage();if(route==='/operator'){operatorConsole=new OperatorConsole($('#main'),{api,esc,download:downloadOperatorBackup});}
}

document.addEventListener('click',async event=>{
 const sectionLink=event.target.closest('a[data-profile-section]');
 if(sectionLink){event.preventDefault();history.replaceState({},'',sectionLink.hash);focusPage(sectionLink.hash);return;}
 const nav=event.target.closest('a[data-nav]');if(nav&&!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&!event.altKey&&event.button===0){event.preventDefault();if(nav.getAttribute('href')==='/discover')resetDiscovery();go(nav.getAttribute('href'));return;}
 const button=event.target.closest('[data-action]');if(!button)return;const {action,id,kind,command,filter}=button.dataset;
 try{
  if(action==='close-dialog'){$('#dialog').close();return;}
  if(isStaging()&&['test-accounts','dating-test-accounts','switch-dating-test'].includes(action)){toast('Create your own fictional account for this preview.');return;}
  if(action==='test-accounts'){dialog('Try both sides of a connection',`<p>These are fictional, unverified local fixtures. Use separate browser profiles or a private window for each student.</p><div class="notice"><strong>Email:</strong> alice@campuslink.test<br><strong>Second student:</strong> brian@campuslink.test<br><strong>Password:</strong> CampusLink-local-2026!</div><p>Run the seed command in the README first. Other fixtures: chipo, david, esther, farai, grace, moderator @campuslink.test.</p>`);return;}
  if(action==='discover-mode'){const mode=button.dataset.mode;if(!DISCOVERY_MODES.includes(mode))return;resetDiscovery(mode);go(mode==='dating'?'/discover':`/discover?mode=${mode}`);$(`[data-action=discover-mode][data-mode="${mode}"]`)?.focus();return;}
  if(action==='toggle-filters'){state.filtersOpen=!state.filtersOpen;$('#search-filters').classList.toggle('hidden',!state.filtersOpen);button.setAttribute('aria-expanded',state.filtersOpen);return;}
  if(action==='clear-filters'){state.query='';state.program='';state.interest='';state.year=0;state.intention='';discoveryPage();return;}
  if(action==='retry-discovery'){await loadStudents();return;}
  if(action==='retry-data'){await refreshData();return;}
  if(action==='retry-conversation'){await openConversation(state.selected);return;}
  if(action==='more-students'){button.disabled=true;await loadStudents(true);return;}
  if(action==='public-profile-likes'){await showLikes(`/profiles/${id}/likes`);return;}
  if(action==='private-comment'){await privateComment(id,kind||'friend');return;}
  if(action==='profile-inbox'){await profileInbox(id,kind||'friend');return;}
  if(action==='request-decision'){button.disabled=true;const result=await api(`/message-requests/${id}/${command}`,'POST',{});await refreshData();if(result.conversation_id){state.selected=result.conversation_id;go('/chats');}return;}
  if(action==='delete-post-dialog'){dialog('Delete this post?',`<p>This will remove the post and its photo.</p><button class="btn danger" data-action="delete-post" data-id="${esc(id)}">Delete post</button>`);return;}
  if(action==='delete-post'){await api('/posts/'+id,'DELETE');$('#dialog').close();await feedManager?.refresh();toast('Post deleted.');return;}
  if(action==='connect'){button.disabled=true;const r=await api('/connections','POST',{target_id:id,kind});toast(r.status==='accepted'?'You’re connected. Your chat is ready.':'Request sent. They can accept it in Matches → Friends & study.');await refreshData();await loadStudents();return;}
  if(action==='like'){button.disabled=true;button.setAttribute('aria-busy','true');const name=state.students.find(p=>p.id===id)?.display_name||'your connection';const undo=button.getAttribute('aria-pressed')==='true';const r=undo?await api(`/profiles/${id}/like`,'DELETE'):await api(`/profiles/${id}/like`,'POST',{context:kind==='dating'?'dating':'campus'});button.setAttribute('aria-pressed',String(!undo));button.innerHTML=icon('heart')+(undo?'Like':'Liked');if(!undo)likeFeedback(button);await refreshData();await loadStudents();if(r.matched){dialog('It’s a match.',`<div class="match-celebration">${icon('heart')}<h3>You matched with ${esc(name)}.</h3><p>Your conversation is ready.</p><button class="btn" data-action="open-chat" data-id="${esc(r.id)}">${icon('chat')}Say hello</button><button class="btn secondary" data-action="close-dialog">Keep exploring</button></div>`);}else toast(undo?'Like removed.':'Like added.',undo?'':'like');return;}
  if(action==='dismiss'){button.disabled=true;if($('#dialog').open)$('#dialog').close();for(const k of kind.split(','))await api(`/discover/${id}/dismiss`,'POST',{kind:k});await loadStudents();return;}
  if(action==='connection-filter'){if(!CONNECTION_VIEWS.includes(filter))return;go(`/connections?view=${filter}`);$(`#connection-tab-${filter}`)?.focus();return;}
  if(action==='connection-action'){button.disabled=true;await api(`/connections/${id}/${command}`,'POST',{});toast(command==='accept'?'Connection accepted. You can now chat.':'Request '+(command==='decline'?'declined.':'cancelled.'));await refreshData();return;}
  if(action==='remove-connection'){dialog('End this connection?',`<p>Both people will lose access to this conversation. Existing messages remain stored until account deletion. A newly accepted request can restore that history after fresh consent.</p><button class="btn danger" data-action="confirm-remove" data-id="${esc(id)}">End connection</button>`);return;}
  if(action==='confirm-remove'){await api(`/connections/${id}/remove`,'POST',{});$('#dialog').close();toast('Connection ended. Messaging is closed.');await refreshData();return;}
  if(action==='open-chat'){state.selected=id;await refreshData();go('/chats');return;}
  if(action==='chat-filter'){state.chatFilter=filter;chatsPage();return;}
  if(action==='select-chat'){await openConversation(id,true);return;}
  if(action==='back-inbox'){await openConversation(null);return;}
  if(action==='jump-latest'){$('#messages').scrollTop=$('#messages').scrollHeight;button.hidden=true;await markRead();return;}
  if(action==='retry-message'){await sendMessage(true);return;}
  if(action==='older-messages'){button.disabled=true;const rid=state.selected,region=$('#messages'),oldHeight=region.scrollHeight;const r=await api(`/chats/${rid}/messages?before=${state.messages[0].id}`);if(rid!==state.selected)return;state.messages=[...r.items,...state.messages];state.older=r.has_more;renderMessages();region.scrollTop=region.scrollHeight-oldHeight;return;}
  if(action==='view-profile'){await showProfile(id,button.dataset.profileContext||(button.closest('.dating-card')?'dating':'general'));return;}
  if(action==='view-photo'){const url=button.dataset.url;if(!/^\/api\/photos\/[a-f0-9-]+(?:\?v=\d+)?$/.test(url||''))return;dialog('Profile photo',`<img class="photo-lightbox" data-profile-photo src="${esc(url)}" alt="Profile photo"><p class="photo-unavailable-note">This photo is unavailable. The profile may have changed or access may have ended.</p>`);return;}
  if(action==='student-menu'){
   const chat=state.chats.find(c=>c.id===state.selected&&c.profile.id===id),context=chat?.kind||(button.closest('.dating-card')?'dating':'general');
   dialog('Conversation options',`<button class="btn secondary" data-action="view-profile" data-id="${esc(id)}" data-profile-context="${esc(context)}">${icon('user')}View profile</button>${!chat&&button.closest('.dating-card')?`<button class="btn secondary" data-action="dismiss" data-id="${esc(id)}" data-kind="dating">Pass</button>`:''}${chat?`<button class="btn secondary" data-action="remove-connection" data-id="${esc(chat.id)}">${icon('close')}${chat.kind==='dating'?'Unmatch':'End connection'}</button><button class="text-button" data-action="chat-info">About this chat</button>`:''}<button type="button" class="btn secondary" data-action="${chat?'open-chat-safety':'profile-safety-dialog'}" data-id="${esc(id)}">${icon('shield')}Safety & support</button>`);return;
  }
  if(action==='open-chat-safety'){$('#dialog').close();openChatSafety();return;}
  if(action==='profile-safety-dialog'){dialog('Safety & support',safetyActions({id}));return;}
  if(action==='chat-info'){dialog('About this chat',`<p>Sent means the server saved your message. Delivered means the recipient’s signed-in device received it. Read means they opened the conversation and viewed the latest messages.</p><p>Messages are stored on the server and are not end-to-end encrypted. Unmatching, blocking or disabling Dating ends the relevant conversation access.</p><small class="muted">Local test build · Profiles and adult declarations are unverified.</small>`);return;}
  if(action==='confirm-block-dialog'){dialog('Block this student?',`<p>Blocking ends all connections between you, stops messaging and hides your profiles from each other. Unblocking does not restore connections.</p><button class="btn danger" data-action="block-student" data-id="${esc(id)}">Block student</button>`);return;}
  if(action==='block-student'){await api('/blocks/'+id,'POST',{});$('#dialog').close();toast('Student blocked. Your connections and conversations are closed.');await refreshData();if(path()==='/discover')loadStudents();return;}
  if(action==='report-profile'||action==='report-conversation'){reportDialog(id,action==='report-conversation');return;}
  if(action==='notifications'){dialog('Your updates',`${state.notifications.length?state.notifications.map(n=>`<div class="notification ${n.read?'':'unread'}">${esc(n.body)}<p>${stamp(n.created_at)}</p></div>`).join(''):'<p>No updates yet. Connection and message notifications will appear here.</p>'}`);await api('/notifications/read','POST',{});state.notifications.forEach(n=>n.read=1);updateBadges();return;}
  if(action==='open-profile-settings'){go('/profile');return;}
  if(action==='dating-settings'&&needsApproval()){go('/approval');return;}
  if(action==='dating-settings'){dialog('Dating settings',datingSettingsForm(state.user,{icon,esc,check,formError,demoAccounts:!isStaging()}));return;}
  if(action==='view-dating-matches'){go('/matches');return;}
  if(action==='dating-test-accounts'){dialog('Try Dating with an adult test account',`<p>You’re currently signed in as <strong>${esc(state.user.display_name)}</strong>. Choosing below switches this browser to a fictional adult account. Your current account stays saved.</p><div class="notice">All demo accounts are fictional and unverified. They exist to test 18+ Dating locally.</div><button class="btn" data-action="switch-dating-test" data-account="alice">Use Alice’s adult test profile</button><button class="btn secondary" data-action="switch-dating-test" data-account="brian">Use Brian’s adult test profile</button><small class="muted">Uses the local fixture password from the README. If you changed it, sign in normally.</small>`);return;}
  if(action==='switch-dating-test'){button.disabled=true;const account=button.dataset.account;if(!['alice','brian'].includes(account))return;const r=await api('/auth/login','POST',{email:account+'@campuslink.test',password:'CampusLink-local-2026!'});source?.close();setUser(r);$('#dialog').close();await refreshData();connectEvents();go('/dating');toast('Adult test account opened. Choose Set up Dating to opt in.');return;}
  if(action==='dating-guide'){dialog('How Dating works',`<div class="stack"><p><strong>1. Opt in.</strong> Open Set up Dating, choose your preferences, and explicitly activate it.</p><p><strong>2. Like or comment.</strong> New likes are public. Comments are private inbox requests. Pass hides a profile for 30 days.</p><p><strong>3. Match, then chat.</strong> A mutual like opens a match. Accepting a private Dating comment also opens a conversation. Find both in Matches or Inbox.</p><div class="notice"><strong>Test a full match:</strong> use Alice in one browser and Brian in another browser or private tab. Opt in on both accounts, choose reciprocal preferences, then like each other. Both fixture accounts use the password in the README. No matches or romantic notifications are fabricated.</div></div>`);return;}
  if(action==='blocked-users'){const r=await api('/blocks');dialog('Blocked students',r.items.length?r.items.map(p=>`<div class="row between"><div><strong>${esc(p.display_name)}</strong><p>@${esc(p.username)}</p></div><button class="btn secondary small" data-action="unblock" data-id="${p.id}">Unblock</button></div>`).join(''):'<p>You haven’t blocked anyone.</p>');return;}
  if(action==='unblock'){await api('/blocks/'+id,'DELETE');button.closest('.row').remove();toast('Unblocked. Previous connections remain closed.');return;}
  if(action==='security'){const r=await api('/security/sessions');dialog('Account security',`<p>${r.items.length} active session${r.items.length===1?'':'s'}. Sessions expire after seven days.</p><button class="btn secondary" data-action="revoke-sessions">Sign out all other sessions</button><form id="password-form" class="stack">${formError()}<h3>Change password</h3><label>Current password<input name="current_password" type="password" autocomplete="current-password" required maxlength="128"></label><label>New password<input name="new_password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label><button class="btn" type="submit">Change password</button></form>`);return;}
  if(action==='revoke-sessions'){await api('/security/revoke-others','POST',{});toast('Other sessions were signed out.');$('#dialog').close();return;}
  if(action==='check-membership'){setUser(await api('/me'));if(needsApproval()){approvalPage();toast('The operator has not approved this account yet.');}else{connectEvents();go('/discover');}return;}
  if(action==='provider-refresh'){const result=await api('/verification/refresh/'+button.dataset.kind,'POST',{});setUser(await api('/me'));await verificationPage();if(!needsApproval()&&!needsStudentVerification()){connectEvents();await refreshData();}toast(result.status==='approved'?'Verification confirmed.':'Verification status: '+result.status);return;}
  if(action==='confirm-email-request'){const r=await api('/verification/email','POST',{});toast(r.message);return;}
  if(action==='pilot-feedback'){await feedbackDialog();return;}
  if(action==='operator-console'){go('/operator');return;}
  if(action==='logout'){await api('/auth/logout','POST',{});signout();return;}
  if(action==='account-dialog'){dialog(command==='delete'?'Permanently delete your account?':'Deactivate your account?',`<form id="account-form" data-command="${command}" class="stack">${formError()}<p>${command==='delete'?'This permanently deletes your profile, sessions, connections and all associated conversation history for both participants. Reports are retained with account references removed. This cannot be undone.':'Your profile becomes unavailable, dating stops, and all sessions end. Reactivation requires local operator assistance.'}</p><label>Confirm your password<input type="password" name="password" autocomplete="current-password" required maxlength="128"></label><button class="btn danger" type="submit">${command==='delete'?'Delete permanently':'Deactivate account'}</button></form>`);return;}
  if(action==='my-reports'){const r=await api('/reports/mine');dialog('Reports & support',`<div class="notice">This test build has no staffed support service. For testing, the seeded moderator account can review submitted reports through its Profile.</div>${r.items.length?r.items.map(report=>`<div class="notification"><strong>${esc(report.reason)}</strong> · ${esc(report.status)}<p>${stamp(report.created_at)} · ${esc(report.id)}</p></div>`).join(''):'<p>You have no submitted reports.</p>'}`);return;}
  if(action==='moderation'){const r=await api('/moderation/reports');dialog('Moderation queue',r.items.length?r.items.map(report=>`<article class="panel stack"><p><strong>${esc(report.target_name||'Deleted account')}</strong> · ${esc(report.reason)} · ${esc(report.status)}</p><p>${esc(report.detail||'No details supplied.')}</p>${report.message_body?`<blockquote>${esc(report.message_body)}</blockquote>`:''}<small class="muted">Report ${esc(report.id)}</small>${report.status==='open'?`<div class="row wrap"><button class="btn small" data-action="moderate" data-id="${report.id}" data-command="resolve">Resolve</button><button class="btn secondary small" data-action="moderate" data-id="${report.id}" data-command="dismiss">Dismiss</button><button class="btn danger small" data-action="suspend-dialog" data-id="${report.id}">Suspend account</button></div>`:''}</article>`).join(''):'<p>No reports to review.</p>');return;}
  if(action==='suspend-dialog'){dialog('Suspend the reported account?',`<p>The student will lose all sessions and access to CampusLink. This action is recorded in the moderation audit.</p><button class="btn danger" data-action="moderate" data-id="${esc(id)}" data-command="suspend">Suspend account</button>`);return;}
  if(action==='moderate'){await api('/moderation/reports/'+id,'POST',{action:command});$('#dialog').close();toast('Moderation action saved and audited.');return;}
 }catch(e){showError(e);if(e.status===401&&state.user)signout();}
 finally{if(button.isConnected){button.disabled=false;button.removeAttribute('aria-busy');}}
});

document.addEventListener('input',event=>{
 if(event.target.id==='message-input'){state.drafts.set(state.selected,event.target.value);resizeComposer();return;}
 if(event.target.id==='student-search'||event.target.id==='filter-program'){state.query=$('#student-search').value;state.program=$('#filter-program').value;clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadStudents(),300);}
});
function syncIntentionControl(form){
 const choice=form.elements.dating_intention,show=form.elements.show_dating_intention;
 if(!choice||!show)return;
 show.disabled=!choice.value;if(!choice.value)show.checked=false;
}
document.addEventListener('change',event=>{
 if(event.target.name==='dating_intention')syncIntentionControl(event.target.form);
 if(['filter-interest','filter-year','filter-intention'].includes(event.target.id)){state.interest=$('#filter-interest').value;state.year=Number($('#filter-year').value);state.intention=$('#filter-intention')?.value||'';loadStudents();}
});
document.addEventListener('keydown',event=>{
 if(event.target.matches('[role="tab"]')&&['ArrowRight','ArrowLeft','Home','End'].includes(event.key)){
  event.preventDefault();const tabs=$$('[role="tab"]',event.target.parentElement),current=tabs.indexOf(event.target);
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
  tabs[next].click();$('[role="tab"][aria-selected="true"]')?.focus();
 }
 if(event.target.id==='message-input'&&event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&!matchMedia('(pointer: coarse)').matches){event.preventDefault();sendMessage();}
});
document.addEventListener('submit',async event=>{
 const form=event.target;event.preventDefault();const submit=event.submitter;const data=Object.fromEntries(new FormData(form));if(submit)submit.disabled=true;$('.form-error',form)?.classList.add('hidden');
 try{
  if(form.id==='auth-form'){if(form.dataset.signup==='true')data.agreement=form.elements.agreement.checked;const r=await api(form.dataset.signup==='true'?'/auth/register':'/auth/login','POST',data);setUser(r);await refreshData();connectEvents();go(state.user.onboarding_step<6?'/onboarding':'/discover');}
  if(form.dataset.providerKind){const result=await api('/verification/start/'+form.dataset.providerKind,'POST',{consent:form.elements.consent.checked});location.assign(result.url);}
  if(form.id==='verify-email-form'){await api('/auth/verify-email','POST',{token:state.emailToken||''});delete state.emailToken;form.innerHTML='<p>Email confirmed. Sign in to that account to continue.</p><a class="btn" href="/login" data-nav>Continue</a>';}
  if(form.id==='feedback-form'){await api('/feedback','POST',data);$('#dialog').close();toast('Feedback sent to the CampusLink operator.');}
  if(form.id==='onboarding-form'){const step=Number(form.dataset.step),back=submit?.name==='back';if(step===1)data.year=Number(data.year);if(step===2)data.interests=new FormData(form).getAll('interests');if(step===3){data.friend_goal=form.elements.friend_goal.checked;data.study_goal=form.elements.study_goal.checked;}if(step===4){data.discoverable=form.elements.discoverable.checked;data.notifications_enabled=form.elements.notifications_enabled.checked;}data.onboarding_step=back?step-1:step+1;const r=await api('/me','PATCH',data);setUser(r);go(r.user.onboarding_step===6?'/discover':'/onboarding',true);}
  if(form.id==='profile-form'){data.year=Number(data.year);data.interests=new FormData(form).getAll('interests');for(const key of ['friend_goal','study_goal','discoverable','notifications_enabled'])data[key]=form.elements[key].checked;setUser(await api('/me','PATCH',data));toast('Profile and preferences saved.');renderRoute();focusPage(location.hash||'#profile-details');}
  if(form.id==='dating-eligibility-form'){data.adult_test_agreement=form.elements.adult_test_agreement.checked;setUser(await api('/dating/test-eligibility','POST',data));dialog('Your Dating preferences',datingSettingsForm(state.user,{icon,esc,check,formError,demoAccounts:!isStaging()}));}
  if(form.id==='dating-form'){data.dating_enabled=form.elements.dating_enabled.checked;data.show_dating_intention=form.elements.show_dating_intention.checked;data.dating_genders=new FormData(form).getAll('dating_genders');data.dating_min=Number(data.dating_min);data.dating_max=Number(data.dating_max);setUser(await api('/me','PATCH',data));state.mode='dating';state.query='';state.program='';state.interest='';state.year=0;state.intention='';$('#dialog').close();toast(state.user.dating_enabled?'Dating is on. Explore your campus connections.':'Dating is off. Your dating chats are closed.');await refreshData();go('/discover');}
  if(form.id==='edit-post-form'){await api('/posts/'+form.dataset.id,'PATCH',{body:data.body});$('#dialog').close();await feedManager?.refresh();toast('Post updated.');}
  if(form.id==='private-comment-form'){
   const uid=form.dataset.target,existing=state.chats.find(c=>c.profile.id===uid);
   let rid=existing?.id;
   if(!rid){const r=await api('/message-requests','POST',{target_id:uid,body:data.body,client_id:form.dataset.clientId,kind:form.dataset.kind,post_id:form.dataset.postId?Number(form.dataset.postId):null});rid=r.conversation_id;}
   if(rid)await api(`/chats/${rid}/messages`,'POST',{body:data.body,client_id:form.dataset.clientId});
   $('#dialog').close();await refreshData();toast(rid?'Comment sent.':'Private comment sent to their inbox requests.');if(rid){state.selected=rid;go('/chats');}
  }
  if(form.id==='composer')await sendMessage();
  if(form.id==='report-form'){data.target_id=form.dataset.target;const messageId=form.elements.message_id?.value;if(messageId)data.message_id=Number(messageId);else delete data.message_id;const r=await api('/reports','POST',data);dialog('Report received.',`<p>Your report is saved for authorized moderator review.</p><small class="muted">Reference: ${esc(r.id)}</small>`);}
  if(form.id==='password-form'){await api('/security/password','POST',data);$('#dialog').close();toast('Password changed. Other sessions were signed out.');}
  if(form.id==='account-form'){await api('/account/'+form.dataset.command,'POST',data);$('#dialog').close();signout();toast('Your account was '+(form.dataset.command==='delete'?'deleted.':'deactivated.'));}
  if(form.id==='recover-form'){const r=await api('/auth/recover','POST',data);form.innerHTML=`<p>${esc(r.message)}</p><a href="/login" data-nav>Back to sign in</a>`;}
  if(form.id==='reset-form'){data.token=state.resetToken||'';await api('/auth/reset-password','POST',data);delete state.resetToken;signout();toast('Password reset. Sign in with your new password.');}
 }catch(e){showError(e,form);}
 finally{if(submit?.isConnected)submit.disabled=false;}
});

document.addEventListener('error',event=>{if(event.target instanceof HTMLImageElement&&event.target.hasAttribute('data-profile-photo')){event.target.classList.add('photo-unavailable');}},true);
window.addEventListener('popstate',()=>{renderRoute();focusPage();if(state.user&&['/matches','/connections'].includes(path()))refreshData();});
window.addEventListener('online',()=>{if(state.user){refreshData();if(path()==='/discover')loadStudents();}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.user){refreshData();if(path()==='/discover')loadStudents();}});
setInterval(()=>{if(state.user&&!document.hidden){refreshData();if(!state.live&&path()==='/discover')loadStudents();}},15000);

async function boot(){
 try{state.catalog=await api('/catalog');setIntentionCatalog(state.catalog.dating_intentions);try{setUser(await api('/me'));await refreshData();connectEvents();}catch(e){if(e.status!==401)throw e;}renderRoute();focusPage();}
 catch(e){app.innerHTML=`<main id="main" class="legal">${publicHeader()}${empty('compass','CampusLink is unavailable.',e.message,'<a class="btn" href="/">Try again</a>')}</main>`;}
}
boot();
