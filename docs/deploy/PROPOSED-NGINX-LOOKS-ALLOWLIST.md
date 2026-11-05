# Proposed Nginx allowlist — My Looks API

**Status:** production FashionRise — keep in sync with live `fashionrise.app` looks locations.

## Intent

- Permit authenticated `GET /api/v1/looks` (list).
- Permit authenticated `GET|PATCH|DELETE /api/v1/looks/{uuid}` (detail / metadata / tombstone delete).
- Keep image bytes on the existing authenticated AI job image route (`/api/v1/ai/jobs/{id}/image`).
- Do not add public/static look image URLs.

## Smallest FashionRise-only change

```nginx
    # My Looks — owner-scoped gallery metadata (no public images)
    location = /api/v1/looks {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/looks/[0-9a-fA-F-]{36}$" {
        limit_except GET PATCH DELETE { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }
```

## Matrix

| Request | Expected |
|---|---|
| `GET /api/v1/looks` | Proxied |
| `GET /api/v1/looks/{uuid}` | Proxied |
| `PATCH /api/v1/looks/{uuid}` | Proxied |
| `DELETE /api/v1/looks/{uuid}` | Proxied |
| `POST /api/v1/looks` | Denied |
| `POST /api/v1/looks/{uuid}` | Denied |

Offline structural check: `backend/scripts/verify_nginx_looks_allowlist.py`.
