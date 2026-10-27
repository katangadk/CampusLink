# CampusLink

Campus dating, discovery and conversations.

Follow the [development checklist](CHECKLIST.md) for completed work, the next features in order, and remaining launch tasks. **Stages 1–5 are implemented. Stage 6's combined fresh-account journey passes automated checks; acceptance on two physical phones is still pending.**

A working local campus dating and student-discovery application with a FastAPI backend, a persistent SQLite database, and a responsive browser interface. The main path is **discover → public Like → mutual match → chat**, with private comment requests as another way to connect. Feed supports text/photo posts and public reactions. Comments stay private; a recipient must accept a request before a new conversation opens. Music is excluded. Friendship and study connections remain available.

**Status: local functional MVP, built and tested.** The owner has authorized launch preparation. Membership approval, queued email recovery/confirmation, backups/restore checks, operator monitoring and an optional external verification adapter are implemented. Actual hosted setup, email receipt, live verification, privacy review and student acceptance remain open. Local use remains supported. A hosted preview service is deployed at [campuslink-staging.onrender.com](https://campuslink-staging.onrender.com); hosted acceptance remains open. This implementation follows the supplied brief through section 14.4, where the pasted document ends mid-sentence. Full profiles and test-account setup identify fictional accounts as **Local test · Unverified**. CampusLink is independent of ZUT.

## Run locally

Use Python 3.11 or newer. No Node build or third-party frontend service is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m campuslink.seed
python -m uvicorn campuslink.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3
```

Open **http://127.0.0.1:8000**. SQLite records live in `data/campuslink.sqlite3` and survive browser and server restarts. The seed command is explicit and idempotent; starting the server never inserts fictional students automatically. The graceful shutdown timeout allows long-lived event streams to close during restart.

## Open on your phone

Connect your phone and computer to the same Wi-Fi, then start the server on the computer:

```sh
python3 -m uvicorn campuslink.app:app --host 0.0.0.0 --port 8001 --timeout-graceful-shutdown 3
```

While this server runs, open **http://127.0.0.1:8001** on the computer. Both the PC and phones use this server on port 8001. Keep its terminal open.

Find the computer's Wi-Fi IPv4 address using `ip -4 -brief address`. On your phone, open `http://COMPUTER_WIFI_IP:8001` in the browser, replacing `COMPUTER_WIFI_IP` with that address. Keep the computer and server running. Port 8001 allows the phone server to run alongside a desktop server on port 8000. Use the computer's network address rather than `localhost` or `0.0.0.0` in the phone browser. If it does not connect, check that the Wi-Fi allows devices to communicate and that your computer's firewall allows port 8001 on that local network.

This shares the local test build on your network; it does not publish an internet site.

For two-person testing, use separate browser profiles, two phones, or a private window. Follow the [two-phone acceptance guide](docs/PHONE_TEST.md) to record the complete Dating journey with fresh accounts. The supplied accounts below remain useful for individual checks:

| Account | Email | Password |
| --- | --- | --- |
| Alice | `alice@campuslink.test` | `CampusLink-local-2026!` |
| Brian | `brian@campuslink.test` | `CampusLink-local-2026!` |
| Moderator | `moderator@campuslink.test` | `CampusLink-local-2026!` |

Other fixtures: `chipo`, `david`, `esther`, `farai`, and `grace` at `campuslink.test`, with the same local password. Never reuse fixture credentials with real data. A newly registered account is explicitly a local test account and must complete onboarding. Dating requires separate 18+ test setup, explicit opt-in, and preferences; no account is presented as age-verified.

## Hosted preview deployment

Open [campuslink-staging.onrender.com](https://campuslink-staging.onrender.com). Visitors open the website directly, then create or sign in to their own accounts. The launch-work update (`330ae53`) is live. Activate your owner account below to use its new tools.

Follow [DEPLOYMENT.md](docs/DEPLOYMENT.md) for the Render Blueprint, persistent disk, HTTPS/proxy settings, normal account login, backup/restore and hosted checks. Old tester username/password environment variables are ignored; no shared access credentials are required.

`staging` keeps a canonical HTTPS origin, separate persistent database, Secure/HttpOnly account cookies, CSRF and private-data permissions. Online demo seeding and copied demo databases are refused. Production eligibility and hosted/student acceptance remain separate from direct preview access.

## Owner approvals and launch setup

You approve membership in **Profile → Operator console**. After deploying this
update, first create your individual account, then grant that existing account
operator access from Render's trusted service shell:

```sh
python -m campuslink.admin grant operator kabundakatanga91@gmail.com
```

Use your registered username/email if different. The support email does not
automatically grant privileges. Hosted approval enforcement activates with the
first operator grant; pending accounts can edit their profile and contact you,
then use discovery/chat after approval. Approve your own membership too.
Membership approval, mailbox confirmation and verified age are separate.

Follow [OPERATIONS.md](docs/OPERATIONS.md) for private SMTP configuration,
backup downloads/restore, monitoring, optional live verification and support
procedures. No provider account or paid service is created automatically.
The [pilot plan](docs/PILOT.md) records the real student work still needed.

## Light and dark themes

Use the **moon/sun button** in the header to switch themes. It is available on the welcome, sign-in, onboarding and app pages. CampusLink starts with your device's preferred theme and remembers your manual choice in that browser. Changing the theme keeps unsaved profile answers and message drafts in place.

## Motion and interaction

Buttons respond to taps, and saved likes receive a brief heart animation. Profiles, posts, navigation and dialogs use short entrance transitions; real pending loads show placeholders. New chat messages animate once while you are at the latest messages. Initial history, older messages, retries becoming saved messages and receipt updates do not replay the conversation. Motion never delays a request or indicates success before the server confirms it.

Animations automatically follow the browser’s **reduced motion** preference. Loading remains visible without motion, and every control works in either mode. There are no extra animation libraries, sounds or background effects. Refresh an already-open page to load the updated styles and modules.

## Find your way around

The five main destinations are **Feed, Discover, Matches, Inbox, and Profile** on both desktop and phone.

| Destination | What opens |
| --- | --- |
| Feed | Campus text/photo posts; public likes and private comments. |
| Discover | Dating first; For you, Friends, and Study partners are secondary categories. |
| Matches | Dating conversations opened by mutual likes or an explicitly accepted Dating comment. One-sided likes and pending requests are not matches. |
| Inbox | Authorized conversations and private message requests, with All, Friends, Study and Dating filters. |
| Profile | Quick links to photos, prompts, Dating preferences/intention, studies, and visibility. |

Open **Matches → Friends & study** for **Received**, **Sent**, **Friends**, and **Study**. Pending friendship/study counts appear on that secondary link. You can also open **Requests & connections** from a non-dating discovery view. The main Matches destination always returns to dating matches.

Secondary views have URLs such as `/connections?view=sent` and `/discover?mode=study`; refresh and Back/Forward preserve the chosen view. `/connections` remains available and opens received friendship/study requests. Profile shortcuts jump within the current editor and preserve drafts; links such as `/profile#prompt-manager` open that section directly.

Matches, Inbox and message requests load independently. Failed loads offer Retry; an already loaded list remains visible with a warning when refresh fails. A failed message-history read preserves the draft and offers **Retry messages**. Restoring connectivity can recover the composer and conversation starters together.

## Try Dating

Dating is the first view in Discover. You can also open `/dating` directly.

1. Sign in and choose **Set up Dating**. A newly created account first enters a private birth date and explicitly declares 18+ local test access. Under-18 dates are rejected. Alice and Brian already have adult fixture eligibility.
2. Check the separate Dating opt-in, choose your gender and who you are interested in, and select **Save and explore Dating**. For Alice to match a created account, both accounts must be opted in with reciprocal gender/age preferences and discoverability enabled.
3. Browse adult test profiles, **Like**, **Comment** or **Inbox**. Likes and liker identities are public; Comment is private. **Pass** is inside the profile’s options menu. Open **Matches** (or the **My matches** shortcut) for mutual dating connections and **Preferences** to update or disable Dating.
4. To test a real mutual match, use Alice in one browser and your created adult test account (or Brian) in another browser or private tab. Activate Dating on both with reciprocal preferences, then like each other. A genuine mutual match opens a **Say hello** action and a conversation under Inbox → Dating.

Created accounts can use self-declared adult access **only in this local test build**. This does not verify age, identity, or student status. An optional external provider adapter is prepared, but no live provider account or university coverage has been confirmed. The setup also offers **Use a fictional adult test account instead**, which explicitly switches this browser to Alice or Brian without changing the original account.

The seed includes explicitly opted-in fictional profiles `demo_daniel`, `demo_naomi`, and `demo_musa` so initial Dating discovery has people to browse. Their emails use `@campuslink.test` with the shared fixture password. They do not send automatic likes, messages, or notifications. Re-running the seed does not enable Dating on existing accounts. To add just these fixtures to an existing local database:

```sh
python3 -m campuslink.seed --dating-only
```

## Posts, public likes and private comments

Open **Feed**, write in **What’s on your mind?**, optionally choose **Photo**, then press **Post**. Each post supports one JPEG, PNG or still WebP image under the same image limits as profile photos. Uploads are processed and stored privately in SQLite. Post and upload keys make retries safe even if the server saved the post before its response was lost. Drafts survive in-app navigation within the same signed-in tab; refresh/sign-out clears unsent drafts. Saved posts and images survive restarts.

Use a post’s options menu to edit its caption or confirm deletion. Deleting removes the post, reactions and stored photo. Posts follow campus membership, active-account, discoverability/accepted-connection and both-direction block rules. New feed items and reaction counts load with **Refresh**; **My posts** filters by author. Likes are public to eligible campus viewers; tap the count to see people. **Profile → Profile likes** opens your own profile’s public reactions. Earlier private Dating likes are not copied into public reactions.

**Comment** opens a private message form, on either a profile or a post. Existing connections receive it in their conversation. Otherwise it appears under **Inbox → Message requests**, visible only to the sender and recipient. Only the recipient can choose **Accept & chat** or **Decline**; acceptance moves the initial comment into chat once. One request per sender/recipient prevents repeated messages after a decline. A Dating request still requires adult eligibility and reciprocal preferences when sent and accepted. **Inbox** on a profile opens an existing chat or a request form. No public comment thread or music player is included.

## Add profile photos

Open **Profile → Your photos**, or use the optional editor in the first onboarding step. Choose a file, check the preview, then press **Upload photo**. You can keep up to four photos, choose a main photo, move photos earlier/later, replace, or remove them. Photo changes save immediately and separately from your profile text. Removing the main photo promotes the next photo; removing all photos restores initials.

Supported files: JPEG, PNG, and still WebP, at least 200 × 200 pixels, at most 8 MB and 20 megapixels. HEIC and animations are not supported. The server resizes and compresses each image and removes embedded location metadata. Processed image bytes are stored privately in SQLite and survive restarts. Existing local databases gain the photo table automatically when the updated server starts.

Photos follow profile visibility, accepted-connection exceptions, and blocking rules. They are not public static assets. Failed uploads retain their preview and retry key in the current page so you can retry without creating another photo. Main photos appear in Discover, Matches, Inbox, Profile, and secondary friendship/study connections.

## Add personality prompts

Open **Profile → Your personality prompts**. Choose up to three questions, write up to 280 characters per answer, then press **Save answers**. You can change questions, edit answers, move them earlier/later, or remove them. Reordering and removal also need **Save answers**. Blank answers are rejected; remove a question to leave it unanswered.

Discovery cards keep the photo, name and program prominent. Tap the photo or name to open the full profile and read all saved answers, including in Friends and Study, under the same visibility and blocking rules as your profile. No answers are required during onboarding. Prompt changes save separately from your other profile text and photos. Failed saves keep your draft for retry; drafts survive navigation inside the app in the current tab, but clear on a full reload or sign-out. Saved answers survive reloads and server restarts. Existing databases upgrade automatically without changing accounts or photos.

## Choose a dating intention

Open **Profile → Dating preferences & intention**, or **Dating → Preferences**. Under **Your dating intention**, optionally choose **Looking for a relationship**, **Getting to know people**, or **Still figuring it out**. Sharing starts off. Check **Display my intention on my Dating profile** to share it, then **Save and explore Dating**. The choice never activates Dating by itself.

Uncheck the display option to hide a saved choice. Select **Leave unset / remove my choice** and save to remove it. Displayed intentions appear inside full profiles opened from Dating, a dating match, or its chat. Discovery cards stay compact. Friends, Study, and general profile reads omit this information, even when the same students also have a dating match.

In Dating, open **Filters → Dating intention** to select one displayed intention. **Any intention** includes students with hidden or unset choices; a specific filter includes only students who choose to display that intention. Hidden choices are never used for filtering. Clear filters or switch discovery categories to reset the intention filter. Different intentions do not prevent mutual matching or chatting. Preferences survive refreshes and server restarts, and failed saves keep the current form ready to retry.

## Use conversation starters

Open a mutual dating match through **Matches → Message**, or select it in **Inbox**. **Conversation starters** offers three optional questions based on shared interests and the other student's visible prompt answers, with campus questions when there is no overlap. The panel starts collapsed; open it whenever you want help starting. Friendship and study conversations do not show it.

Choose a question to fill the message box, edit it if you like, then press **Send** (or use the existing Enter send shortcut). Selecting a suggestion never sends a message. An existing draft stays in place; clear the box first if you want to choose a different starter. A failed send retains its message and retry key, and starter clicks cannot replace that pending message.

If suggestions fail to load, the composer remains usable and **Retry suggestions** reloads them. Questions are generated from currently authorized profile information. Blocking, unmatching, disabling Dating, or losing reciprocal eligibility denies further starter access, just like message access. Saved messages survive restarts; unsent drafts and panel preferences live only in the current tab.

## Chat and view profiles

Tap a discovery photo, match avatar, chat photo/name or incoming sender avatar to open the full profile. Cards keep detailed answers, interests and academic information inside this view. Dating information still follows the sharing setting and authorized profile context.

Conversations group consecutive messages and keep the composer at the bottom. On a phone, Return inserts a newline; tap Send to submit. Desktop Enter sends, while Shift+Enter adds a line. The composer grows for longer drafts. Reading older history keeps your position when new messages arrive; use **New messages ↓** to jump to the latest. At the bottom of a chat, open **Safety & support** when you want to report or block. It stays collapsed until you choose it. Report lets you select the conversation/profile or a received message; submitting the form sends it. Blocking requires a separate confirmation. The header menu keeps **Unmatch / End connection** and **About this chat**, with a shortcut to the bottom safety section. Profile safety actions are also collapsed. **Sent** means the server committed the message. **Delivered** means the recipient’s signed-in browser acknowledged receiving it through the inbox or conversation. **Read** means the conversation was visible and at the latest messages. These receipts persist; they do not prove a person read the text.

The [interface review](docs/UX_REVIEW.md) records the reference, comparison sources and behavior decisions. Physical phone keyboard/background tests remain in [the device guide](docs/PHONE_TEST.md).

## Exercise the actual product

1. Create two fictional adult test accounts in separate browsers or on two phones. Complete onboarding with different academic programs, a shared interest, a test photo and optional prompt answers.
2. On both accounts, open Profile → Dating preferences & intention, complete local 18+ test setup, then explicitly opt in with reciprocal gender and age preferences. Keep discoverability on.
3. Find the other account in Dating. Like from one side only and confirm other students can see the public like and its author, while no match or chat opens. Like back from the second account; exactly one mutual match should appear in Matches.
4. Open the match and exchange messages both ways. A conversation starter fills the composer without sending. Edit it and press Send. A typed draft should survive incoming messages.
5. Disconnect the sender’s network, attempt a send, reconnect, and retry. The failed message keeps its idempotency key; retrying saves a single copy.
6. Restart the server with the same database and refresh the browsers. Sessions, profiles, photos, answers, matches and saved messages persist. Unsent drafts belong to the current tab and do not survive a full refresh.
7. Unmatch, match again with fresh mutual likes, and disable Dating. Both actions stop chat access. Enabling Dating again must not restore a match automatically. Match again and block the other account; both lose profile/photo and chat access. Unblocking requires fresh mutual consent.
8. For secondary friendship/study checks, send a request from Discover → Friends or Study partners and accept it through Matches → Friends & study → Received. Acceptance opens a separate authorized conversation without creating a dating match.
9. Report a profile or incoming message. Sign in as the local moderator, open Profile → Moderation queue, and resolve, dismiss, or suspend. Ordinary students cannot access the moderation API.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check web/app.js
node --check web/theme.js
node tests/message_id.mjs
python -m tests.browser_smoke
python -m tests.dating_browser
python -m tests.photo_browser
python -m tests.prompt_browser
python -m tests.intention_browser
python -m tests.starter_browser
python -m tests.navigation_browser
python -m tests.journey_browser
python -m tests.conversation_browser
python -m tests.social_browser
python -m tests.staging_browser
```

The browser scripts require local Chromium and a matching `chromedriver` on PATH. Each starts and stops its own server, uses a temporary database, and creates two independent browser contexts. They write screenshots to ignored `artifacts/`. They exercise live delivery, an interrupted send, a forced server crash/restart, block revocation, safe rendering, and phone-sized viewports. They do not access or send email to real students. Browser and API tests require the OS to permit local sockets.

The combined `tests.journey_browser` check begins with an empty database and registers both accounts through the UI. To exercise a plain HTTP LAN origin, set `CAMPUSLINK_JOURNEY_HOST` to the computer's current Wi-Fi IPv4 address before running it. It binds a separate temporary server on an available port and does not alter the running app's accounts. A machine-readable result is written to `artifacts/journey-results.json` only after all groups pass. Physical-device results belong in [the phone test guide](docs/PHONE_TEST.md); browser emulation does not complete that item.

See [engineering decisions](docs/ENGINEERING.md) for data and permission rules and [implementation status](docs/STATUS.md) for evidence and remaining work.

## Optional password recovery

Password change and session revocation work without external services. Recovery uses expiring, single-use, hashed tokens and revokes every session after reset. A real SMTP transport is included but is **disabled until configured**; the sign-in screen says so. Set the variables in `.env.example` in the environment and restart. Recovery requires STARTTLS and a fixed trusted application URL. No token appears in API responses or server request paths; the emailed link uses a URL fragment which the browser removes immediately.

Recovery responds identically for known and unknown emails. Delivery runs after the response is sent. Tests exercise recovery with an injected test transport; an actual SMTP service has **not** been configured or verified. Do not treat a configured transport as a reviewed public recovery or email verification process.

## Deferred public launch work

Launch preparation is now authorized. Supporting approval, mail, verification and operations code is implemented; real provider coverage, SMTP receipt, privacy review, hosted recovery and student/device acceptance still require actual setup and observation. See the [operator runbook](docs/OPERATIONS.md).

`CAMPUSLINK_MODE` supports `local` and hosted-preview `staging`. Public/production values still refuse startup. The remaining acceptance work and deployment checks are tracked in [implementation status](docs/STATUS.md) for a future public launch.
