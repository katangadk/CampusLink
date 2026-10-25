# Validation record — updated 25 October 2026

## Outcome

The local discovery → connection → conversation journey passes automated API and real-browser checks. This is evidence for the local build, not a claim of public readiness, production reliability, or successful student acceptance testing.

## Restricted hosted test preparation — 25 October 2026

The complete API suite passed **168 tests in 69.43 seconds**, with the same upstream TestClient deprecation warning. This includes 42 deployment/backup cases: fail-closed mode/settings validation, host/HTTPS checks, gate protection across pages/assets/APIs/photos/SSE, malformed credentials, failed-attempt limits, independent application authentication/CSRF, Secure cookies, trusted/untrusted proxy headers, fixture/seed refusal, persistence and backup/restore. Public/production modes remain disabled and schema version 5 is unchanged.

`python -m tests.staging_browser` passed all **6 groups** using two fresh accounts, separate 390px/412px Chromium sessions and a temporary real TLS server. The browser accepts only a temporary QA certificate configuration; HTTP checks trust that generated certificate. The run verified gated pages/assets/APIs/photos/SSE, a minimal public health response, no demo login helpers, complete onboarding/photos/prompts and adult-test/Dating opt-in, cross-program matching, bidirectional SSE messages, draft preservation, one-copy offline retry, forced server crash/restart, secure-session/image/history persistence, an online SQLite backup and both-direction blocking. It created only two temporary users and five saved messages. `artifacts/staging-results.json` explicitly records `real_hosted_service: false` and `physical_devices: false`.

`python -m tests.social_browser` passed all **5 groups** for local-mode regression. JavaScript/Python syntax and documentation links passed. The Render YAML was parsed and checked for one Python service, one instance, persistent `/var/data` storage, restricted staging mode, a generated secret and disabled automatic deployments. The provider's actual deployment validation still happens when the service is created. No new runtime dependency was required.

The 42-case deployment test run also passed separately. Source is prepared for the user-provided `katangadk/CampusLink` repository. The release checkout excludes local databases/images, secrets, backups, generated test artifacts, private workspace metadata and the pasted development brief. Existing local accounts and messages were not migrated to a host.

**No actual Render service, managed public certificate, paid resource, real recovery delivery or physical-phone hosted result is claimed.** Account connection, compute/storage estimate review, service creation and acceptance on its actual URL remain pending in [DEPLOYMENT.md](DEPLOYMENT.md) and [PHONE_TEST.md](PHONE_TEST.md).

## Motion and interaction — 25 October 2026

This earlier update changed frontend styles/modules and feedback only. The 126-case API run preceded that motion work; the later staging checks are recorded above.

- `python -m tests.social_browser` — all 5 groups passed with motion integrated: public likes, private requests/recovery, Sent/Delivered/Read, photo-post retry and author edits/deletion.
- `python -m tests.conversation_browser` — all 5 groups passed with motion integrated: profile access, grouping, phone keyboard/viewport, older-history position and optional safety actions.
- Final focused checks used a temporary script/database/server and passed all 4 groups after correcting post-like focus restoration: placeholders during actual latency; no heart/success feedback after a failed like; draft and keyboard focus preservation; reduced-motion behavior with functioning likes, themes and genuine matching; dialog focus/Escape; no animation for initial history; one entrance per fresh incoming/outgoing message without replay on saved/Read updates; 320px and 1280px layouts; no uncaught JavaScript/CSP errors. Pending-to-saved messages use the same sender/client key. No permanent implementation-mirroring animation test suite was added.
- All JavaScript modules passed syntax checks. The PC and Wi-Fi server on port 8001 serve the exact updated index, app/feed modules and new motion CSS/module. No backend restart was required. No real account/post/message records were used by these checks.

Evidence: `artifacts/motion-results.json` (4 groups; physical devices false), `motion-loading-dark-mobile.png`, `motion-reduced-mobile.png` and `motion-chat-mobile.png`. The final focus correction captures focus before disabling the Like button and restores it only if the user has not focused a different control. Reduced-motion mode disables motion without waiting for animation events; all request/persistence behavior stays immediate. Loading effects stop when their pending content is replaced, and nothing claims delivery/read success from an animation.

Physical Android feel, native keyboard and background/resume checks remain pending in [PHONE_TEST.md](PHONE_TEST.md).

## Public likes, private comments, posts and receipts — 25 October 2026

