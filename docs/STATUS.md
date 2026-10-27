# Implementation and validation status

Use the [development checklist](../CHECKLIST.md) to track the next feature phases and their acceptance checks.

This is a local functional MVP, not a finished public product. Visual quality is not the acceptance criterion. The test target is students discovering, connecting, and chatting with real persisted state and server-side permissions.

**Current scope:** local development and hosted preview. On 27 October the owner authorized launch preparation and confirmed that membership/email approval belongs to them. The supporting operations and verification code is implemented; actual hosted configuration, provider coverage, mailbox receipt, privacy review, physical Android acceptance and a consenting-student pilot remain incomplete. Earlier deferred-scope statements below are historical.

| Area | Local implementation |
| --- | --- |
| Landing and navigation | Direct landing copy; Feed, Discover, Matches, Inbox, Profile; dating matches by default; secondary friendship/study views with URL/history support; editor shortcuts, route focus and retry states; draft policies and independent branding |
| Appearance | Optional short animations, confirmed-like feedback and real loading placeholders; reduced-motion support; Light/dark header toggle across public pages and the app; device preference by default, remembered browser choice, keyboard access, synchronized tabs and retained form/message drafts |
| Accounts | Registration, login/logout, normalized usernames, salted passwords, cookie sessions, CSRF, password change, revoke-other-sessions |
| Recovery | Expiring single-use reset links and SMTP transport implemented; delivery unavailable until configured |
| Student verification | Explicitly unavailable; modular local adapter; no fixture claims verified status |
| Onboarding | Six persisted steps with back navigation; academic info, normalized interests, goals, privacy |
| Profiles | Edit name, username, bio, academic fields, interests, goals, discoverability, notifications; optional four-photo gallery; up to three optional personality answers with question selection, editing, reordering and removal |
| Discovery | Deterministic explanations, campus fallbacks, category goals, search/filter/debounce/pagination, cooldowns and privacy exclusions; compact photo/name/program cards opening the full profile |
| Friendship and study | Send, receive, accept, decline, cancel, remove, duplicate prevention, concurrent crossing requests |
| Dating | First Discover view with visible setup, self-declared 18+ access for created local test accounts and optional fixture switching; explicit opt-in, reciprocal preferences, public profile likes, Pass in options, mutual match/chat or accepted private Dating request, My matches, unmatch and disable; optional intentions with separate sharing control, contextual profile privacy and displayed-intention filter |
| Chats | Persisted text, live updates, previews, Sent/Delivered/Read receipts, private message requests, timestamps, unread counts, older history, reconnect, idempotent retry; optional dating-only conversation starters from shared interests/visible answers with safe draft selection and campus fallback |
| Safety | Both-direction blocks, private profile/message reports, moderator queue, resolve/dismiss/suspend, audit trail |
| Account lifecycle | Password-confirmed deactivation and deletion, cascade/anonymization policies |

## 25 October: public reactions, private comments and Feed

New profile and post likes are public, with an authorized liker list. Earlier private Dating interests are retained separately and never migrated into public reactions. Profile cards use Like, Comment and Inbox; Pass is in the options menu. Private comments enter an existing conversation or create a recipient-controlled message request. No public comment body or request body enters Feed or liker responses. Accepting a Dating request requires continued reciprocal adult eligibility. New initial requests are limited to one per sender/recipient, including after decline.

Feed persists text and optional processed photo posts, idempotent uploads/publishing, author caption edits, deletion and public reactions. Campus membership, visibility and blocks apply on list, reaction and direct image reads. Drafts are scoped to the current signed-in browser tab. No music integration is present. Sent/Delivered/Read use persisted acknowledgement cursors; fetching history alone does not create an API acknowledgement. The browser marks Read only for a visible conversation at its latest messages. The repeated ZUT/campus slogans, leaf icon and normal Live updates label are removed.

All 126 API tests passed (25 October), and all ten browser scripts reached successful results during this update. The full combined journey and conversation suite were rerun after receipt/quota corrections. See [validation](VALIDATION.md) for exact runs and their scope. Physical Android acceptance remains open.

## Conversation and discovery refinement

The current interface keeps discovery details inside photo-open profiles and gives phone conversations more space above the main navigation. Messages are grouped, starters default to collapsed, touch Return creates a newline, the composer grows with its draft, older-history reading keeps its position, and a New messages shortcut returns to the latest. Chat options include profile access, Unmatch/End connection and About this chat. Report/Block are behind the optional, collapsed Safety & support section below the composer; a report can include a chosen received message, and blocking still requires confirmation. Photos and private Dating information retain their existing authorization rules. No music-player integration or verified badges were added.

The [UX review](UX_REVIEW.md) records the reference, official app comparison sources and policy differences. The new conversation browser checks cover details access, grouped bubbles, drafts, light/dark text contrast, mobile viewport changes, history/scrolling, reporting and unmatching. Physical-device acceptance remains pending.

