# Discovery and conversation review — 23 October 2026

The supplied chat reference guided the spacing, rounded bubbles, sender grouping
and compact header. No song card, music player or Spotify integration was added.
The app retains its plum/rose palette and remembered light/dark themes.

## Comparison sources

This was a review of official product/help documentation, not hands-on testing
of installed third-party apps or access to their private systems.

| Source | Documented pattern | CampusLink decision |
| --- | --- | --- |
| [Bumble: Your conversations](https://support.bumble.com/hc/en-us/articles/28055378294685-Your-conversations) | A dedicated conversation/match area and optional opening help; no read receipts or activity status. | Keep a dedicated inbox and optional collapsed starters. The initial design used Saved for server commits. The 25 October update uses persisted Sent/Delivered/Read acknowledgements at the user’s request; no typing or online indicators are invented. |
| [Tinder: Unmatching someone](https://www.help.tinder.com/hc/en-us/articles/115003360106-Unmatching-someone) | Unmatch is available from the conversation's three-dot menu. | Keep Unmatch and View profile in chat options; Report and Block are behind the optional bottom safety section. The backend still authorizes every message read/send. |
| [Match: Chat with your matches](https://help.match.com/hc/en-us/articles/7341373823771-Messages-How-to-Chat-with-Your-Matches) | Matching leads into a thread with a bottom composer; photo/profile actions connect discovery and conversation. | Keep stable header/log/composer regions. Discovery photos, match avatars, the chat header and incoming sender avatars open the authorized full profile. |

Compact cards and message grouping are our design choices based on the user's
reference. These sources do not establish that all three apps have identical
interfaces. Their pricing, verification, deletion and unmatching policies were
not copied. CampusLink retains its documented consent/retention policy: ending a
conversation revokes access; fresh mutual consent can restore retained history.

## Delivered behavior

- Discovery cards show the photo or initials cover, name, Dating age where
  applicable, program, unverified test label and relevant actions. Bio, year,
  subjects, skills, study goals, interests, answers and displayed Dating intention
  belong in the opened profile. Filters retain their existing authorization.
  Repeated explanatory banners and side rails are removed.
- Phone chats use the available viewport above the main navigation.
  The general top bar and page heading leave room for the conversation. The chat
  header offers Back, a photo/name profile button and conversation options.
- Consecutive messages from one sender within five minutes on the same Lusaka
  calendar day form a visual group. Date separators, one incoming sender avatar
  per group and compact time/saved labels reduce repetition.
- Starters begin collapsed and never send automatically. Storage/permission help
  lives in About this chat instead of repeating inside every message log.
- The composer grows for multiple lines. Touch-device Return inserts a newline;
  Send submits. Desktop Enter sends and Shift+Enter inserts a line. Visual
  viewport changes adjust the chat and navigation bounds.
- Incoming messages preserve the reading position in older history. New messages
  returns to the latest; pagination retains message IDs without duplicates.
  Profile viewing and live updates retain drafts. Unsent drafts still clear on a
  full refresh as documented.
- Unmatch/End connection remains in the chat menu. As updated on 25 October,
  Report and Block appear only after opening Safety & support below the composer.
  The report form can attach a selected received message; a block still needs
  separate confirmation. Profile safety actions are also collapsed. Profile/photo permissions continue to follow the
  current relationship context and server-side checks.

## Verification and limits

[VALIDATION.md](VALIDATION.md) records the actual results. The focused
`tests/conversation_browser.py` covers photo-open profiles, grouping, drafts,
mobile Return, reduced viewport height, light/dark message contrast, history,
scroll position, reporting and chat-menu unmatching. Existing journey and feature
regressions cover the underlying flows.

Actual phone keyboards and background/resume behavior still need the
[physical-device run](PHONE_TEST.md). Browser/API checks do not establish public
readiness or performance at campus-wide scale.

## User-directed update — 25 October 2026

The user requested simpler labels, public likes, private comments, inbox access, text/photo posts and actual delivery/read states, then explicitly excluded music. Those choices supersede the initial private-like/Saved-only UI. Dating cards now use Like, Comment and Inbox; Pass is secondary. New public reactions display authorized liker lists, while earlier private Dating interests are not published. Private comments create recipient-controlled inbox requests or enter an existing conversation. A separate Feed holds posts without filling discovery cards with profile detail. Repeated ZUT/campus slogans, the leaf header icon and the normal Live updates label are removed. Receipt states depend on server persistence and receiving-client acknowledgements; Read requires the visible latest conversation. These are implementation choices requested by the user, not claims about third-party apps.
