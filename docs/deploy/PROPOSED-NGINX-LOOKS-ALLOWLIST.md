# Proposed Nginx allowlist — My Looks API

**Status:** apply on FashionRise production only after BE My Looks (`GET/PATCH /api/v1/looks`) is deployed and verified. Narrow owner-scoped gallery routes; does not open unrelated API surfaces.

## Intent

- Permit authenticated `GET /api/v1/looks` (list) and `GET|PATCH /api/v1/looks/{uuid}` (detail / metadata).
- Keep image bytes on the existing authenticated AI job image route (`/api/v1/ai/jobs/{id}/image`).
- Do not add public/static look image URLs.

## Smallest FashionRise-only change

Place **before** any catch-all deny for unknown `/api/v1/` paths:

```nginx
    # My Looks — owner-scoped gallery metadata (no public images)
    location = /api/v1/looks {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/looks/[0-9a-fA-F-]{36}$" {
        limit_except GET PATCH { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }
```

## Matrix

| Request | Expected |
|---|---|
| `GET /api/v1/looks` | Proxied |
| `GET /api/v1/looks/{uuid}` | Proxied |
| `PATCH /api/v1/looks/{uuid}` | Proxied |
| `POST /api/v1/looks` | Denied |
| `DELETE /api/v1/looks/{uuid}` | Denied |
| `GET /api/v1/looks/{uuid}/extra` | Denied (no match) |

Offline structural check: `backend/scripts/verify_nginx_looks_allowlist.py`.
