# Proposed Nginx allowlist — custom fabric library (WEB-V4C) (NOT applied)

**Status:** proposal only. Do **not** edit or reload production Nginx until Technical PM authorizes a FashionRise-scoped activation. This document records the verification result and the minimum allowlist needed for `/api/v1/fabrics`.

**Companion:** `docs/deploy/PROPOSED-NGINX-AI-ALLOWLIST.md`, `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`

## Goal

Allow authenticated Cloudflare Access clients (with FashionRise Authenticated Origin Pulls) to call **only**:

| Method | Path |
|--------|------|
| `POST` | `/api/v1/fabrics` |
| `GET` | `/api/v1/fabrics` |
| `GET` | `/api/v1/fabrics/{uuid}` |
| `DELETE` | `/api/v1/fabrics/{uuid}` |
| `GET` | `/api/v1/fabrics/{uuid}/image` |

without opening general `/api/`, public `/static/uploads`, upload routes, docs, or neighbor sites.

Fabric image bytes are **not** served from `/static/uploads` — they are stored under a private sibling directory and returned only by the owner-auth `…/image` route (`Cache-Control: private, no-store`).

## Verification (live FashionRise site — read-only `nginx -T`, 2026-10-22)

Production FashionRise Nginx (`server_name fashionrise.app`) uses **explicit route allowlisting**, not a generic `/api` proxy. Live locations observed:

| Location | Role |
|----------|------|
| `location = /api/v1/auth/register` (+ suffix deny) | Register POST allowlist |
| `location ~ ^/api/v1/auth/(login\|refresh\|logout\|me)$` | Auth session |
| `location ~ ^/api/v1/designs(?:/.*)?$` | Designs API |
| AI exact + jobs regex + `/api/v1/ai/` deny | Magic polish / job image |
| `location = /static/uploads` + `^~ /static/uploads/` → **403** | Public uploads denied |

**There is no `location` matching `/api/v1/fabrics`.** Without a new FashionRise-only allowlist entry, production Nginx will not proxy these endpoints even after the app/migration ship (edge deny / no match — not covered by designs or AI blocks).

Keep `/static/uploads` denied. Private fabric bytes live in a **sibling** of `uploads/` and must never be mounted.

## Minimum FashionRise-only allowlist (illustrative)

Place **inside** the FashionRise HTTPS `server` block only (same isolation rules as register/AI allowlists). Reuse the existing `proxy_set_header` overwrite quartet used on other FashionRise API locations:

```nginx
# --- FashionRise only: WEB-V4C private fabric library (apply only after PM auth) ---
# Deny trailing junk under /fabrics that is not a UUID resource.
location ^~ /api/v1/fabrics/ {
    # Handled by the regex below for UUID routes; this ^~ is NOT used when the
    # regex is preferred — keep a single regex location instead (recommended).
}

# Recommended: one regex covering collection + UUID + image.
location ~ ^/api/v1/fabrics(?:/?|[/\-][0-9a-fA-F-]{36}(?:/image)?/?)$ {
    limit_except GET POST DELETE {
        deny all;
    }

    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Host $host;

    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    # Matches app max_fabric_upload_size_mb (8) with headroom for multipart.
    client_max_body_size 10m;
    add_header Cache-Control "no-store" always;
}
```

Simpler equivalent (preferred if the site already uses separate exact + regex patterns like AI):

```nginx
location = /api/v1/fabrics {
    limit_except GET POST {
        deny all;
    }
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Host $host;
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    client_max_body_size 10m;
    add_header Cache-Control "no-store" always;
}

location ~ ^/api/v1/fabrics/[0-9a-fA-F-]{36}(/image)?$ {
    limit_except GET DELETE {
        deny all;
    }
    # DELETE is only meaningful on the asset root (not /image); app returns 405/404 otherwise.
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Host $host;
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    client_max_body_size 10m;
    add_header Cache-Control "no-store" always;
}
```

### Must not change

- Do **not** open `location /api/` or `location /api/v1/`.
- Do **not** mount or alias private fabric storage under `/static/uploads`.
- Do **not** add `location /static/uploads/fabrics` (bytes are not there).
- Do **not** edit PickWise / CureCompass / kehilabapark server blocks.
- Do **not** apply this allowlist in the same change as an unapproved deploy.

## Probe matrix (candidate config only)

| Request | Expected after allowlist |
|---------|--------------------------|
| `GET /api/v1/fabrics` (Bearer) | Proxied |
| `POST /api/v1/fabrics` (Bearer, multipart) | Proxied |
| `GET /api/v1/fabrics/{uuid}/image` (owner Bearer) | Proxied |
| `GET /api/v1/fabrics/{uuid}/image` (other user) | Proxied → app **404** |
| `DELETE /api/v1/fabrics/{uuid}` | Proxied |
| `PUT /api/v1/fabrics` | Denied (`limit_except`) |
| `GET /static/uploads/fabrics/...` | **404/403** (not a public fabric URL) |
| Neighbor vhosts | Unchanged (`nginx -T` isolation) |

## Activation order (separate authorization)

1. Merge WEB-V4C app code.
2. Backup FashionRise site file; apply allowlist on a candidate copy; `nginx -t`.
3. Deploy backend + run Alembic **`005`** (separate auth).
4. Reload Nginx only after PM approval.
5. Smoke: upload → owner image GET → cross-account 404 → static path denied.

**Rollback:** restore prior FashionRise Nginx file; reload. App can remain deployed with fabrics unreachable at the edge.
