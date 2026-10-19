# FashionRise family-beta deployment runbook (INFRA-2 preflight)

**Date:** 2026-10-19  
**Status:** Documentation only. **No VPS change in this step.**  
**Merged product SHA on `main`:** `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0`  
**Approved application commit (PR #9, second parent):** `5e70dc76d851219b1b1d881169bc0af761c9b62c`

This file records the intended protected family-beta shape and a **read-only** audit. It does not authorize restarting services, copying a build, editing Nginx, changing DNS, opening registration, or enabling paid Magic.

Do not paste credentials, private keys, API tokens, JWT secrets, or database passwords into this document, tickets, or chat logs. If a command would print a secret, redact it before sharing the output.

## Confirmed in git (this repository)

| Item | Fact |
|------|------|
| Product client | `web-ui/` React/TypeScript PWA. Routes in production builds: `/`, `/login`, `/studio`. Design-lab is DEV-only. |
| API | FastAPI under `backend/`, prefix `/api/v1`. |
| Schema head in git | Alembic revision **`003`** (`003_user_follows`). PR #9 did not add a migration. |
| Same-origin API base to build | `VITE_API_BASE_URL=/api/v1` |
| Magic | Studio control stays a later-milestone notice. No paid OpenAI call from the web client. |
| Custom references | Session-only blob preview. Persistent upload is disabled in the client because `/static/uploads` is not owner-private. |
| Public registration in the UI | Login page only. There is no signup screen in `web-ui`. |
| Repo deploy templates | `deploy/fashionrise.service` still shows user `fashionrise`, port **8000**, unit name `fashionrise`. `deploy/nginx_fashionrise.conf` proxies every path to that port. **Treat those files as templates, not as the live host.** |
| Production safety in code | `ENVIRONMENT=production` rejects a default `SECRET_KEY`, a short key, `CORS_ORIGINS=*`, and `DEBUG=true`. |

## Operator-reported host facts (not independently inspected)

PM recorded these from operator logs. The audit below must re-check them before any change. They are not a license to edit the host.

| Item | Operator report |
|------|-----------------|
| OS | Ubuntu 24.04 |
| App user | `fashionriseapp` |
| Checkout | `/opt/fashionrise/src`, previously pinned to `2fc4c1fa` |
| Database | `fashionrise_beta`, reported at Alembic `003` |
| API | systemd unit `fashionrise-api`, bound to `127.0.0.1:8010` |
| Edge | Cloudflare Access and zone Authenticated Origin Pulls reported configured; certificate DNS-01 renewal dry-run reported successful |
| Current public behavior | App and API return **origin 403**. Leave that 403 in place until a later explicit approval. |

PickWise and synagogue services are out of scope. The audit may **list** their unit and site names to prove they were not selected. Do not restart, reload, or edit them.

## Target architecture (proposed, not applied)

```text
Family browser
  -> Cloudflare Access (apex and www allowlist only)
  -> Full (strict) TLS + Authenticated Origin Pulls
  -> Nginx on the FashionRise origin
       -> static web root for the Vite build
       -> /api/v1/* (approved routes only) -> 127.0.0.1:8010
       -> deny register, uploads, AI, and API docs
  -> fashionrise-api (FastAPI, loopback only)
  -> PostgreSQL database fashionrise_beta
```

Direct origin requests that do not present a valid Authenticated Origin Pull must keep failing. Do not publish the origin IP as a public bypass.

### Same-origin web build

Build on a trusted machine, not by loosening permissions on the server secret directory:

```bash
cd web-ui
# VITE_API_BASE_URL=/api/v1
npm ci
npm run build
```

The value must be exactly `/api/v1` so the browser calls the same host as the page. Do not bake `http://127.0.0.1:8001` or a separate API hostname into the family-beta bundle.

Static files come from `web-ui/dist/`. Copy them only after the audit records the live Nginx `root` (or `alias`) for `fashionrise.app` and `www`. Do not place the build inside the backend environment directory, and do not change mode bits on that environment file.

### Family tester accounts

1. Keep public `POST /api/v1/auth/register` denied at Nginx.
2. Create only the named family accounts from the operator's private list, using a **loopback** call to `127.0.0.1:8010` or the existing backend password helper `backend/scripts/set_user_password.py` after the row exists.
3. Do not commit emails, usernames, or passwords. Do not add a public signup control.
4. After the accounts work on loopback, confirm the public registration URL still returns 403.

### Explicit denials for this beta

Nginx for the FashionRise site must keep returning 403 for:

| Path | Why |
|------|-----|
| `/api/v1/auth/register` | No public signup. |
| `/static/uploads` and `/api/v1/uploads` | Uploaded images are not owner-private. Custom references stay session-only. |
| `/api/v1/ai` | Paid Magic / sketch pipeline stays off. |
| `/docs` and `/openapi.json` | No public developer API documentation. |

Also set the API process so the AI worker does not run and no paid image/chat call is made (`AI_WORKER_ENABLED=false`; do not place an OpenAI key in the shell history or in git). The web Magic button already does not call the API.

Approved beta traffic is login, session refresh, logout, `/auth/me`, and owner-scoped design read/write used by Studio autosave, plus `/health` and `/ready` on loopback for the operator.

## Safety gates before the 403 is lifted

All of these stay closed until a later PM/operator approval:

1. Cloudflare Access allowlist verified for **apex and www** (exact emails checked in the dashboard, not copied here).
2. Zone Authenticated Origin Pulls enforced at the origin; SSL/TLS mode Full (strict); a direct-origin request without the pull certificate is rejected.
3. Live unit is `fashionrise-api` on `127.0.0.1:8010` only, database name `fashionrise_beta`, Alembic current is `003`.
4. Nginx still denies the paths in the table above and does not proxy them to the app.
5. Static bundle was built with `VITE_API_BASE_URL=/api/v1`.
6. Family accounts exist; public registration still 403.
7. A database backup exists even though this merge adds no migration.
8. Rollback SHA and the previous static tree are recorded.
9. PickWise and synagogue units/sites are unchanged.

## Rollback

| Layer | Action when a later deploy is reverted |
|-------|----------------------------------------|
| Git | Checkout the previously recorded production SHA. Before this preflight the operator pin was `2fc4c1fa`. After a future deploy, the rollback SHA is whatever `git rev-parse HEAD` showed **before** the update. |
| Static files | Keep the previous web root as a sibling directory and point Nginx back only under a separate approval. |
| Database | This merge does not revise Alembic past `003`. Do not run a downgrade as part of preflight. If a later migration ships, restore from the backup taken immediately before that migration. |
| Edge | The current origin 403 configuration is the safe rollback target. Do not delete it. |
| API process | Do not restart it during this preflight. A later rollback restarts only `fashionrise-api` after the checkout is back on the old SHA. |

## Read-only VPS audit

Run these on the FashionRise host as an operator. They are inspect-only. Do not `systemctl restart` or `reload`, do not `nginx -s reload`, do not `alembic upgrade`, do not copy `dist/`, do not edit site files, and do not print `.env`.

### 1. Checkout

```bash
sudo -u fashionriseapp git -C /opt/fashionrise/src rev-parse HEAD
sudo -u fashionriseapp git -C /opt/fashionrise/src status --porcelain
sudo -u fashionriseapp git -C /opt/fashionrise/src branch --show-current
```

Record the SHA. Expected before a later deploy: the old pin `2fc4c1fa` or whatever is actually checked out. Desired after a later approved deploy: `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0`. A dirty tree stops the deploy.

### 2. FastAPI service

```bash
systemctl status fashionrise-api --no-pager
systemctl show fashionrise-api -p User -p Group -p FragmentPath -p WorkingDirectory -p ExecStart -p EnvironmentFiles
sudo ss -ltnp | awk '/8010|8000/'
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/ready
```

Confirm the process listens on `127.0.0.1:8010` only. `/ready` checks the database; a failure is a stop, not a prompt to edit config in this phase. Do not `cat` the environment file. If you must confirm flags, use a redacting check such as `sudo systemctl show fashionrise-api -p Environment` and omit any line that contains a URL with a password, a key, or a token before pasting it into a ticket.

### 3. Database migration

```bash
sudo -u fashionriseapp bash -lc 'cd /opt/fashionrise/src/backend && . .venv/bin/activate && alembic current'
```

Adjust the venv path only if `systemctl show` recorded a different `WorkingDirectory` or `ExecStart`. Expected current revision: `003`. Do not upgrade.

### 4. Nginx and static destination

```bash
sudo nginx -t
sudo nginx -T | awk 'BEGIN{p=0} /server_name/ {p=0} /fashionrise/ {p=1} p'
```

From that snippet, record without secrets:

- `server_name` values (apex and www)
- `root` or `alias` for the static site (this is the build destination)
- every `proxy_pass` (FashionRise must be `http://127.0.0.1:8010` only)
- whether `return 403` or `deny` still covers the whole site
- whether these locations are denied: `/api/v1/auth/register`, `/static/uploads`, `/api/v1/uploads`, `/api/v1/ai`, `/docs`, `/openapi.json`

Also list other site files so PickWise and synagogue are visible and untouched:

```bash
ls -l /etc/nginx/sites-enabled
```

Do not open those other files for editing.

### 5. Cloudflare Access, origin authentication, and the 403

In the Cloudflare dashboard (read-only review):

- Access application covers `fashionrise.app` and `www.fashionrise.app`.
- The allowlist is the intended family set. Do not copy the list into git.
- SSL/TLS mode is Full (strict).
- Authenticated Origin Pulls are on for the zone and required by the origin listener.

From a network that is **not** the origin itself, a request that skips Cloudflare should fail. Do not disable the pull to test it. Record the HTTP status of `https://fashionrise.app/` (expected **403** until a later approval).

### 6. Isolation

```bash
systemctl list-units --type=service --state=running --no-pager
```

Note `fashionrise-api` versus any PickWise or synagogue units. This preflight does not restart any of them.

## Precise next steps

1. PM reviews this runbook.
2. Operator runs the read-only audit and pastes redacted results (SHA, unit bind, Alembic current, Nginx root, 403 status). No secrets.
3. Only after that approval: build with `VITE_API_BASE_URL=/api/v1`, back up the database, deploy static files to the recorded web root, fast-forward `/opt/fashionrise/src` to `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0`, and restart **only** `fashionrise-api` if the code checkout changed.
4. Provision family accounts on loopback, then re-check public registration is still 403.
5. A separate approval is required before replacing the origin-wide 403 with the limited route policy.
6. Then verify `/login` and `/studio` on live HTTPS, including owner-scoped autosave and refresh, on a desktop browser and a tablet.

**STOP. Do not change the VPS in this step.**
