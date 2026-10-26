# Proposed Nginx allowlist — Create Real Design (techpacks)

**Status:** candidate for production FashionRise — apply with BE deploy for Issue #83.

## Intent

- Permit authenticated techpack draft CRUD + PDF export/download.
- Keep PDF bytes on the private authenticated route (never `/static/uploads`).
- Deny sibling/extra paths under `/api/v1/techpacks/`.

## Smallest FashionRise-only change

```nginx
    # Create Real Design — owner-scoped techpack drafts + private PDF
    location = /api/v1/techpacks {
        limit_except GET POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}$" {
        limit_except GET PATCH { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/export$" {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/exports$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }
```

## Matrix

| Request | Expected |
|---|---|
| `GET /api/v1/techpacks` | Proxied |
| `POST /api/v1/techpacks` | Proxied |
| `GET /api/v1/techpacks/{uuid}` | Proxied |
| `PATCH /api/v1/techpacks/{uuid}` | Proxied |
| `POST /api/v1/techpacks/{uuid}/export` | Proxied |
| `GET /api/v1/techpacks/{uuid}/exports` | Proxied |
| `GET /api/v1/techpacks/exports/{uuid}/pdf` | Proxied |
| `DELETE /api/v1/techpacks/{uuid}` | Denied |
| `POST /api/v1/techpacks/{uuid}/ai-draft` | Denied at edge (API also 403) |

Offline structural check: `backend/scripts/verify_nginx_techpacks_allowlist.py`.
