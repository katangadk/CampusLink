# CampusLink development checklist

Created: 22 October 2026. Keep this file updated as we work through each phase.

**Product:** a campus dating app where adult students discover people across programs, like publicly, match mutually or accept a private comment request, and chat. Friendship and study connections stay secondary.

**Main journey:** Discover → Like → Mutual match → Chat, or Comment privately → Recipient accepts → Chat.

**Phases 1–3 completed: 22 October 2026. Phases 4–5 completed: 23 October 2026. Phase 6 automated journey checks passed on 23 October; acceptance on two physical phones remains open.**

An item is complete when its interface and backend work together, its data persists where needed, and the relevant checks pass. Screenshots alone do not establish completion. Update [validation evidence](docs/VALIDATION.md) after functional changes. On 27 October the owner authorized the remaining launch work; its current evidence and external dependencies are recorded below.

## 0. Agreed direction and existing foundation

Checked items reflect the current implementation and previously recorded validation; this checklist does not represent a new test run.

- [x] Make Dating the first Discover view, with visible setup and explicit opt-in.
- [x] Support discovery across academic programs, with program, year, and interest filters.
- [x] Use deep plum `#43283F`, lavender `#F6F4FF`, rose `#F2A4C7`, and white `#FFFFFF`.
- [x] Provide registration, login, persistent profiles, and progressive onboarding.
- [x] Support explicitly labelled local 18+ test setup for created accounts without claiming verified age or identity.
- [x] Enforce reciprocal dating preferences, mutual matching and Pass; new profile likes are public, earlier private likes remain private.
- [x] Provide persistent live chat, unread counts, history, reconnection, and duplicate-safe message retry.
- [x] Enforce conversation permissions on the backend.
- [x] Provide unmatch, Dating deactivation, blocking, reporting, and role-restricted moderation.
- [x] Support local network access and message sending over a phone's HTTP connection.
- [x] Record automated API and browser checks, including Alice matching and messaging with a created test account.

## 1. Profile photos — completed

- [x] Add an optional profile photo gallery; keep initials as the fallback.
- [x] Let a student upload, preview, replace, reorder, and remove their own photos.
- [x] Let the student choose a main photo.
- [x] Validate actual file contents, supported formats, size, and image dimensions on the server.
- [x] Resize and compress uploads for mobile; remove embedded location metadata.
- [x] Persist processed image data and records across refreshes and server restarts (private SQLite BLOB storage).
- [x] Apply profile visibility, eligibility, and block rules when serving photos.
- [x] Show the main photo consistently in Discover, Matches, Chats, and Profile.
- [x] Remove stored image data when the owner deletes a photo or deletes the account.
- [x] Check upload failure/retry, invalid uploads, unauthorized access, and a phone-sized layout.

## 2. Profile personality prompts — completed

- [x] Offer campus-friendly questions such as “I can talk for hours about…” and “My ideal campus date would be…”.
- [x] Allow up to three optional prompt answers per profile.
- [x] Support editing, reordering, and removing answers.
- [x] Save answers with server-side validation and safe text rendering.
- [x] Show chosen answers in the full profile opened from compact discovery cards.
- [x] Check persistence, empty answers, long inputs, visibility rules, and mobile editing.

## 3. Dating intentions — completed

- [x] Add optional choices: looking for a relationship, getting to know people, and still figuring it out.
- [x] Let students choose whether to display their intention in Dating.
- [x] Keep this dating information out of friendship and study profile views.
- [x] Provide a clear way to edit, hide, or remove the choice.
- [x] Add an optional discovery filter without excluding people who leave their intention unset by default.
- [x] Check that labels, filtering, and privacy work consistently through the API and interface.

## 4. Conversation starters — completed

- [x] Offer optional questions after a mutual match, using shared interests or visible prompt answers.
- [x] Let either participant choose a suggestion, edit it, or write their own message.
- [x] Send only after the student explicitly presses Send.
- [x] Keep suggestions inside authorized, active dating conversations.
- [x] Check the no-shared-interests fallback and failed-send retry.

## 5. Finish the dating-first navigation — completed

- [x] Use Feed, Discover, Matches, Inbox, and Profile (updated 25 October).
- [x] Make Matches open dating matches by default.
- [x] Keep friendship and study connections accessible as secondary views.
- [x] Make photos, prompts, intentions, preferences, and visibility easy to edit.
- [x] Update navigation labels, links, empty states, guides, and browser checks together.
- [x] Check phone navigation, keyboard access, focus, contrast, and loading/error states.
- [x] Add a remembered light/dark theme toggle on public pages and the app header; preserve drafts while switching and validate Dating/chat in dark mode.

## 6. Validate the complete updated local app

