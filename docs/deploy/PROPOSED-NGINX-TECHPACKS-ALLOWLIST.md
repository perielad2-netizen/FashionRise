# Proposed Nginx allowlist — Create Real Design (techpacks) V2

**Status:** candidate for Create Real Design V2 deploy — keep in sync with live `fashionrise.app`.

## Intent

- Permit authenticated techpack draft CRUD + PDF export/download.
- Permit explicit AI status / confirm / generate / run-status routes (paid AI still fail-closed in API without spend ceiling).
- Keep PDF bytes on the private authenticated route (never `/static/uploads`).
- Deny sibling/extra paths under `/api/v1/techpacks/` including legacy `/ai-draft`.

## Smallest FashionRise-only change

```nginx
    # Create Real Design — owner-scoped techpack drafts + private PDF + gated AI
    location = /api/v1/techpacks {
        limit_except GET POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/techpacks/ai/status {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/ai/runs/[0-9a-fA-F-]{36}$" {
        limit_except GET { deny all; }
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

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/confirm$" {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate$" {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate-professional$" {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/latest-run$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/techpacks/artifacts/[0-9a-fA-F-]{36}/image$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }
```

## Matrix

| Request | Expected |
|---|---|
| `GET /api/v1/techpacks` | Proxied |
| `POST /api/v1/techpacks` | Proxied |
| `GET /api/v1/techpacks/ai/status` | Proxied |
| `GET /api/v1/techpacks/ai/runs/{uuid}` | Proxied |
| `GET /api/v1/techpacks/{uuid}` | Proxied |
| `PATCH /api/v1/techpacks/{uuid}` | Proxied |
| `POST /api/v1/techpacks/{uuid}/export` | Proxied |
| `GET /api/v1/techpacks/{uuid}/exports` | Proxied |
| `POST /api/v1/techpacks/{uuid}/ai/confirm` | Proxied |
| `POST /api/v1/techpacks/{uuid}/ai/generate` | Proxied |
| `POST /api/v1/techpacks/{uuid}/ai/generate-professional` | Proxied (V3.1 one-tap) |
| `GET /api/v1/techpacks/{uuid}/ai/latest-run` | Proxied (V3.1 resume) |
| `GET /api/v1/techpacks/exports/{uuid}/pdf` | Proxied |
| `DELETE /api/v1/techpacks/{uuid}` | Denied |
| `POST /api/v1/techpacks/{uuid}/ai-draft` | Denied at edge (API also 403) |

Offline structural check: `backend/scripts/verify_nginx_techpacks_allowlist.py`.
