# Proposed Nginx allowlist — saved-design DELETE (Issue #17)

**Status:** apply on FashionRise production only after BE `DELETE /api/v1/designs/saved/{uuid}` is deployed and verified. Narrows designs DELETE at the edge; does not open unrelated routes.

## Goal

- Permit **only** authenticated `DELETE /api/v1/designs/saved/{uuid}` for My Designs deletion.
- Stop proxying generic `DELETE /api/v1/designs/{uuid}` at Nginx (FastAPI route remains for internal/generic consumers behind the edge).
- Keep existing designs `GET` / `POST` / `PUT` behaviour unchanged.

## Candidate locations (FashionRise HTTPS server only)

Place the **saved** location **before** the general designs regex:

```nginx
    # Issue #17 — saved-design delete only (owner + type enforced by FastAPI).
    location ~ "^/api/v1/designs/saved/[0-9a-fA-F-]{36}$" {
        limit_except DELETE {
            deny all;
        }
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

    # Owner-scoped design API — GET/POST/PUT only (no edge DELETE).
    location ~ ^/api/v1/designs(?:/.*)?$ {
        limit_except GET POST PUT {
            deny all;
        }
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

## Method matrix

| Request | Expected |
|---|---|
| `DELETE /api/v1/designs/saved/{uuid}` | Proxied |
| `GET /api/v1/designs/saved/{uuid}` | Denied (405/403) |
| `DELETE /api/v1/designs/{uuid}` | Denied at edge |
| `GET/POST /api/v1/designs` / `GET /designs/my` / `PUT /designs/{uuid}` | Proxied as today |

Offline structural check: `backend/scripts/verify_nginx_saved_delete_allowlist.py`.
