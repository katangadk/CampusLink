# CampusLink operator runbook

The owner approves membership. Approval does not confirm mailbox ownership or
prove a person is 18+. Direct website access remains open; there is no shared
site password. The application remains a preview until the outstanding hosted,
provider, privacy and consenting-student acceptance checks are complete.

## Deploy and become the operator

Deploy the latest reviewed `main` commit to the existing Render service. Keep
one worker/instance and the existing `/var/data` persistent disk. No additional
service or paid verification account is created by this source update.

1. Create your individual CampusLink account with an email you control.
2. In the **Render service → Shell**, grant that existing account staff access:

   ```sh
   python -m campuslink.admin grant operator kabundakatanga91@gmail.com
   ```

   This command works only if that email belongs to an existing active account.
   Otherwise replace it with your registered username/email. It does not set or
   reveal a password. Anyone registering the published support email does not
   automatically become an operator; only the trusted console grants the role.
3. Refresh your browser, open **Profile → Operator console**, or visit
   `/operator`. Approve your own membership and then the accounts you recognize.
4. With `CAMPUSLINK_REQUIRE_APPROVAL=auto` (hosted default), this first grant
   activates approval for all accounts, including existing preview accounts.
   They appear in the queue as pending. Activation survives restarts and later
   staff-role revocations. Local development defaults to approval off.

Use `CAMPUSLINK_REQUIRE_APPROVAL=true` to require approval immediately, even
before the first operator grant. Keep `auto` while preparing the staff account
so existing preview access is not interrupted before an owner can review it.
`false` is for isolated development tests. Operator access works while the
operator's own membership is pending; ordinary users cannot approve themselves.

To grant a reports-only reviewer, use `python -m campuslink.admin grant moderator
USERNAME`. To revoke staff, use `revoke` instead of `grant`. Revoking an operator
also removes their moderator role. Never use shared moderator credentials.

## Review members and reports

Verify that each applicant belongs to the intended campus using an agreed
process, then approve that account in **Membership approvals**. A public email
address alone is not enrollment evidence. A university-domain filter is
optional; no domain is guessed or automatically trusted. Do not collect ID
scans or university passwords in chat, feedback or ordinary email.

Declining requires confirmation, turns off Dating and ends existing
connections. Saved messages remain under the normal retention rules.
Re-approval allows campus access but does not recreate old connections or
reactivate Dating. Students retain access to their profile, security controls,
feedback, support and account deletion while pending or declined.

Review **Profile → Moderation queue** and private pilot feedback at least daily
while the pilot is running. Prioritize credible threats, harassment, minors,
impersonation and repeated unwanted contact. Review only the relevant report
and selected message. Resolve or dismiss with the existing controls; use
suspension when justified. Decisions are audited. A suspended/deactivated
account is not reactivated by membership approval. Appeals go to
**kabundakatanga91@gmail.com**; verify account ownership privately and record
review evidence before a trusted server administrator changes account status.
No response-time guarantee or staffed moderation team is claimed by this code.

## Email confirmation and recovery

The support address alone does not configure sending. Set SMTP credentials
privately in **Render → Environment**, never in GitHub or a chat message:

| Variable | Gmail example / purpose |
| --- | --- |
| `CAMPUSLINK_SMTP_HOST` | `smtp.gmail.com` |
| `CAMPUSLINK_SMTP_PORT` | `465` |
| `CAMPUSLINK_SMTP_TLS` | `ssl` (or port `587` with `starttls`) |
| `CAMPUSLINK_SMTP_USER` | The sending Google account |
| `CAMPUSLINK_SMTP_FROM` | That authorized sender address |
| `CAMPUSLINK_SMTP_PASSWORD` | A Google App Password, set only in Render |
| `CAMPUSLINK_MAIL_TOKEN_SECRET` | Independently generated random secret, at least 32 characters |