The new behavior passed isolated API and Chromium checks. New profile/post likes expose authorized liker identities; private comment bodies appear only in a participant’s request list or accepted conversation. New public reactions do not backfill earlier private Dating likes. Music is excluded. The leaf icon, repeated campus headings and normal Live updates label are removed.

| Browser command | Result during this update |
| --- | --- |
| `python -m tests.social_browser` | All 5 groups: public identities/card actions; private request acceptance and failed-list recovery; actual Sent → Delivered → Read; photo-post lost-acknowledgement retry; private post comments and author edit/delete. |
| `python -m tests.conversation_browser` | All 5 groups: compact/full profiles, grouping, keyboard/viewport, history, optional reporting/unmatch/block. Rerun after receipt optimization. |
| `python -m tests.journey_browser` | All 9 groups: fresh registrations/onboarding, discovery, matching, live messages, retry/lost acknowledgements, forced crash/restart, unmatch, deactivation, block/unblock. Rerun after quota correction. |
| `python -m tests.navigation_browser` | All 5 groups with Feed, Discover, Matches, Inbox, Profile; secondary routes and retries remain usable. |
| `python -m tests.browser_smoke` | All 7 groups. |
| `python -m tests.dating_browser` | All 7 groups; Pass is inside profile options. |
| `python -m tests.photo_browser` | All 6 groups. |
| `python -m tests.prompt_browser` | All 6 groups. |
| `python -m tests.intention_browser` | All 6 groups. |
| `python -m tests.starter_browser` | All 5 groups. |

The combined journey initially exposed the old 600-requests-per-IP budget when two clients shared a network and rapidly exercised the entire product. Duplicate receipt acknowledgements were removed: incoming messages at the visible conversation bottom use one Read acknowledgement, which also marks delivery. Inbox previews acknowledge receipt without Read. The general budget is now 600/minute per signed-in account (600/minute per IP for anonymous requests), with a 6,000/minute shared-IP ceiling. Existing action-specific limits remain. API tests verify one exhausted account cannot consume another account’s budget on the same Wi-Fi; the complete journey then passed without 429 errors. This is functional evidence, not a load test.

Evidence: `artifacts/social-results.json`, `artifacts/journey-results.json`, `artifacts/conversation-results.json`, `campus-feed-light.png`, `campus-feed-dark.png`, `private-inbox-request-dark.png`, and `chat-read-receipts-dark.png`. The new social run uses separate 390×844 dark and 412×915 light Chromium views. The current combined run uses loopback HTTP; the 23 October plain-HTTP LAN journey below is historical. Screenshots are supplemental to API/state assertions.

The existing port-8001 server was restarted with a local SQLite backup and its previous configuration. PC and current Wi-Fi origin `http://10.106.85.176:8001` return 200 for the updated UI/assets; unauthenticated Feed/requests return 401. The served app module matches the workspace source. Existing data counts were unchanged: 12 users, 14 messages and 1 profile photo. No QA posts, public likes or private requests were inserted into that database. Test databases/servers were temporary and cleaned up.

Both physical devices are Android, but the updated real-phone keyboard, background/resume, receipts and post/request flows are still pending in [PHONE_TEST.md](PHONE_TEST.md). This update does not close Stage 6.

## API and database checks

Command: `python3 -m pytest -q`

**Latest result: 168 passed in 69.43 seconds (25 October 2026), with one upstream TestClient deprecation warning.** Forty-two deployment/backup cases are described above; the earlier 126-case application result remains historical evidence. The 16 social/receipt cases cover public reactions, legacy-private separation, private requests/recipient decisions, concurrent acceptance, posted-photo validation and privacy, persistence, safe retry, edit/delete, campus/block rules, receipt acknowledgements, CSRF, schema-4 upgrades and independent quotas for accounts sharing Wi-Fi. Tests run against isolated temporary SQLite databases and independent authenticated clients. No external email or institutional service was contacted. The photo phase adds 21 cases covering supported image formats, EXIF orientation, metadata stripping, compression, persistence, gallery ordering, concurrent/idempotent uploads, ownership, visibility, dating eligibility, blocking, account deletion/deactivation, invalid/animated/oversized images, streamed-body limits, CSRF and the version-1 database upgrade. The prompt phase adds 25 cases covering the catalog, optional answers, editing/order/removal, restart persistence, safe plain-text/Unicode limits, invalid replacement rollback, CSRF, owner scope, atomic concurrent saves, existing visibility/eligibility/block rules, account lifecycle and upgrading a version-2 database without losing photos, users or sessions. The intention phase adds 19 cases covering private/unset defaults, all labels, editing/hiding/removal, retries/restarts, default and specific filters, general/friend/study exclusions, forged Dating contexts, consent and eligibility rules, validation rollback, CSRF/ownership, account lifecycle and preserving photos, prompts, users and sessions through a version-3 upgrade. The starter phase adds 15 cases covering shared interests and visible answers, no-overlap fallback, bounded/current plain text, private-data exclusions, reads without message/notification/cursor changes, authentication/membership, non-dating and pending connections, revoked consent/eligibility, accepted hidden profiles, and persistent duplicate-safe sending of edited starter text.

