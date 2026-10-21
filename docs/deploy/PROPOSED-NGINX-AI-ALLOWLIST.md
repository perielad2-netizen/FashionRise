# Proposed Nginx allowlist — Magic AI routes (NOT applied)

**Status:** documentation only. Do **not** edit production Nginx until Technical PM / operator authorization for WEB-V4A Magic activation.

**Companion:** `docs/deploy/REGISTRATION-ACTIVATION.md` (registration already live); this note is FashionRise-only AI routing.

## Goal

Allow authenticated Cloudflare Access clients (with FashionRise AOP) to call **only**:

- `POST /api/v1/ai/sketch/polish`
- `GET /api/v1/ai/jobs/*` (job status + authenticated image)

without opening general `/api/v1/ai`, uploads, docs, or public `/static/uploads`.

## Current production deny (unchanged today)

```nginx
location = /api/v1/ai { return 403; }
location ^~ /api/v1/ai/ { return 403; }

location = /static/uploads { return 403; }
location ^~ /static/uploads/ { return 403; }
```

Keep `/static/uploads` **denied**. React Magic retrieves look images via:

`GET /api/v1/ai/jobs/{job_id}/image` (Bearer + job ownership).

## Smallest FashionRise-only change (future activation)

Inside the FashionRise HTTPS `server` block, **replace** the blanket AI deny with:

```nginx
# Keep uploads public path closed — Magic uses authenticated job image route.
location = /static/uploads { return 403; }
location ^~ /static/uploads/ { return 403; }

# Deny AI prefix children except explicit allowlist below.
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

# Job status + authenticated image (GET only).
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

# Everything else under /api/v1/ai stays closed.
location ^~ /api/v1/ai/ { return 403; }
```

Do **not** enable `CF_ACCESS_JWT_VALIDATION` or `TRUST_PROXY_HEADERS` as part of Magic activation unless separately authorized.

## Frontend gate

Rebuild `web-ui` with `VITE_MAGIC_UI_ENABLED=true` only after the Nginx allowlist and backend worker/`OPENAI_API_KEY` are approved for the activation window.

## Rollback

1. Restore AI + static-upload deny blocks.  
2. Rebuild frontend with `VITE_MAGIC_UI_ENABLED=false` (or prior release).  
3. Leave completed `ai_jobs` rows and on-disk files in place.