## Motion and interaction — 25 October 2026

A small native CSS/module layer provides button feedback, confirmed-like hearts, profile/post entrances, dialog/backdrop transitions and loading placeholders. New message identities are tracked within the current message region so initial history, pagination, saved acknowledgements and read-receipt refreshes do not replay older content. Message/post persistence and navigation do not wait for animations. Reduced-motion preference disables animation and transitions while retaining usable controls and static loading feedback. Touch layouts avoid hover lifts; no new dependencies or backend/schema changes were added. Post likes preserve keyboard focus after replacement or failure without stealing it from another selected control.

The social and conversation suites passed with motion integrated, and final focused checks passed for reduced motion, failed/saved feedback, focus/drafts, message identity, 320px/desktop layouts and dialog Escape. Details are recorded in [validation](VALIDATION.md). These browser checks do not replace physical Android acceptance.

## Restricted hosted test preparation — 25 October 2026

The code supports local mode and access-controlled staging. Staging requires a canonical HTTPS origin, separate persistent storage and a random tester credential. It gates every route including assets, uploads, photos and live events, with a minimal public health exception. Individual app accounts, Secure/HttpOnly cookies, CSRF, eligibility and relationship rules remain enforced. Demo seeding and supplied fixture databases are refused; the hosted interface hides fixture login helpers. No public/student eligibility provider is claimed, and production modes still refuse startup.

The Render Blueprint, one-worker launcher, Python version and consistent SQLite backup command are prepared in the source tree. The initial restricted TLS browser journey passed six groups using temporary certificates/accounts/servers, including live SSE, offline retry, forced restart and database/image backups. The initial 168 API tests passed, including 42 deployment/backup cases, and the local social browser regression passed all five groups. Exact results and the subsequent tester-login regression checks are recorded in [validation](VALIDATION.md).

On 27 October the user requested direct website access. The current source removes shared tester credentials, the access form/cookies and browser-gate redirects. Visitors open the website and use their individual CampusLink accounts. Canonical HTTPS, Secure/HttpOnly sessions, CSRF, private-data authorization and fixture refusal remain. Old tester settings are ignored and old access-page bookmarks return to the landing page. The direct-access version (`739c3ff`) is deployed at <https://campuslink-staging.onrender.com>; the user confirmed it works. Anonymous landing/health checks returned 200 without a native challenge, while `/api/me` still required individual sign-in. The complete real Android journey, hosted persistence and restore acceptance remain pending. See [DEPLOYMENT.md](DEPLOYMENT.md) and [validation](VALIDATION.md).

## Automated evidence

The Stage 6 combined journey passed all nine groups on 23 October 2026, starting with an empty temporary database and registering two new accounts through the UI. The test uses separate 390px and 412px Chromium sessions on a plain HTTP LAN origin. **Physical two-phone acceptance remains open** in [the device test guide](PHONE_TEST.md); no physical-device or student acceptance result is claimed.

`tests/journey_browser.py` covers the complete onboarding/photo/prompt/adult-test/Dating setup, cross-program discovery, one-sided and mutual likes, duplicate-safe matching, editable starters, live bidirectional messages, offline retry, a lost acknowledgement after a real committed POST, forced server-crash recovery and persisted records. Unmatch, Dating deactivation and blocking are exercised through the UI and verified through direct reads/sends, photo/profile URLs and starter access. Unblocking or re-enabling Dating alone cannot restore consent. That historical validation phase preceded the schema-5 social update. `requests` is now explicitly listed in development requirements so the existing browser scripts also run inside the documented virtual environment.

`tests/test_flows.py` exercises the real application routes with isolated databases and independent sessions. It covers authentication/CSRF, onboarding persistence, public/private projections, eligibility filters, request state transitions, simultaneous crossing requests, both messaging categories, conversation ID attacks, unread cursors, bidirectional block revocation, concurrent duplicate sends, history pagination/catch-up, private and mutual dating behavior, adult/preferences gates, unmatching, moderation roles/audits, account lifecycle, rate limits, server recreation, and password recovery expiry/reuse/session revocation.

`tests/browser_smoke.py` exercises real HTTP and SSE in Chromium with two independent authenticated clients. It captures screenshots and checks live bidirectional delivery, safe text rendering, draft preservation, offline failed-send retry, a forced server restart, persistence, block revocation in both clients, and mobile navigation/overflow. Results are recorded in `docs/VALIDATION.md` after execution.

`tests/dating_browser.py` exercises Dating in separate phone-sized and desktop browsers: visible entry, explicit activation, profile discovery, Pass, public one-sided likes, mutual match, bidirectional dating chat, unmatch, disabling Dating, fixture switching, and Alice matching and messaging with a newly created account after explicit local 18+ setup.

