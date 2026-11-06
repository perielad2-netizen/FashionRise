# Google login / register — disable Cloudflare Access

FashionRise public auth is **login + register + Google (Gmail) Sign-In**.
Cloudflare Access (Zero Trust) should be **turned off** for `fashionrise.app` so the
SPA login page is reachable without an Access challenge.

## 1. Google Cloud OAuth client

1. Google Cloud Console → **APIs & Services → Credentials → Create credentials → OAuth client ID**
2. Application type: **Web application**
3. Name: `FashionRise production`
4. Authorized JavaScript origins:
   - `https://fashionrise.app`
5. Authorized redirect URIs:
   - `https://fashionrise.app/api/v1/auth/google/callback`
6. Copy **Client ID** and **Client secret**

Use the operator Gmail (`fashionriseapp@gmail.com`) as a project owner / test user
while the OAuth consent screen is in Testing.

## 2. Backend env (VPS `/opt/fashionrise/backend/.env`)

```bash
GOOGLE_OAUTH_CLIENT_ID=<client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<client-secret>
GOOGLE_OAUTH_REDIRECT_URI=https://fashionrise.app/api/v1/auth/google/callback
PUBLIC_APP_URL=https://fashionrise.app
GOOGLE_OAUTH_AUTO_REGISTER=true
CF_ACCESS_SSO_LOGIN=false
CF_ACCESS_JWT_VALIDATION=false
```

Restart API after writing env:

```bash
sudo systemctl restart fashionrise-api
# or the compose/unit name used on the VPS
```

Confirm:

```bash
curl -sS https://fashionrise.app/api/v1/auth/google/status
# {"google_oauth_enabled": true, "auto_register": true, ...}
```

## 3. Nginx allowlist

Extend the auth location regex so Google start/callback/status are proxied
(same server block as login/register):

```nginx
location ~ ^/api/v1/auth/(login|register|refresh|logout|me|cf-access/.*|google/.*)$ {
    # existing proxy_pass + proxy_set_header quartet
}
```

Or add explicit locations:

```nginx
location = /api/v1/auth/google/status { /* proxy */ }
location = /api/v1/auth/google/start { /* proxy */ }
location = /api/v1/auth/google/callback { /* proxy */ }
```

`nginx -t && systemctl reload nginx`

## 4. Disable Cloudflare Access (owner / Zero Trust)

This cannot be done from the app repo — do it in the Cloudflare dashboard:

1. **Zero Trust → Access → Applications**
2. Open the application that protects `fashionrise.app` (and `*.fashionrise.app` if any)
3. Either **Disable** the application or **Delete** it
4. Confirm visiting `https://fashionrise.app/login` shows FashionRise login **without**
   a Cloudflare email/OTP Access page
5. Keep DNS + SSL (orange cloud) as-is; only remove the Access policy gate

Optional: leave Access on a separate staging hostname if needed.

## 5. Frontend

Production builds already ship `/login`, `/register` (when UI enabled), and
`/auth/google/complete`. The **Continue with Google** button appears when
`GET /auth/google/status` reports `google_oauth_enabled: true`.

## 6. Behaviour

| Path | Result |
|---|---|
| Continue with Google (new Gmail) | Creates FashionRise user + session (auto_register) |
| Continue with Google (existing email) | Issues session for that user |
| Email + password | Unchanged |
| Invite register | Unchanged when registration UI + `REGISTRATION_ENABLED` |

## Rollback

Unset `GOOGLE_OAUTH_*` (or leave blank) and restart API — Google button disappears.
Re-enable the Cloudflare Access application if edge gating is required again.
