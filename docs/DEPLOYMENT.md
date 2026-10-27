# Hosted preview deployment

The preview website is <https://campuslink-staging.onrender.com>.
The 27 October update removes the shared tester password. Visitors open the
website directly and create or sign in to their own CampusLink accounts.
Profiles, photos, Feed and conversations still require account authentication
and their existing visibility, consent and block permissions.

The source repository is <https://github.com/katangadk/CampusLink>. Publish
source only: databases, images, sessions, secrets, backups and private workspace
metadata remain excluded. Local use remains supported.

## Update the existing Render service

1. Open the `campuslink-staging` web service in Render.
2. Choose **Manual Deploy → Deploy latest commit**. If selecting a particular
   commit, use the update titled **Open hosted website without shared tester login**.
3. Wait for that deployment to become **Live**. Cancel any old browser password
   popup, then open <https://campuslink-staging.onrender.com> again.
4. The landing page and **Create account / Sign in** pages should open directly.
   There is no shared access form, tester username or site-wide password.
5. Create an individual test account. Supplied local Alice/Brian/moderator
   fixtures are not available online; the hosted database is separate.

Existing `CAMPUSLINK_STAGING_USERNAME` and `CAMPUSLINK_STAGING_PASSWORD` values
are ignored by the updated application. There is no need to reset them or
share them. Old `/tester-access` bookmarks redirect to the website.

The current workspace has no Render deployment connection. A GitHub push alone
does not prove the service has updated. Confirm the deployed commit and direct
page behavior on the actual URL.

## Create a service from the Blueprint

1. Sign in to Render and connect the GitHub account for `katangadk/CampusLink`.
2. Choose **New → Blueprint**, branch `main`, Blueprint path `render.yaml`.
3. Review the paid compute/storage estimate before creation. The Blueprint
   defines one Python service (`0.5c-512mb`) and a 1 GB disk at `/var/data`.
   Keep one instance. Automatic code deployments are off.
4. Keep build command `pip install -r requirements.txt` and start command
   `python -m campuslink.serve`. Do not seed the database during deployment.
5. Render supplies `RENDER_EXTERNAL_URL`; CampusLink uses that HTTPS origin.
   Check `/api/health`: expect `status: ok`, `mode: staging` and
   `public_launch_ready: false`. The last value records unfinished launch work.
6. Open the website directly and test separate individual accounts.

The Python version is specified in [.python-version](../.python-version).
The persistent disk holds SQLite accounts, sessions, messages and processed
images. Deploying a service with a disk causes a brief interruption.

## Settings

Set these in the hosting environment; the app does not load `.env` files itself.
The [.env.staging.example](../.env.staging.example) contains no actual secrets.

| Variable | Value or behavior |
| --- | --- |
| `CAMPUSLINK_MODE` | `staging` for the hosted preview. |
| `CAMPUSLINK_DB` | `/var/data/campuslink.sqlite3`; absolute, separate from local `data/`. |
| `CAMPUSLINK_BASE_URL` | Optional canonical HTTPS origin for a custom domain; defaults to Render's `RENDER_EXTERNAL_URL`. |
| `CAMPUSLINK_TRUSTED_PROXY_IPS` | The launcher trusts Render ingress; elsewhere configure actual proxy IPs/networks. |
| `PORT` | Assigned by Render; one worker listens on this port. |

HTTPS and canonical-host checks remain enforced. Account cookies are
Secure/HttpOnly, writes retain CSRF and origin checks, and preview responses
remain no-store/no-index. The supplied demo database and seed command are
refused online. Production mode and real eligibility verification remain
separate from opening the preview website.

## Recovery email

Recovery remains unavailable until configured. Set `CAMPUSLINK_SMTP_HOST`,
`CAMPUSLINK_SMTP_PORT` (normally 587), `CAMPUSLINK_SMTP_FROM` and any required
SMTP user/password in Render. Test actual mailbox delivery. Recovery links
open the reset page directly and do not require a tester password.

## Back up and rehearse restore

Run a consistent backup from Render's service shell:

```sh
python -m campuslink.backup /var/data/backups/campuslink-2026-10-27.sqlite3
```

Use a fresh filename. The backup command creates an owner-only file, checks
integrity and refuses overwrites. Accounts, sessions, messages and image bytes
are included. Download a secure external copy; a backup on the same disk does
not protect against losing that disk. Never commit backups to GitHub.

Restore a copy into a separate test database/service, then check sign-in,
profiles, images and history. Do not overwrite a live database while Uvicorn
is using it.

## Hosted acceptance checks

- Landing, signup, sign-in and required assets return 200 without credentials
  or redirects to a shared access page. There is no native password challenge.
- Private APIs, photos and live events return 401 until an account signs in.
- Registration/login, wrong-password errors, logout and refresh work over HTTPS;
  Secure/HttpOnly cookies persist and invalid-CSRF/cross-origin writes fail.
- Two independent accounts discover, match, exchange Sent/Delivered/Read messages,
  and handle private comment requests under recipient control.
- Photos persist across redeployment, offline retry saves one message, and
  unmatch, Dating deactivation and block revoke access in both clients.
- Complete hosted backup/restore and actual Android/mobile-data checks in
  [PHONE_TEST.md](PHONE_TEST.md). Temporary TLS browser tests do not close them.

After future changes, deploy the reviewed commit and repeat the two-account
message/photo check. Local automated results and the actual hosted result are
recorded separately in [VALIDATION.md](VALIDATION.md).

Real student/adult verification, recovery delivery, operational support,
privacy review and consenting student trials remain in [CHECKLIST.md](../CHECKLIST.md).

## Provider references

- [Render FastAPI hosting](https://render.com/docs/deploy-fastapi)
- [Render deploy options](https://render.com/docs/deploys)
- [Render Blueprint fields](https://render.com/docs/blueprint-spec)
- [Render persistent disks](https://render.com/docs/disks)
- [Render automatic URL variables](https://render.com/docs/environment-variables)
- [FastAPI proxy headers](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