The combined run uses two freshly registered accounts, an initially empty temporary database, separate 390px/412px Chromium sessions, and the computer's plain HTTP LAN origin. It passed all nine groups; this does not complete the physical-device item below. See [recorded evidence](docs/VALIDATION.md#phase-6--combined-fresh-account-journey-23-october-2026).

- [x] Create two independent adult test accounts in different academic programs.
- [x] Complete onboarding, add photos and prompt answers, and explicitly activate Dating on both.
- [x] Discover each other across programs with mutually compatible preferences.
- [x] Confirm one-sided interest alone creates no chat and a mutual like creates exactly one match; new public reaction visibility is covered in the social checks.
- [x] Open the match and exchange real messages in both directions.
- [ ] Test the updated journey on two physical phones over the local network; record device and journey results in [the phone test guide](docs/PHONE_TEST.md).
- [x] Check failed-send retry, refresh, and server restart without lost saved messages or duplicates.
- [x] Confirm unmatch, blocking, and disabling Dating revoke the relevant access.
- [x] Check photo and profile privacy through direct API requests, not just hidden buttons.
- [x] Run the relevant API, browser, and syntax checks and record results in `docs/VALIDATION.md`.
- [x] Update README and implementation status to match the delivered behavior.

## Conversation and discovery refinement — 23 October 2026

- [x] Keep discovery cards compact; move bio, interests, answers and full academic/Dating detail into photo-open profiles.
- [x] Make discovery photos, match avatars, chat headers and sender avatars open the authorized profile.
- [x] Give phone conversations more space; group messages and collapse optional starters.
- [x] Preserve drafts, handle mobile Return/newlines and viewport changes, and preserve the reading position in older history.
- [x] Keep message reporting and chat-menu unmatching/blocking functional.
- [x] Review official app guidance and record decisions in [UX_REVIEW.md](docs/UX_REVIEW.md).
- [x] Pass the 110 API tests and all nine browser suites; record results in [VALIDATION.md](docs/VALIDATION.md).
- [ ] Complete the updated journey on physical phones, including native keyboards and background/resume; this remains part of Phase 6.

## Optional safety footer — 25 October 2026

- [x] Move Report/Block behind a collapsed Safety & support section below the chat composer.
- [x] Remove per-message reporting buttons and collapse full-profile safety actions.
- [x] Keep reports optional, support a selected received message, and require explicit submission/confirmation.
- [x] Verify that opening/cancelling controls takes no action and preserves drafts; reporting, moderation and confirmed blocking remain functional.
- [ ] Confirm the updated controls on the user's two Android phones as part of Phase 6.

## Public likes, private comments and Feed — 25 October 2026

- [x] Remove repeated campus slogans, the leaf icon and the normal Live updates badge; use direct page labels.
- [x] Show Like, Comment and Inbox on Dating cards; keep Pass in the options menu.
- [x] Make new profile/post likes and liker identities public to authorized campus viewers; preserve older private Dating likes.
- [x] Keep comments private; require the recipient to accept an initial inbox request before chat opens.
- [x] Provide text/photo posts, caption editing, confirmed deletion, public reactions, private photo access and duplicate-safe retry.
- [x] Show Sent, Delivered and Read from stored server/device acknowledgements, with visible/latest-conversation checks for Read.
- [x] Exclude music as requested.
- [x] Pass 126 API tests and all ten browser scripts during this update, including a rerun of the complete journey after fixing shared-Wi-Fi quotas and redundant receipt requests.
- [ ] Confirm these updated flows on both physical Android phones; Stage 6 remains open.

## Motion and interaction — 25 October 2026

- [x] Add brief button, saved-like, profile/post, navigation and dialog feedback without delaying real actions.
- [x] Show placeholders only during actual pending profile/post loads.
- [x] Animate fresh messages once; keep initial/older history and receipt updates still, preserving reading position and drafts.
- [x] Respect reduced motion and keep controls usable without animation; restrict hover lifts/photo zoom to mouse/trackpad users.
- [x] Preserve keyboard focus after successful or failed post likes, without moving focus away from another control the user chose.
- [x] Pass the social/conversation browser suites and focused reduced-motion, 320px/desktop, focus, draft and message checks; record the scope in validation.
- [ ] Confirm the feel and native keyboard behavior on the two physical Android phones; Stage 6 stays open.

## Original hosted test preparation — 25 October 2026 (historical)