Covered: registration/login, CSRF and origin protection, onboarding persistence, safe profile projections, discovery eligibility and search, friendship/study lifecycle, simultaneous requests, guessed conversation IDs, unread counts, both-direction blocking, concurrent retry deduplication, history pagination, dating privacy and reciprocal eligibility, unmatching/disable, moderator roles and audits, password change and session revocation, deletion/deactivation, persisted rate limits, restart persistence, and recovery token expiry, one-time use, generic responses and session revocation.

## Chromium journey checks

Command: `python3 -m tests.browser_smoke`

**Result: all seven browser check groups passed.** The script starts a real local HTTP server with an isolated persistent database and uses two separate Chromium sessions:

1. Discover → request → accept → bidirectional live chat. A recipient draft survives incoming updates. Script-looking message text remains literal text.
2. Offline failure retains the message and retry key. Retrying after reconnect creates one message.
3. A forced server crash/restart preserves records and sessions; the event stream reconnects and messages continue. Refreshing the browser restores history.
4. Blocking through the UI closes the conversation in both clients.
5. Profile edits survive reload. A submitted report reaches the authorized moderator queue; resolution is visible to the reporter.
6. Registration completes six onboarding steps, preserving academic data through Back navigation. A new account cannot access dating without established adult eligibility.
7. A 390px mobile viewport has visible bottom navigation and no horizontal overflow. No uncaught JavaScript errors or CSP violations were detected.

Screenshots are generated in ignored `artifacts/`: `landing-desktop.png`, `discovery-desktop.png`, `chat-desktop.png`, and `discovery-mobile.png`. They illustrate the tested interface; passing is determined by functional assertions.

## Syntax checks

- `node --check web/app.js` — passed.
- `python3 -m compileall -q campuslink tests` — passed.
- `node --check web/dating.js`, `node --check web/photos.js`, `node --check web/prompts.js`, `node --check web/starters.js` and `node --check web/navigation.js` — passed.
- `node tests/message_id.mjs` — passed.

## Phase 1 — profile photos

Command: `python3 -m tests.photo_browser`

**Result: all six photo browser check groups passed.** The test uses synthetic labelled image fixtures, isolated databases, and separate 390 × 844 phone-sized and desktop browsers:

1. Upload preview, main selection, gallery reordering and replacement work without discarding unsaved profile text.
2. Offline upload failure retains the preview and retry key; retry saves once. An SVG disguised as PNG is rejected. The four-photo limit and layout fit the phone viewport.
3. A real server crash/restart and browser refresh preserve gallery records, processed image bytes and the session.
4. Students in different academic programs see photos in Dating discovery, full profile galleries, the photo viewer, matches and chat after mutual matching.
5. Changing the main photo updates the other participant's chat avatar without losing their draft. Blocking closes the chat and denies a direct image URL request.
6. Removing the entire gallery removes its stored image records and restores initials.

The same browser journey also passed against the project's `.venv` server (Starlette 1.9.0), using `CAMPUSLINK_TEST_PYTHON=.venv/bin/python python3 -m tests.photo_browser`. The system-server run used Starlette 1.3.1. Pillow 12.3.0 is installed and pinned in the project requirements. The general registration/discovery/chat browser regression passed after adding the photo UI and binary request handling.

Screenshots: `artifacts/photo-gallery-mobile.png` and `artifacts/photo-profile-mobile.png`. No actual student photos were used. The current local server's health, profile page and photo module returned 200 over the LAN, and an unauthenticated upload returned 401. These are local checks; two-physical-phone acceptance remains a later checklist item.

## Phase 2 — personality prompts

