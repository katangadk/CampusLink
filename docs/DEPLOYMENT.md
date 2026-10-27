# Hosted preview deployment

The preview website is <https://campuslink-staging.onrender.com>.
The 27 October update removes the shared tester password. Visitors open the
website directly and create or sign in to their own CampusLink accounts.
Profiles, photos, Feed and conversations still require account authentication
and their existing visibility, consent and block permissions.

The launch-work release `330ae53` deployed successfully on 27 October 2026 at
13:48:44 UTC. The live catalog exposes the new approval tools; private operator
routes require sign-in. Email/provider credentials and the actual owner-role
grant remain setup tasks.

The source repository is <https://github.com/katangadk/CampusLink>. Publish
source only: databases, images, sessions, secrets, backups and private workspace
metadata remain excluded. Local use remains supported.

## Update the existing Render service

1. Open the `campuslink-staging` web service in Render.
2. Choose **Manual Deploy → Deploy latest commit**. If selecting a particular
   commit, select the reviewed launch-work update on `main`; record its exact commit in the acceptance log.
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

## Owner, email and recovery setup

After deploying the launch-work update, follow [OPERATIONS.md](OPERATIONS.md).
Create your own account, grant it operator access from the trusted Render shell,
then approve membership in the console. The first grant activates hosted `auto`
approvals, including for existing preview accounts; it does not introduce a shared
website password. The Blueprint configures the supplied support email, an independent
mail token key and three scheduled backups. It does not configure SMTP credentials,
buy a verification account, or prove that those settings exist on the current service.

Set SMTP secrets privately in Render and confirm actual email receipt. Use the
operator console for backups, isolated restore checks and password-confirmed backup
downloads. Protect a separate offsite copy; server copies alone cannot recover disk
loss. The runbook covers expiry/retention, staff revocation, restore procedures,
monitoring and optional external verification. Schema 6 refuses an old-app downgrade;
use a reviewed roll-forward correction if needed. Existing one-worker/disk settings
and paid resources are unchanged.

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
