# Proposed Nginx allowlist — invite registration (NOT applied)

**Status:** proposal only. Do **not** edit or reload production Nginx until Technical PM authorization for Stage D **and** Decision Gate 0 verification completes.

**Companion:** `docs/deploy/WEB-V3B-TRUST-BOUNDARY.md`

## Goal

Allow authenticated Cloudflare Access clients (with FashionRise Authenticated Origin Pulls) to call **only**:

`POST /api/v1/auth/register`

without opening general `/api/` access, other methods on that path, or public registration — and forward a **validated visitor IP** to FastAPI for SlowAPI.

## Current production deny (unchanged today)

```nginx
location = /api/v1/auth/register { return 403; }
location ^~ /api/v1/auth/register/ { return 403; }
```

Current proxied auth/designs blocks use:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

`$remote_addr` is the Cloudflare edge. `$proxy_add_x_forwarded_for` **appends** and must not remain once trusting headers.

## Decision Gate 0 — Option B (preferred)

Use `ngx_http_realip_module` (**confirmed present** on the VPS) **inside the FashionRise HTTPS `server` block only**.

1. `set_real_ip_from` each current official Cloudflare IPv4/IPv6 CIDR (never `0.0.0.0/0`).
2. `real_ip_header CF-Connecting-IP;`
3. Optionally `real_ip_recursive on;` only if CF chain shape requires it — verify with packet/header capture before relying on it.
4. After real_ip runs, `$remote_addr` becomes the visitor IP for trusted peers; `$realip_remote_addr` retains the connecting edge.
5. On **every** FashionRise proxied API location, **overwrite** (do not append):

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header Host $host;
```

6. Then set `TRUST_PROXY_HEADERS=true` on `fashionrise-api` (separate restart authorization).

### FashionRise-scoped real_ip snippet (illustrative)

Place **inside** `server { … server_name fashionrise.app … }` for the HTTPS listener — **not** in `http {}` global context — so PickWise / CureCompass / kehilabapark are unaffected:

```nginx
# --- FashionRise only: Cloudflare real_ip (update CIDRs from cloudflare.com/ips-v4|v6) ---
# Example prefixes only — replace with the full current lists before Stage D.
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
# ... all current IPv4 ...
set_real_ip_from 2400:cb00::/32;
# ... all current IPv6 ...
real_ip_header CF-Connecting-IP;
```

### Register POST allowlist (after real_ip in same server)

```nginx
location ^~ /api/v1/auth/register/ { return 403; }

location = /api/v1/auth/register {
    limit_except POST {
        deny all;
    }

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

Apply the **same** `proxy_set_header` overwrite quartet to:

- `location ~ ^/api/v1/auth/(login|refresh|logout|me)$`
- `location ~ ^/api/v1/designs(?:/.*)?$`
- the new register location

Remove the old `location = /api/v1/auth/register { return 403; }` only when the POST proxy block is installed.

### Inheritance / isolation checklist

| Check | Requirement |
|---|---|
| Scope | `set_real_ip_from` / `real_ip_header` only under fashionrise.app HTTPS `server` |
| `nginx -T` | Confirm no other `server` inherits FashionRise real_ip |
| `proxy_set_header` | Explicit on each proxied location (do not rely on unclear inheritance for XFF) |
| Other apps | PickWise, CureCompass, kehilabapark configs unchanged |
| AOP | Keep `ssl_verify_client on` + FashionRise private CA path |

### Precedence probes (staging or approved window)

- `POST /api/v1/auth/register` → proxied (still behind Access + AOP; app flag may still forbid)
- `GET /api/v1/auth/register` → denied by `limit_except`
- `POST /api/v1/auth/register/extra` → 403
- Other `/api/…` → 403 unless already allowlisted
- See negative tests in `WEB-V3B-TRUST-BOUNDARY.md` §4

## Rejected designs

| Design | Why |
|---|---|
| Option A: unconditional `$http_cf_connecting_ip` | Trusts header without proving peer ∈ Cloudflare ranges |
| `X-Real-IP $remote_addr` **without** real_ip | Keys on CF edge / shared buckets |
| `$proxy_add_x_forwarded_for` once trusting headers | Appends client-influenced chain |
| `set_real_ip_from 0.0.0.0/0` | Trusts all peers |

## Upstream rate limiting

- `TRUST_PROXY_HEADERS=false` (default): ASGI peer ≈ `127.0.0.1` behind Nginx → **shared bucket**. Unacceptable for registration activation.
- `TRUST_PROXY_HEADERS=true`: keys on single `X-Real-IP` after Nginx overwrite from real_ip-normalized `$remote_addr`.

Backend parser must use strict `ipaddress` validation (separate draft code PR).

## Application / Access gates still required

- `REGISTRATION_ENABLED` stays false until the approved activation window.
- Invitations remain mandatory.
- Custom AOP is FashionRise-private (not global) — still add Access JWT origin validation plan per trust-boundary doc before claiming Access-bound origin.
- Frontend: enable `VITE_REGISTRATION_UI_ENABLED` only after server gates work.

## Frontend route

`/register` is SPA `try_files` under `location /` — no Nginx change for the page itself (still behind Access + AOP).