Command: `CAMPUSLINK_TEST_PYTHON=.venv/bin/python python3 -m tests.prompt_browser`

**Result: all six prompt browser check groups passed**, against the actual project's virtual-environment server, in independent 390 × 844 and desktop Chromium sessions:

1. Optional editing supports question changes, retained keyboard focus, the three-answer cap, empty/long-input handling, reordering, removal and saving. Saving answers preserves unsaved profile text; the phone layout has no horizontal overflow.
2. Saving profile text and uploading a photo preserve the prompt draft. Prompt saves preserve the photo. Answers survive in-app navigation without forcing an extra onboarding step.
3. An offline save offers retry and retains the draft. Retrying saves a single ordered set. A forced server crash/restart and browser reload retain saved answers and the authenticated session.
4. Friends and cross-program Dating discovery show the first answer, and the full profile shows all answers in order. HTML-looking input remains literal text. A real two-sided like creates a mutual match and opens chat.
5. Updating an answer preserves the recipient's chat draft. Clicking the chat header name opens fresh full-profile answers. Actual messages flow in both directions; blocking revokes direct profile access.
6. Removing all answers persists an optional empty profile after reload. No uncaught JavaScript errors or CSP violations were detected.

The existing seven-group registration/discovery/connection/live-chat browser regression also passed after integrating prompt editing and rendering. Screenshots: `artifacts/prompt-editor-mobile.png` and `artifacts/prompt-profile-desktop.png`. Browser input is synthetic test text; no actual student answers are used. Two physical phones remain a separate later acceptance item.

The existing LAN server was restarted with its original database. Health, the profile page, and the prompt module returned 200. The live catalog returned all eight questions and the three-answer/280-character limits. An unauthenticated prompt save returned 401, and the database retained its accounts/photos while upgrading to schema version 3.

## Phase 3 — dating intentions

Command: `CAMPUSLINK_TEST_PYTHON=.venv/bin/python python3 -m tests.intention_browser`

**Result: all six intention browser check groups passed**, against the project's virtual-environment server with independent 390 × 844 and desktop Chromium sessions:

1. Optional setup defaults to unset with sharing off. All three catalog labels are available, and a cross-program student with no intention remains discoverable.
2. A specific filter excludes hidden/unset choices. Clear filters and discovery-category changes reset it. Friendship/study views omit the control and label, and direct reads cannot recover a hidden choice.
3. Displayed labels agree between filters, Dating cards and full profiles opened from Dating/matches/chat. General, friend and study API projections omit the information. Different intentions still allow genuine mutual matching.
4. Hiding retains the private choice; editing updates fresh authorized profile reads. Chat drafts survive the change, and real messages travel in both directions.
5. Removing clears the choice and disables sharing. An offline settings failure retains the form for retry. A forced server crash/restart preserves intentions, sessions and saved chat history.
6. Blocking revokes Dating profile access in both directions, including direct requests with Dating context. The phone layout has no horizontal overflow, and no uncaught JavaScript or CSP errors occur.

The existing seven-group registration/discovery/connection/live-chat regression passed after the context and filter changes. Syntax checks and the HTTP-compatible message-ID check also passed. Screenshots: `artifacts/intention-settings-mobile.png` and `artifacts/intention-profile-desktop.png`. Data belongs to synthetic local fixtures; two-physical-phone acceptance remains in the later checklist phase.

The existing LAN server was restarted with its original database. Health, the profile page, and the Dating module returned 200 over the Wi-Fi address. The live catalog returned the three intended choices and labels; a signed-out intention edit returned 401. The live database is at schema version 4.

## Phase 4 — conversation starters (23 October 2026)

Command: `CAMPUSLINK_TEST_PYTHON=.venv/bin/python python3 -m tests.starter_browser`

**Result: all five starter browser check groups passed.** The 390px layout also verifies that Send stays above the fixed phone navigation after a small chat-height correction.

The browser journey uses independent 390 × 844 and desktop Chromium sessions against the project's virtual-environment server and an isolated database:

