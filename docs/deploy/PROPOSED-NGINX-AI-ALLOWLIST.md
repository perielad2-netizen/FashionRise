# Proposed Nginx allowlist — Magic AI routes (NOT applied)

**Status:** **applied in production** on 2026-10-21 as part of WEB-V4A Magic activation (`dc9e31aa`). Live config uses a **quoted** job regex (`location ~ "^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$"`) so nginx does not misparse `{36}`. Sibling AI routes and `/static/uploads` remain denied. Operator browser Magic generation acceptance still PENDING.

**Companion:** `docs/deploy/REGISTRATION-ACTIVATION.md` (registration already live); this note is FashionRise-only AI routing.

## Goal

Allow authenticated Cloudflare Access clients (with FashionRise AOP) to call **only**:

- `POST /api/v1/ai/sketch/polish`
- `GET /api/v1/ai/jobs/{uuid}`
- `GET /api/v1/ai/jobs/{uuid}/image`

without opening general `/api/v1/ai`, sibling AI routes, uploads, docs, or public `/static/uploads`.

## Current production deny (unchanged today)

```nginx
location = /api/v1/ai { return 403; }
location ^~ /api/v1/ai/ { return 403; }

location = /static/uploads { return 403; }
location ^~ /static/uploads/ { return 403; }
```

Keep `/static/uploads` **denied**. React Magic retrieves look images via:

`GET /api/v1/ai/jobs/{job_id}/image` (Bearer + job ownership).

## Nginx precedence (critical)

Do **not** use a final `location ^~ /api/v1/ai/ { return 403; }` alongside a regex jobs rule.

With `^~`, Nginx stops after the longest matching prefix and **never evaluates** the jobs regex, so GET status/image would stay denied.

Correct pattern:

1. Exact `=` locations (polish POST, bare `/api/v1/ai` deny).
2. Regex `~` for GET job + GET job image.
3. Plain prefix `location /api/v1/ai/` (**no** `^~`) as catch-all deny for sibling AI routes.

## Smallest FashionRise-only change (future activation)

Inside the FashionRise HTTPS `server` block, **replace** the blanket AI deny with:

```nginx
# Keep uploads public path closed — Magic uses authenticated job image route.
location = /static/uploads { return 403; }
location ^~ /static/uploads/ { return 403; }

location = /api/v1/ai { return 403; }

location = /api/v1/ai/sketch/polish {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 120s;
    client_max_body_size 12m;
    add_header Cache-Control "no-store" always;
}

# Job status + authenticated image (GET only). Must be regex so it beats
# the plain prefix deny below (do not mark the deny with ^~).
location ~ ^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$ {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    add_header Cache-Control "no-store" always;
}

# Sibling AI routes stay closed. Plain prefix (no ^~) so regex jobs still match.
location /api/v1/ai/ { return 403; }
```

Do **not** enable `CF_ACCESS_JWT_VALIDATION` or `TRUST_PROXY_HEADERS` as part of Magic activation unless separately authorized.

## Pre-activation routing / method matrix (isolated)

Run against an isolated candidate config (never production) with `nginx -t`, then method probes:

| Request | Expected |
|---|---|
| `POST /api/v1/ai/sketch/polish` | Proxied (allowlist) |
| `GET /api/v1/ai/sketch/polish` | Denied (`limit_except`) |
| `GET /api/v1/ai/jobs/{uuid}` | Proxied (regex) |
| `GET /api/v1/ai/jobs/{uuid}/image` | Proxied (regex) |
| `POST /api/v1/ai/jobs/{uuid}` | Denied (`limit_except`) |
| `POST /api/v1/ai/sketch/clean` | **403** (prefix deny) |
| `GET /api/v1/ai/jobs` | **403** (prefix deny) |
| `GET /static/uploads/...` | **403** |
| Neighbor vhosts | Untouched |

Automated check: `backend/scripts/verify_nginx_ai_allowlist.py` (writes a temp conf, runs `nginx -t`, asserts location precedence comments/matrix expectations).

## Frontend gate

Rebuild `web-ui` with `VITE_MAGIC_UI_ENABLED=true` only after the Nginx allowlist and backend worker/`OPENAI_API_KEY` are approved for the activation window.

## Rollback

1. Restore AI + static-upload deny blocks.  
2. Rebuild frontend with `VITE_MAGIC_UI_ENABLED=false` (or prior release).  
3. Leave completed `ai_jobs` rows and on-disk files in place.
