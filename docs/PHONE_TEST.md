# Stage 6: two-phone acceptance

Status: **signup page loads on both phones; remaining device checks pending**.
Both phones are Android, as confirmed by the user on 25 October 2026. Models
and browser names remain unrecorded.
The user confirmed both signup pages load at `http://172.18.3.76:8001/signup`
on 23 October 2026. Automated Chromium checks use two
separate phone-sized sessions; they cannot establish behavior on actual phones.
Use fictional adult test profiles and harmless messages for this local exercise.

## Connect

Keep the computer running and connect both phones to the same Wi-Fi. Open
`http://COMPUTER_WIFI_IP:8001/signup` in each browser. Find the computer's current
address with `ip -4 -brief address`; the address can change after reconnecting.
Server setup and network troubleshooting are in [README](../README.md#open-on-your-phone).
This address serves the existing local app, not the automated test's temporary
database. Do not run the seed command to reset existing accounts.

Address update, 25 October 2026: the computer's Wi-Fi IPv4 address changed to
`10.106.85.176`. The current phone URL is `http://10.106.85.176:8001`; use
`http://127.0.0.1:8001` on the computer. Health, signup, sign-in and the current
application module respond on both addresses. The earlier physical-phone
page-load confirmation used the previous address; access from the phones on
the new network still needs confirmation.

## When testing the hosted staging build

Use the actual HTTPS address produced by Render after deployment; no hosted address has been verified yet. Enter the separate tester gate username/password at the browser prompt, then use a different individual app account on each phone. Create fictional test accounts; the supplied Alice/Brian/moderator fixtures are not available in staging. Test on mobile data as well as Wi-Fi. Record the actual hosted URL, native gate prompt, HTTPS login, background/resume and redeployment results. See [DEPLOYMENT.md](DEPLOYMENT.md) for setup. Local TLS browser tests do not mark these device checks complete.

## Prepare two independent profiles

On each phone, create a different test account. For example, use usernames
`phone_ada` and `phone_ben` with corresponding `@campuslink.test` emails. Choose
your own test passwords; no real mailbox is needed. If those names already
exist, use different names rather than overwriting an account.

1. Complete all six onboarding steps. Choose Computer Science on phone A and
   Business Administration on phone B, with Music as a shared interest. Leave
   discoverability on.
2. Add one harmless test image on each phone and save two personality answers
   in Profile. Refresh and confirm the image and answers are still there. If
   the phone defaults to HEIC, choose a JPEG, PNG or still WebP instead.
3. Open **Dating preferences & intention**, enter a fictional adult birth date
   such as 15 June 2002, and acknowledge local 18+ test access. Explicitly opt
   into Dating on the following screen.
4. For this test, configure A as Woman interested in Men and B as Man interested
   in Women, with an age range including 24. Set any optional intention and
   choose whether to display it. These are fictional test details, not verified
   age or identity.

## Record the journey

Mark a box only after observing the result on the devices. If something fails,
record the step, exact error, phone model and browser. Screenshots can help,
but do not include passwords or private account details.

| Check | Expected result | Result |
| --- | --- | --- |
| Signup page loads | Both phones can open the Create test account page on the LAN address. | Passed — user confirmed, 23 October 2026 |
| Navigation | Both phones can open Feed, Discover, Matches, Inbox and Profile without clipping. | Pending |
| Cross-program discovery | Search the other test username in Dating. Each phone sees the other profile, image, program and answers. | Pending |
| Public like | Like B from A only. The like and author are visible on B’s profile likes; no match or chat opens yet. | Pending |
| Private comment | Send a comment without a match. Only the recipient sees it in Inbox requests; Accept opens one conversation, Decline does not. | Pending |
| Receipts | With the recipient offline, sender sees Sent. Reconnect on Feed for Delivered; open the conversation at the latest messages for Read. | Pending |
| Photo posts | Create a photo/text post on Feed, like it from the other phone, send a private comment, edit the caption and confirm deletion. | Pending |
| Mutual match | Like A from B. Each phone has exactly one dating match in Matches. | Pending |
| Photo opens profile | Tapping a discovery photo, match avatar or chat photo/name opens full details; closing the profile preserves a chat draft. | Pending |
| Conversation starter | The panel starts collapsed. Selecting a suggestion fills the box; it sends only after Send. Editing works with the phone keyboard open. | Pending |
| Live chat | Send from A to B and reply from B to A. Messages appear without refreshing. An existing draft survives incoming messages. | Pending |
| Motion | Likes animate only after saving; new messages enter once; drafts and reading position stay put. With the browser/device reduced-motion preference, controls and loading still work without animation. | Pending |
| Mobile keyboard | Return inserts a newline; Send submits. The composer stays usable above navigation with the native keyboard open. | Pending |
| History reading | New messages preserve the position while reading older history; the New messages button returns to the latest. | Pending |
| Offline retry | On A, switch Wi-Fi and mobile data off, attempt a harmless send, and see Retry. Restore Wi-Fi and retry once. B receives one copy. | Pending |
| Refresh | Refresh both pages. Saved history, photos, answers and preferences remain. | Pending |
| Background and resume | Lock or background one phone, send from the other, then resume. The conversation catches up; sending still works. | Pending |
| Server restart | Coordinate a restart on the computer using the same database. Both phones recover, retain history and can exchange another message. | Pending |
| Unmatch | Unmatch from A. The match disappears and neither phone can continue the chat. | Pending |
| Fresh consent | Both students find and like each other again; no match returns from just one like. | Pending |
| Disable Dating | Switch Dating off on A. B loses that dating chat. Turning Dating back on does not restore the match automatically. | Pending |
| Optional safety controls | Safety & support starts closed below the composer. Report/Block appear only after tapping it; cancelling either retains the draft and takes no action. | Pending |
| Report | Open Safety & support → Report, optionally choose a received message, then submit. Cancelling creates no report. | Pending |
| Block | Match again with fresh mutual likes, open Safety & support → Block and confirm. Both lose the chat and cannot view the other profile/photo through the app. | Pending |
| Unblock | Unblocking does not restore a match or chat without fresh mutual consent. | Pending |

The automated journey separately checks direct API denials for profiles,
photos, message reads/sends and starters; hidden buttons are not its acceptance
criterion. Do not mark those checks based only on what the phone interface hides.

## Device results

- Initial page-load test: 23 October 2026, `172.18.3.76:8001`; remaining journey pending
- Phone A: Android confirmed; model and browser pending
- Phone B: Android confirmed; model and browser pending
- Results and failed steps: pending
- Restart observed on both phones: pending

Copy confirmed results into [VALIDATION.md](VALIDATION.md) and update
[CHECKLIST.md](../CHECKLIST.md). The two-phone item stays open until the full
physical-device journey is confirmed; loading a page alone does not complete it.