1. Students in different programs create a real mutual match with no shared interests or prompt answers. Both receive campus questions. Keyboard selection fills a draft without creating any message; editing and explicit Send exchange real messages in both directions. Selecting another question preserves an existing draft.
2. Shared-interest and visible-answer suggestions appear after profile edits. HTML-looking answers remain literal text. Fresh prompt answers update suggestions while preserving the existing message draft.
3. An edited starter survives an offline failed send. Suggestion clicks cannot replace the pending message. Reconnecting and retrying saves exactly one copy through the normal message endpoint.
4. Hiding is remembered during in-app navigation. Suggestions can fail and retry independently of the composer, preserving a typed draft and leaving Send available.
5. After a forced server crash/restart, saved messages and sessions remain, suggestions load afresh, and the composer is not pre-filled or sent automatically. Blocking removes the panel and denies direct starter reads in both directions. No uncaught JavaScript or CSP errors are detected.

The existing seven-group registration/discovery/connection/live-chat regression passed with the starter integration. Screenshots: `artifacts/starters-fallback-mobile.png` and `artifacts/starters-profile-mobile.png`. These tests use synthetic profiles and answers; two physical phones remain a later acceptance item. Schema version remains 4 because starters require no new persisted records.

The existing LAN instance was restarted with its original database. Health, Chats and the starter module returned 200 at the current Wi-Fi address; a signed-out starter request returned 401. The phone address changed with the Wi-Fi network, so use the computer's current address as described in README.

## Phase 5 — dating-first navigation (23 October 2026)

Command: `CAMPUSLINK_TEST_PYTHON=.venv/bin/python python3 -m tests.navigation_browser`

**Result: all five navigation browser check groups passed** in separate 390 × 844 and desktop Chromium sessions:

1. The main navigation contains exactly Discover, Matches, Chats and Profile. Discover and Matches default to Dating. Secondary friendship/study views have working URLs, discovery links and Back/Forward behavior. Arrow-key tabs and route focus stay synchronized with the selected view.
2. A real friendship request appears only in the secondary request area with its own badge. Accepting it does not create a dating match. A one-sided dating like remains private; two-sided likes create a mutual match that opens actual bidirectional dating chat through Matches.
3. Profile shortcuts reach photos, prompts, preferences and visibility without discarding drafts. Uploads and edits persist. Hash links focus the intended editor after reload; Escape from Dating preferences restores focus to its opener.
4. Blocking individual API requests produces explicit initial errors or cached-list warnings. Other successfully loaded lists remain usable. Retry restores Matches, Chats and discovery. Manual history retry and automatic reconnect both retain the typed message draft and recover the composer with its dating starters.
5. A throttled initial load shows status feedback. Main navigation and profile shortcut targets meet the tested touch sizes; the selected navigation text and heading copy meet 4.5:1 contrast. Keyboard focus is visible, phone navigation stays in the viewport, and there is no horizontal overflow, uncaught JavaScript error or CSP violation.

The existing seven-group request/accept/chat browser regression and the complete Dating browser journey passed with their navigation selectors updated. The Dating regression still includes Alice matching and messaging with a created adult test account. API routes and schema version 4 are unchanged; all 110 API tests passed. Screenshots: `artifacts/matches-navigation-mobile.png` and `artifacts/profile-shortcuts-mobile.png`.

The current LAN instance serves Matches, the secondary study view and the navigation module with 200 responses. Its app module includes the four-destination navigation and profile shortcuts; a signed-out connection request returns 401. This frontend phase preserves the existing database and API behavior.

These are focused browser checks, not a full accessibility audit or two-physical-phone acceptance. The combined updated journey is recorded below.

## Phase 6 — combined fresh-account journey (23 October 2026)

Command: `CAMPUSLINK_JOURNEY_HOST=172.18.3.76 .venv/bin/python -m tests.journey_browser`

**Result: all nine combined journey groups passed.** The actual local server used a temporary database with no seed accounts; the only two users were registered through the interface. Independent Chromium sessions used 390 × 844 and 412 × 915 phone viewports with touch emulation. The origin was plain HTTP on the computer's Wi-Fi address (`isSecureContext=false`), exercising the LAN message-ID path.