Google App Passwords require 2-Step Verification and are not available for every
account; follow [Google's instructions](https://support.google.com/mail/answer/185833?hl=en).
Use an SMTP provider supported by the hosting account if either account blocks
these connections. There is no plaintext fallback. Preserve the token secret
across deployments; rotation invalidates pending links. The Blueprint generates
this key for new synchronized configuration, but verify it exists on the actual
service. It is unrelated to normal account passwords or website entry.

In Render Shell, `python -m campuslink.mail` reports missing settings without
printing credentials. For an explicitly requested delivery test to your own
mailbox, run `python -m campuslink.mail --test-to kabundakatanga91@gmail.com`.
Confirm arrival in Inbox/Spam yourself. Then exercise **Forgot your password**
and **Profile → Email and eligibility → Send confirmation link** with your
account. Links expire after 30 minutes and are single use. A reset signs out
all sessions. Confirmation changes email ownership only.

Queued jobs survive restarts and retry transient failures up to five attempts.
The operator console shows delivery states. `sent` means the SMTP provider
accepted the message; it does not establish mailbox receipt. A disconnected
provider must not expose whether an address has an account.

## Optional external verification

No live provider account exists yet. The SheerID adapter is prepared and tested
against synthetic responses; actual university coverage in Zambia and both
required evidence programs are unconfirmed. Do not enable it or incur provider
costs until the owner confirms the provider arrangement and privacy treatment.

Before enabling, obtain a real provider account, confirm the exact institution
and its provider organization ID, and configure two separate **live** programs:
student enrollment for that institution in Zambia, and an age program enforcing
18+. The student program must supply enrollment evidence and identity fields
that can be bound to the age check. Honor-system or email-domain-only results
are rejected. No institution name/domain is inferred from the owner's email.

Set these privately in Render:

- `CAMPUSLINK_VERIFICATION_PROVIDER=sheerid`
- OAuth `CAMPUSLINK_SHEERID_CLIENT_ID` and `CAMPUSLINK_SHEERID_CLIENT_SECRET`
- `CAMPUSLINK_SHEERID_STUDENT_PROGRAM_ID` and `CAMPUSLINK_SHEERID_AGE_PROGRAM_ID`
- `CAMPUSLINK_SHEERID_ORGANIZATION_ID` (exact institution)
- `CAMPUSLINK_SHEERID_WEBHOOK_SECRET`
- `CAMPUSLINK_VERIFICATION_LIVE=true`

Configure the provider webhook as
`https://campuslink-staging.onrender.com/api/webhooks/sheerid`, with signed
`X-SheerID-Signature` and **extraSigningFields enabled** (timestamp in milliseconds
and nonce). Use the canonical `/verification` page for the return journey. A
redirect or success label alone cannot grant eligibility: CampusLink retrieves
the provider's canonical record and checks program, account email, institution,
evidence, live mode, expiry and matching identity across student/age checks.
Documents go directly to the provider; CampusLink stores references/status and
identity fingerprints, not document images or legal names. Adult verified birth
dates remain private. Student checks expire within 90 days or the earlier
enrollment end; age checks within 365 days. Old callbacks cannot renew them.

Only after the real setup and consent flow are accepted, switch
`CAMPUSLINK_ELIGIBILITY_MODE=external` and require membership approval. This
disables self-declared test eligibility. Confirmed email + owner approval +
student evidence are required for campus access; checked 18+ status and separate
Dating opt-in/preferences are additionally required for Dating. Test-mode
results never grant access. Keep the preview mode for fictional testing until
then. Configuring an adapter does not establish public launch readiness.

Provider references: [OAuth](https://developer.sheerid.com/tutorials/api-tokens-detail),
[secure creation](https://developer.sheerid.com/tutorials/secure-verification-creation),
[webhook signing](https://developer.sheerid.com/tutorials/verifications/webhooks),
[API quickstart](https://developer.sheerid.com/api-quickstart).

## Backups, restore and retention

Hosted backups are enabled by default: every 24 hours, retain three recognized
automatic copies under `/var/data/backups`. They include accounts, messages,
photos, reports and sessions. Each copy receives an integrity/content check,
a SHA-256 manifest and an isolated restore check. Files are owner-only; copies
are never served as public assets. The console supports **Create backup**,
**Verify a separate restore**, and password-confirmed **Download latest backup**.
Download to protected storage outside the hosting account, preferably encrypted,
and record the date/checksum and an expiry date. This is a sensitive database,
not a shareable export. Same-disk copies cannot protect against losing the disk.
A download does not automatically mark offsite recovery verified.

Server commands:

```sh
python -m campuslink.operations status
python -m campuslink.operations backup
python -m campuslink.operations restore-check
python -m campuslink.operations cleanup
```

`restore-check` restores into disposable storage and compares all table/image
contents; it never overwrites the live database. To verify an external copy on
a protected machine: `python -m campuslink.operations inspect --db
/absolute/path/to/downloaded.sqlite3`. Use a separately isolated staging server
for a full restored sign-in/message/photo exercise. Never start two servers
writing the live database or overwrite it while Uvicorn is running. During a
real recovery, stop the service first, retain the damaged database/WAL files
for investigation, restore the reviewed copy, reconcile later account deletions
and moderation changes, revoke copied sessions/reset tokens and resume only
after the isolated journey passes. Downgrading schema 6 to an old app is refused;
roll forward to a corrected release rather than run old code against new data.

Hourly cleanup removes expired sessions/email tokens, refresh events older than
24 hours, read notifications older than 30 days, abandoned unposted images older
than 24 hours, and completed mail metadata older than 7 days. Saved conversations,
published photos, reports and unread notifications are not pruned by cleanup.
Account deletion removes live account data and related conversation history;
backups retain earlier data until expiry/deletion. Record deletion requests so
a restore does not silently resurrect deleted accounts. Reports/audit retention
and any external backup retention require an approved operator policy.

A 1 GB disk also holds live photos, SQLite WAL and multiple backup/restore
copies. Check free space before inviting more testers; reduce storage use or
review an expansion before that disk fills. Low-storage backup failures retain
the last good copies and appear as failed operations. Code does not purchase
additional disk space or change the paid plan.

## Monitor and respond

The operator console exposes request counts, errors, latency percentiles,
active live streams, disk space and maintenance/email status. Request IDs link
server error reports without logging message bodies or reset tokens. Metrics
reset on process restart. `/api/health` checks service responsiveness, not full
student acceptance. Alerting outside the app is not configured: the operator
must check the console/logs, or connect an approved external uptime/error
service before broader use. Restrict any such service to public health and
aggregate metrics rather than account data.

Treat repeated 5xx responses, failed restore checks, exhausted email retries or
low disk space as reasons to pause new invitations and investigate. Record UTC
time, deployed commit, request ID and reproducible steps, excluding passwords,
identity documents and private conversation text. Follow the
[pilot plan](PILOT.md) and [phone guide](PHONE_TEST.md) before expanding access.

## Privacy and operator review

The support contact is configured; the operator's legal name and completed
privacy review have not been supplied. Set `CAMPUSLINK_OPERATOR_NAME` accurately.
Only set `CAMPUSLINK_PRIVACY_REVIEW_DATE` after an actual review. The UI's draft
notice describes stored information, receipts, staff access and backup retention.
It is not a legal compliance determination. Review controller/processor roles,
registration, provider data sharing, international storage, rights requests,
reports/audit retention and breach response against the applicable requirements
with qualified local advice. See the [Zambia Data Protection Commission](https://www.dataprotection.gov.zm/)
and its [controller/processor registration guide](https://www.dataprotection.gov.zm/wp-content/uploads/2025/03/Guide_Registration-of-Data-Controllers-and-Processors.pdf).
