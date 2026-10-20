# Proposed Nginx allowlist — invite registration (NOT applied)

**Status:** proposal only. Do **not** edit or reload production Nginx until Technical PM approval after WEB-V3B merge and the permanent PWA/service-worker fix (PR #16) is integrated.

## Goal

Allow authenticated Cloudflare Access clients (with Authenticated Origin Pulls) to call:

`POST /api/v1/auth/register`

without opening general `/api/` access or public registration.

## Current production deny (unchanged today)

```nginx
location = /api/v1/auth/register { return 403; }
location ^~ /api/v1/auth/register/ { return 403; }
```

## Proposed replacement

Extend the existing auth regex allowlist (login|refresh|logout|me) to include `register`, **or** add an explicit proxy location matching only that path:

```nginx
location = /api/v1/auth/register {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    client_max_body_size 2m;
    add_header Cache-Control "no-store" always;
}
```

Remove the dedicated `return 403` register locations once the proxy location is in place.

Keep:

- `ssl_verify_client on` (AOP)
- Cloudflare Access in front of the hostname
- Default-deny `location /api/`
- Denies for AI, uploads, docs, OpenAPI, Gallery

## Application gate still required

Even after Nginx allows the route, `REGISTRATION_ENABLED` must remain **false** until the approved activation window. Invitations remain mandatory.

## Frontend route

`/register` is static SPA content under the existing `location /` try_files — no Nginx change required for the page itself (still behind Access + AOP).