1. Both new accounts complete all six onboarding screens with persisted Back navigation, different programs, a synthetic photo and two prompt answers each. Local adult declaration leaves Dating off; each separately chooses reciprocal preferences and opts in.
2. Cross-program discovery and program/year/interest filters find the other profile. Full photos and answers load. Hidden intentions and private fields stay out of unauthorized projections; signed-out direct profile/photo requests return 401.
3. A one-sided like creates no recipient notification, relationship or chat. Mutual likes create one dating match. Retried likes return the same relationship, with no friendship created.
4. Selecting a starter creates no message. Explicit Send delivers edited text; replies arrive live in the other browser without discarding its draft.
5. An offline send retains its text and retries once. A second fault commits a real POST and then loses its success acknowledgement; temporary sender-side history failure keeps Retry available. Retrying returns the same message ID and leaves one stored copy. Normal history reads are restored afterward.
6. A forced server crash and restart preserve sessions and all saved records. Live delivery resumes before refresh. After refreshing both browsers, photo hashes, prompts, programs, intentions and the five saved messages remain unchanged. Send fits above the bottom navigation, images load and neither tested viewport overflows horizontally.
7. A hidden profile remains accessible to its accepted match. Unmatching closes the other live client and denies direct history, send and starter requests for both. With that consent ended, the hidden profile and its direct photo URL return 404 to the other account; the owner retains access.
8. After fresh mutual consent, switching Dating off denies conversation access and the Dating profile projection. Switching it on again restores no match without new mutual likes.
9. After another fresh mutual match, blocking closes both clients and denies profile/photo URLs, discovery and conversation reads/sends/starters in both directions. Unblocking restores no consent. The database retains exactly one relationship and five legitimate messages; no denied send or retry created an extra record. No uncaught JavaScript errors or CSP violations were detected.

Evidence: `artifacts/journey-results.json` contains the successful groups, viewport sizes, fresh-account/message counts and completion timestamp. `artifacts/journey-chat-mobile.png` illustrates the tested chat. These are ignored generated artifacts; assertions determine success. All temporary accounts, images and messages are removed with the test database. The user's running database is untouched.

The full API suite also passed: **110 tests in 65.71 seconds**, with one upstream TestClient deprecation warning. The existing general browser regression passed all seven groups using `.venv/bin/python -m tests.browser_smoke`. Every frontend module passed `node --check`; Python compilation and `node tests/message_id.mjs` passed. `pip check` reports no broken requirements. The missing `requests` dependency used by the existing browser scripts was added to `requirements-dev.txt` and installed in the virtual environment.

The existing app on port 8001 returned 200 for health, signup, Matches and its navigation module over the LAN. On 23 October 2026, the user confirmed the Create test account page loads on both physical phones at `http://172.18.3.76:8001/signup`. This is a user-reported page-load result; phone models and browsers have not been recorded. **Physical phones have not yet completed the journey.** [PHONE_TEST.md](PHONE_TEST.md) records the remaining steps, including registration, matching, live chat, background/resume, the phone keyboard and an observed restart on both devices. Phase 6 remains open for those results.

## Dating as the primary Discover experience

Command: `python3 -m tests.dating_browser`

**Result: all checks passed**, including the user's specific scenario of Alice and a newly created account. The mobile browser used an exact 390 × 844 CSS-pixel viewport. The initial Set up Dating button is visible above the bottom navigation without scrolling.

- Dating appears first, remains optional, and displays actual opted-in adult test fixtures after setup.
- Pass persists a cooldown; one-sided likes do not create a match or recipient notification.
- Mutual likes create a genuine match with a Say hello action, followed by bidirectional dating chat. No friendship is created.
- Unmatching and disabling Dating revoke both UI and direct API history access.
- Explicit fixture account switching rotates only that browser's old session.
- A created account rejects an under-18 date. An adult date plus an explicit local test acknowledgement establishes self-declared test access without enabling Dating or claiming verified status. Separate opt-in and reciprocal preferences then permit an actual match and message exchange with Alice.
- No uncaught JavaScript errors or CSP violations were detected. The general `tests.browser_smoke` regression also passed after adapting navigation for Dating appearing first.

Screenshots: `artifacts/dating-setup-mobile.png`, `dating-discovery-mobile.png`, `dating-mutual-match.png`, and `dating-chat-mobile.png`. The phone server was restarted with the updated backend; `/dating` and its module returned 200 over the LAN. Its new eligibility endpoint correctly returned 401 when signed out.

## Local phone access check

The app was also served on the computer's Wi-Fi interface on port 8001. The LAN health endpoint returned 200. Chromium at a 390px viewport loaded the actual LAN HTTP origin with no horizontal overflow. In that browser, `isSecureContext` was false and `crypto.randomUUID` was unavailable; the new message-ID helper successfully generated a cryptographic UUID using `getRandomValues`. `node tests/message_id.mjs` passed for both secure-context and plain HTTP cases. This verifies LAN serving and the browser compatibility fix; an actual handset connection still depends on both devices sharing a network that permits peer access.