- [x] Add a staging mode that fails closed without HTTPS, a canonical host, separate database storage and a strong tester gate.
- [x] Protect pages, static assets, photos, APIs and SSE; retain individual account sessions, CSRF and relationship permissions.
- [x] Hide fixture login helpers and refuse copied demo databases and demo seeding in staging.
- [x] Add the Render Blueprint, Python version, one-worker launcher and generated secret configuration.
- [x] Add owner-only consistent SQLite backups; validate accounts, messages, sessions and images after restore.
- [x] Pass the local API regressions, restricted TLS browser journey and local social-browser regression; record exact results in validation.
- [x] Prepare source-only publication for the user-provided GitHub repository.
- [x] Create the hosted service after Render account connection and review of the paid compute/storage estimate; user deployed `campuslink-staging`.
- [x] Locate the actual HTTPS URL and verify its public health endpoint and restricted tester challenge.
- [x] Remember accepted tester access separately from account login; pass 179 API tests and all seven TLS browser groups with one native tester challenge per browser.
- [x] Deploy the initial cookie fix (`b93e69c`); Render confirmed success, but the user still reported the prompt.
- [x] Replace native HTTP-auth prompts with an HTML access form, clear password/cookie errors, same-origin/CSRF protection and recovery of the original page; pass 199 API tests and eight TLS browser groups with zero native challenges.
- Shared-gate work above is historical; it is superseded by the direct-access update below.
- [ ] Validate the actual Render URL, managed certificate, persistence across redeployment and off-Wi-Fi two-phone journey.
- [ ] Record hosted backup/restore and actual email-delivery results if email is configured.

## Direct website access — 27 October 2026

- [x] Remove the shared tester password, access page/cookies and frontend gate redirect.
- [x] Open landing, signup, sign-in and required assets directly; ignore old tester settings and redirect old access-page bookmarks to the website.
- [x] Retain HTTPS, normal account authentication, CSRF, private messages/photo permissions, consent and block checks.
- [x] Pass all 168 API tests and eight TLS browser groups, including direct entry, normal login/logout, matching/chat, offline retry, restart persistence and zero native password challenges.
- [x] Deploy the direct-access update (`739c3ff`); the user confirmed access works, and the hosted landing/health endpoints return 200 without a password challenge.
- [ ] Complete the full hosted journey on both Android phones: registration, cross-program discovery, mutual match, messages/receipts, photos, offline retry and background/resume.

## Later feature backlog

- [ ] Consider simple campus date activity ideas after the main journey is complete.
- [ ] Reassess additional features against whether they help students discover, match, or converse.

## Launch work — authorized 27 October 2026

Owner decision: the owner approves account emails/membership. There is no verification-provider account yet. Membership approval does not establish email ownership or checked 18+ status. Support contact: kabundakatanga91@gmail.com.

- [x] Add a trusted-console operator grant, audited membership queue and pending-account screen. Auto approval enforcement activates with the first operator grant; no shared website password returns.
- [x] Enforce approval on discovery, connections, photos/uploads and live chat; keep own security/support/account deletion available. Decline ends connections; re-approval requires fresh connection consent.
- [x] Add email ownership confirmation and durable TLS SMTP recovery jobs with expiry, single-use tokens, bounded retries and restart recovery.
- [x] Prepare the optional external student/18+ provider adapter; enforce live canonical results, account/institution/identity binding and signed webhooks. Test responses are rejected.
- [x] Add scheduled consistent backups, bounded retention, content/integrity checks, isolated restore checks and password-confirmed operator downloads.
- [x] Add expired-record cleanup, request IDs, operator service metrics and private pilot feedback/triage.
- [x] Document support/moderation procedures, SMTP/provider setup, offsite recovery, privacy review and a consenting-student pilot.
- [x] Pass the owner approval/email/feedback/backup browser journey and the 16-account, 8-match messaging exercise. These use isolated QA services, not actual Render or physical phones.
- [ ] Deploy this launch-work update to the actual Render service and grant the owner's existing account operator access using the trusted server shell.
- [ ] Configure SMTP privately and confirm confirmation/reset messages arrive in an actual mailbox.
- [ ] Confirm a live provider supports the actual Zambian university and both student/18+ evidence checks; configure credentials/consent and validate real outcomes before using external eligibility.
- [ ] Supply the legal operator identity, complete privacy/legal review and approve reports/audit/external-backup retention and appeals procedures.
- [ ] Download and protect an actual offsite backup, rehearse hosted recovery, and configure external operational alerts.
- [ ] Finish the hosted discovery → match → chat journey on both Android phones, including keyboard, mobile data, receipts, offline retry and background/resume.
- [ ] Conduct the consenting adult student pilot, resolve observed issues and retest before expanding access.

The application remains a preview. Supporting code and automated tests do not complete the unchecked real-world acceptance items. See [operator runbook](docs/OPERATIONS.md), [pilot plan](docs/PILOT.md) and [implementation status](docs/STATUS.md).