`tests/test_photos.py` covers image decoding, resizing and metadata removal, image/body limits, gallery ownership, concurrent/idempotent uploads, visibility and block rules, dating-only eligibility, deletion and schema upgrades. `tests/photo_browser.py` exercises the gallery and image access in independent phone-sized and desktop browsers, including offline retry, crash persistence, cross-program dating, live chat avatars and blocking.

`tests/test_prompts.py` covers the question catalog, optional empty profiles, editing/order/removal, Unicode and length validation, atomic retry/concurrent saves, owner scope, CSRF, profile/discovery/connection access rules, dating eligibility, deletion/deactivation and the version-2 database upgrade. `tests/prompt_browser.py` checks 390px editing, failed-save retry, drafts across profile/photo changes, server-crash persistence, escaped answers in discovery/full profiles, mutual dating and chat, and blocking.

`tests/test_intentions.py` covers optional/private defaults, all labels, editing/hiding/removal, idempotent saves and restart persistence, hidden/unset filter behavior, general/friend/study projection exclusions, forged Dating contexts, matching and consent revocation, eligibility/blocks/institution scope, validation rollback, CSRF/ownership, account lifecycle and the version-3 database upgrade. `tests/intention_browser.py` checks these settings and filters on a 390px viewport and a separate desktop browser, including cross-program matching/chat, offline save retry, crash persistence and direct access denial after blocking.

`tests/test_starters.py` covers both participants' suggestions, no-overlap fallback, bounded and current profile answers, private-data exclusions, read-only behavior, authentication/membership, pending and non-dating connections, revoked consent/eligibility, accepted hidden profiles, and persistence/idempotent sending of edited starter text. `tests/starter_browser.py` exercises actual mutual matching, keyboard selection without sending, editing, draft preservation, source updates, failed-send retry, independent suggestion-load retry, restart persistence and block revocation.

`tests/navigation_browser.py` checks five primary destinations, dating defaults, secondary friendship/study routes, request badges, Back/Forward, keyboard tabs and route/dialog focus, photo/prompt/visibility editing through shortcuts, real private likes and mutual dating chat, independent request failures, cached-list warnings, retry/reconnect with a retained message draft, initial loading feedback, selected text contrast, mobile touch targets and layout.

## Launch preparation — 27 October 2026

Schema 6 adds trusted operator roles/audits, membership approval, email confirmation,
durable mail jobs, external eligibility records, maintenance history and private pilot
feedback. Hosted approval defaults to `auto`: the first trusted operator grant activates
enforcement permanently unless the operator explicitly changes configuration. Local
preview keeps approval off by default. Pending/declined members retain their own
profile/security/support/deletion access but cannot discover or chat. Approval never
silently confirms email, age or external student status.

Email uses certificate-verified SMTP TLS and durable, purpose-bound, single-use links.
A separate server secret reconstructs tokens without storing plaintext links in SQLite.
Retries survive restarts; test transport acceptance is distinct from actual mailbox
receipt. Live SMTP is not configured by the support email alone.

The optional SheerID adapter separates student and 18+ checks, binds them to an
account and institution, rejects weak/test results, authenticates callbacks and
rechecks canonical provider records. No live provider account exists; actual Zambian
university coverage, program fields and live journeys remain unconfirmed. Preview
eligibility is still explicitly unverified, and public/production mode remains disabled.

Hosted maintenance schedules consistent backups with three-copy retention and
isolated restore checks; the owner can download a checked copy after confirming their
password. Cleanup removes only expired temporary records. Request IDs and bounded
aggregate metrics support investigation. External uptime alerts, a protected offsite
copy and a real hosted restore exercise remain the operator's setup tasks.

The owner approval/email/feedback/backup TLS browser exercise passed five groups.
A bounded TLS exercise used 16 accounts, eight mutual matches, 16 simultaneous SSE
streams, 96 saved messages and 96 idempotent retries with zero 5xx responses; sessions,
receipts and history survived a forced restart. This is evidence for that isolated
pilot-sized workload, not a campus capacity or Render performance claim. See
[validation](VALIDATION.md) for final counts and scope.

## Remaining real-world acceptance

- Deploy this update and bootstrap the actual operator account on Render.
- Configure and observe real confirmation/recovery delivery.
- Establish the actual institution and live student/18+ verification arrangement.
- Supply legal operator identity, complete applicable privacy review and approve
  retention, appeals, support staffing and incident procedures.
- Confirm offsite recovery, external alerts and hosted storage/redeploy persistence.
- Finish the two actual Android-phone journey, including mobile data and native keyboards.
- Run consenting adult student trials and fix/retest their findings.

HEIC, animated images, cropping and chat image attachments remain outside this phase.
The supplied specification ends during section 14.4; omitted content is not assumed
implemented. These limitations are tracked in the [checklist](../CHECKLIST.md),
[operator runbook](OPERATIONS.md) and [pilot plan](PILOT.md).