## Light/dark theme toggle — 23 October 2026

The toggle is available in public page headers and the authenticated app header. The external initialization script runs before the stylesheets and applies the saved choice, or the device preference when no choice exists. Browser-only styling changes leave the API and database schema unchanged.

The existing `python -m tests.navigation_browser` regression passed all five groups with the new control. Ad hoc Chromium checks on an isolated temporary server also passed:

- Native Space-key activation, accessible pressed state and retained unsaved sign-in input; the explicit preference survives reload.
- One toggle per public page, including welcome, signup, policies and recovery, without horizontal overflow at 320px, 390px or 1280px. The control meets the tested 44px target. Tested dark text, button, notice and navigation combinations meet 4.5:1 contrast.
- System theme changes apply until the student makes an explicit choice. A manual choice takes precedence and synchronizes between tabs on the same origin.
- With local storage forced to throw, the device theme still applies, the toggle still works and the form remains usable. There are no uncaught JavaScript errors or CSP violations.
- Unsaved profile text, prompt answers and chat drafts survive toggling light → dark and dark → light. Profile photos have no color filter applied.

The complete existing nine-group fresh-account journey also passed with dark device preference emulated in both browsers. This includes onboarding, photos/prompts, adult test setup, cross-program discovery, private likes, mutual matching, edited starters, actual bidirectional live chat, offline/lost-acknowledgement retry, forced server restart, persisted records, unmatch, Dating deactivation and blocking. Theme switches were additionally exercised with unsaved profile/prompt/message drafts during that run. The tests used temporary records; the running app's accounts were untouched.

Evidence: `artifacts/theme-results.json`, `artifacts/theme-profile-dark-mobile.png` and `artifacts/theme-chat-dark-mobile.png`. The targeted theme checks were an ad hoc validation using the existing journey helpers; they are not a new permanent test suite. All frontend JavaScript syntax checks, Python compilation and the HTTP-compatible message-ID check passed. The PC and current LAN origins both serve the new theme script/styles and updated sign-in document. These browser results do not close the pending physical-phone acceptance item.

## Conversation and discovery refinement — 23 October 2026

**Result: all 110 API tests passed in 63.09 seconds**, with the existing upstream TestClient deprecation warning. All nine browser suites listed below passed against isolated temporary records. The API/schema and message idempotency policy are unchanged.

| Browser command (`python -m …`) | Result and scope |
| --- | --- |
| `tests.conversation_browser` | Five focused groups: compact photo-open profiles, private contextual intentions, grouped messages, photo/name/avatar access with retained drafts, mobile Return/newlines, reduced viewport height, light/dark bubble contrast, pagination/scroll position, New messages, message reporting and chat-menu Unmatch. |
| `tests.journey_browser` | All nine groups: two fresh accounts through real onboarding, profiles, cross-program discovery, private likes, one mutual match, live bidirectional messages, offline/lost-acknowledgement retry, forced restart, persistence and direct consent/privacy denials. |
| `tests.navigation_browser` | All five groups: main/secondary navigation, keyboard tabs, editor shortcuts, mutual matching/chat, independent errors/recovery, loading, focus, contrast and phone layout. |
| `tests.browser_smoke` | All seven groups: registration/onboarding, friendship request/accept/live chat, retry/restart, blocks, persisted profile/report/moderator flow and mobile/console checks. |
| `tests.dating_browser` | All checks: visible setup, Pass, private/mutual likes, chat, unmatch, disabling Dating, explicit demo switching and Alice matching/messaging with a created adult test account. |
| `tests.photo_browser` | All six groups: upload/order/main/replace, offline retry/invalid files/cap, crash persistence, galleries/avatars, live updates, blocks and removal. |
| `tests.prompt_browser` | All six groups: optional editing/order/removal, independent drafts/saves, retry/restart, photo-open full answers, safe text, dating/chat and blocks. |
| `tests.intention_browser` | All six groups: optional sharing/labels, filters/reset, contextual full profiles, draft-preserving updates, retry/restart and block denial. |
| `tests.starter_browser` | All five groups: explicit optional opening, safe selection/edit/send, source updates, independent failure/retry, persisted messages and revoked access. |

