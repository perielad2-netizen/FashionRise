# Proposed Nginx allowlist — profile followers / following

**Why:** FashionRise nginx uses an explicit API allowlist. Without these locations, `GET /api/v1/profiles/{id}/followers` (and `/following`) returns **403**, and the web client shows the generic “sketch is unchanged” copy.

**Applied on VPS:** 2026-11-17 (Asia/Jerusalem) for tip after #399 followers sheet.

Insert **before** the existing `follow-status` profile location:

```nginx
    location ~ "^/api/v1/profiles/[0-9a-fA-F-]{36}/followers$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/profiles/[0-9a-fA-F-]{36}/following$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }
```

Verify:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  "https://fashionrise.app/api/v1/profiles/<user-uuid>/followers"
# expect 200 (or 401 if auth required by CF Access — not 403 from nginx)
```
