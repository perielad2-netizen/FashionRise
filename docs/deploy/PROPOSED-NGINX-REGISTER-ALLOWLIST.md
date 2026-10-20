# Proposed Nginx allowlist — invite registration (NOT applied)

**Status:** proposal only. Do **not** edit or reload production Nginx until Technical PM approval after WEB-V3B merge and the permanent PWA/service-worker fix (PR #16) is integrated.

## Goal

Allow authenticated Cloudflare Access clients (with Authenticated Origin Pulls) to call **only**:

`POST /api/v1/auth/register`

without opening general `/api/` access, other methods on that path, or public registration.

## Current production deny (unchanged today)

```nginx
location = /api/v1/auth/register { return 403; }
location ^~ /api/v1/auth/register/ { return 403; }
```

## Proposed replacement

1. Keep **exact-path** matching for `/api/v1/auth/register`.
2. Keep **suffix deny** for `/api/v1/auth/register/…`.
3. Allow **POST only**; reject other methods on that path.
4. Preserve default-deny `location /api/`.
5. Preserve Cloudflare Access and `ssl_verify_client on` (AOP).
6. Overwrite forwarding headers with the real peer so FastAPI rate limits cannot be spoofed.

```nginx
# Suffix paths under register remain denied.
location ^~ /api/v1/auth/register/ { return 403; }

# Exact path only — method-gated.
location = /api/v1/auth/register {
    limit_except POST {
        deny all;
    }

    # Trustworthy client IP for upstream rate limiting:
    # overwrite (do not append) so clients cannot forge X-Forwarded-For.
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Host $host;

    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    client_max_body_size 2m;
    add_header Cache-Control "no-store" always;
}
```

Remove the old `location = /api/v1/auth/register { return 403; }` once the proxy block above is installed.

Leave all of the following unchanged:

- `ssl_verify_client on` / AOP client certificate
- Cloudflare Access in front of the hostname
- `location /api/ { return 403; }` default deny
- Denies for AI, uploads, docs, OpenAPI, Gallery
- Existing allowlist for `login|refresh|logout|me` and designs

### Precedence note (verify on a staging Nginx before production)

Exact `location =` beats prefix `^~` for the identical path; the suffix `^~ /api/v1/auth/register/` continues to deny nested paths. After editing a staging config, run `nginx -T` and confirm only one intended register location remains, then probe:

- `POST /api/v1/auth/register` → proxied (still behind Access + AOP)
- `GET /api/v1/auth/register` → denied by `limit_except`
- `POST /api/v1/auth/register/extra` → 403
- Other `/api/…` → 403 unless already allowlisted

## Upstream rate limiting (activation requirement)

SlowAPI keys on `client_ip_key`:

- `TRUST_PROXY_HEADERS=false` (default today): uses the direct ASGI peer. Behind Nginx that is almost always `127.0.0.1`, so **every user shares one login / refresh / register bucket**. Do **not** activate registration (or leave production in this mode after any allowlist change) without fixing client IP.
- `TRUST_PROXY_HEADERS=true`: keys on a single `X-Real-IP` value. Safe **only** when Nginx **overwrites** that header with `$remote_addr` (never appends client-supplied XFF).

**Required before flipping `TRUST_PROXY_HEADERS=true` in production:**

1. Apply the same header overwrite snippet to **every** proxied API location that hits SlowAPI — at minimum `login`, `refresh`, `logout`, `me`, `register`, and designs — not only register:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
```

2. Confirm with a staging probe that two distinct Access clients receive distinct `X-Real-IP` values upstream and do not exhaust a shared `30/minute` login bucket.
3. Then set `TRUST_PROXY_HEADERS=true` on `fashionrise-api` and restart only that unit.

Leave `TRUST_PROXY_HEADERS=false` if the API is ever exposed without that Nginx sanitization — forged `X-Forwarded-For` is ignored by design.

## Application gate still required

Even after Nginx allows POST, `REGISTRATION_ENABLED` must remain **false** until the approved activation window. Invitations remain mandatory.

## Frontend route

`/register` is static SPA content under the existing `location /` try_files — no Nginx change required for the page itself (still behind Access + AOP).