The focused conversation test uses separate 390 × 844 dark and 412 × 915 light Chromium sessions, synthetic photos and fictional accounts. It verifies received/sent message text contrast of at least 4.5:1, one incoming avatar per visual group, grouped time labels, a draft surviving profile viewing, and a viewport reduced to 430px with the composer/navigation still visible. Mobile Return creates newlines without premature sends. A 62-message exercise checks pagination without duplicate IDs, preserving the top reading position on a new arrival and using the New messages control to reach the bottom. Message reports reach the user's submitted reports; chat-menu Unmatch denies direct history/send/starter reads for both participants.

Screenshot inspection caught an outgoing dark-message contrast issue caused by an overly specific grouped theme selector. The selector was corrected; explicit light/dark contrast assertions and the complete focused suite then passed. Profile answers and intentions now live in the opened profile; existing prompt/intention tests were updated to exercise the deliberate photo-open behavior. Starters default to collapsed, and phone chats keep the four main destinations below the conversation. Earlier phase records describe their UI at that time; this section supersedes older references to card answer/intention previews and automatically expanded starters.

Evidence: `artifacts/conversation-results.json`, `artifacts/conversation-light-mobile.png`, `artifacts/conversation-dark-mobile.png` and `artifacts/discovery-compact-dark.png`. Assertions, API status/data checks and persisted IDs determine success, not screenshots. The [UX review](UX_REVIEW.md) records the supplied reference, official third-party help sources and the decisions they informed; no installed third-party app audit is claimed.

All frontend modules passed `node --check`; Python compilation and `node tests/message_id.mjs` passed. The running PC origin and current Wi-Fi origin on port 8001 serve the updated document and exact current app, Dating, theme and conversation assets. Signed-out chat reads return 401. The Wi-Fi address at this check was `10.92.143.176`; addresses can change.

These checks do not finish the physical-phone journey. The device guide still requires native keyboard, background/resume, network recovery and observed two-device restart results. No public readiness, load/latency benchmark or complete accessibility/cross-browser audit is claimed.

## Optional safety footer — 25 October 2026

Report and Block now live behind a native, initially collapsed Safety & support disclosure below the chat composer. The per-message report controls are removed. Header options provide a shortcut to this footer; full-profile actions are also collapsed. Reporting can attach a chosen received message. Final report submission and block confirmation use the existing API and permissions; no schema or backend route changed.

Current verification:

- `.venv/bin/python -m tests.conversation_browser` — all five groups passed. Report/Block are hidden initially in both themes and inside unopened profile disclosures. Opening the header menu reveals no direct Report/Block actions. Its safety shortcut opens the bottom disclosure. Merely opening or cancelling these controls creates no report/block and preserves the composer draft. A selected-message report stores the exact chosen message ID, and a fresh match can be explicitly blocked through the footer, revoking both participants' UI and direct API access.
- The same focused run passed light/dark readability, keyboard disclosure activation, mobile Return/newlines, history pagination without duplicate IDs, reading-position preservation, and the New messages shortcut. At a reduced 430px viewport, both closed and expanded footer states keep the composer/actions above navigation with 44px action targets. No uncaught JavaScript or CSP errors were detected.
- `.venv/bin/python -m tests.browser_smoke` — all seven groups passed, including real friendship chat, offline retry, forced restart, footer blocking, explicit profile-safety reporting, moderator review, report status, persisted profile edits and onboarding. Other feature scripts' safety paths were updated to the new disclosure location.
- Every frontend module passed `node --check`; Python compilation and `node tests/message_id.mjs` passed. The current PC/LAN instance serves the exact updated app and conversation stylesheet on port 8001. The Wi-Fi address at this check was `10.106.85.176`; it can change.

Evidence remains in `artifacts/conversation-results.json`, `artifacts/conversation-light-mobile.png`, `artifacts/conversation-dark-mobile.png` and `artifacts/chat-safety-open-dark.png`. All accounts and report/block records used for these tests belong to temporary databases.

The user confirmed both physical phones are Android. Their models/browsers and full native-keyboard/background/network results are still pending in [PHONE_TEST.md](PHONE_TEST.md). OS confirmation is not a completed device acceptance run. The full 110-case API result and nine-suite audit recorded on 23 October remain historical evidence; the two suites above are the targeted reruns for this frontend change.

## Limits

No real students participated in the automated tests. Local adult declarations are not age verification. A live SMTP service was not configured; recovery tests use an injected transport. This was not a load/soak test, accessibility audit, cross-browser/device test, backup recovery exercise, security certification, legal review, or public deployment. See [remaining gates](STATUS.md).
