# Password reset (forgot password) — activation

Code ships with **`PASSWORD_RESET_ENABLED=false`**. The login screen shows **Forgot password?** only when the API reports `password_reset_available: true` (flag on **and** SMTP configured). Do not flip the flag until SMTP can send mail.

## Email provider (exact env)

FashionRise uses the existing **SMTP** delivery path (`EMAIL_DELIVERY_BACKEND=smtp`). No SendGrid/Resend SDK.

Set on the API host (`/opt/fashionrise/src/backend/.env`):

```bash
# Required to show the link and send mail
PASSWORD_RESET_ENABLED=true

EMAIL_DELIVERY_BACKEND=smtp
SMTP_HOST=<your-smtp-host>          # e.g. smtp.gmail.com, email-smtp.<region>.amazonaws.com
SMTP_PORT=587                       # or 465 for SMTPS
SMTP_USERNAME=<smtp-user>           # omit only for unauthenticated local relays
SMTP_PASSWORD=<smtp-password>
SMTP_USE_TLS=true                   # required when SMTP_USERNAME is set (unless port 465)
SMTP_FROM_EMAIL=noreply@fashionrise.app
SMTP_FROM_NAME=FashionRise

# Optional tuning (defaults shown)
PASSWORD_RESET_TOKEN_TTL_MINUTES=60
PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS=60

# Reset links use this origin (fragment token — never query-string)
PUBLIC_APP_URL=https://fashionrise.app
```

**Provider checklist**

1. Choose an SMTP relay you already trust (Google Workspace SMTP, Amazon SES SMTP, Mailgun SMTP, etc.).
2. Authorize `SMTP_FROM_EMAIL` (SPF/DKIM on the sending domain).
3. Confirm TLS: STARTTLS on 587 **or** implicit TLS on 465.
4. Send a test message from the VPS before enabling the flag.

Capture backend (`EMAIL_DELIVERY_BACKEND=capture`) is **tests-only** and never counts as configured in `ENVIRONMENT=production`.

## Nginx (required before activation)

Extend the auth allowlist regex with:

`password-reset/status|forgot-password|reset-password`

Canonical snippet: `docs/deploy/PROPOSED-NGINX-GOOGLE-AUTH-ALLOWLIST.md`.

```bash
# Probe after nginx reload (expect JSON, not 403)
curl -sS https://fashionrise.app/api/v1/auth/password-reset/status
```

## Release plan

### 1. Backend (web API)

1. Deploy main tip containing migration **029** + password-reset routes.
2. `alembic upgrade head` (creates `password_reset_tokens`).
3. Restart `fashionrise-api`.
4. Leave `PASSWORD_RESET_ENABLED=false` until SMTP is verified.
5. Patch nginx allowlist; `nginx -t && systemctl reload nginx`.
6. Probe: `GET /api/v1/auth/password-reset/status` → `password_reset_available: false`.

### 2. Frontend (website)

1. Deploy `web-ui` build that includes `/forgot-password`, `/reset-password`, and the gated login link.
2. Confirm login has **no** Forgot password? link while the flag is off.
3. After SMTP + `PASSWORD_RESET_ENABLED=true` + API restart: link appears; request → email → `/reset-password#token=…` → new password → signed in.

### 3. iOS / Android (Capacitor)

Reset links are **HTTPS** (`PUBLIC_APP_URL/reset-password#token=…`), same as email verification — no new custom-scheme intent required.

| Surface | Behavior |
|---------|----------|
| Website | Full flow in browser |
| iOS / Android (email app opens link) | Opens Safari/Chrome → set password on web → use new password (or Google) in the installed app |
| Installed app WebView | If the user navigates to `/forgot-password` inside the shell after activation, same SPA works |

Ship a native AAB/IPA only when you want the Forgot password? link inside the shell UI (needs FE build + API already activated). **No store rebuild is required** for the email link itself once the website SPA is live.

### 4. Activation (after SMTP works)

1. Set `PASSWORD_RESET_ENABLED=true` with working SMTP vars.
2. `systemctl restart fashionrise-api`
3. Confirm `password_reset_available: true`.
4. End-to-end: request reset for a test account → open link → login with new password on web and in the Android/iOS app.

## Security notes

- Single-use, hashed tokens; fragment handoff (token not in access logs).
- Opaque `204` on forgot-password (no account enumeration) when available.
- SlowAPI: `5/minute;20/hour` on forgot, `20/minute;60/hour` on reset; plus per-email cooldown.
- Successful reset revokes all prior refresh sessions and issues a new pair.
