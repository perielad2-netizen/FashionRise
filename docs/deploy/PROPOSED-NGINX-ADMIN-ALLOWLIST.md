# Nginx allowlist — Admin console API (Admin 2.0)

**Status:** Proposed only — do **not** apply to production edge until Technical PM authorizes deploy.

Add **before** the catch-all `location /api/ { return 403; }` on `fashionrise.app`.

Exact locations required by Admin 2.0 (beyond the original overview + reports):

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/admin/overview` | Audience + range query params |
| GET | `/api/v1/admin/reports` | Moderation queue |
| GET | `/api/v1/admin/metrics/dictionary` | Metric definitions |
| GET | `/api/v1/admin/customers` | Directory pagination |
| GET | `/api/v1/admin/customers/{uuid}` | Customer 360 |
| PATCH | `/api/v1/admin/customers/{uuid}/classification` | Audited classification |
| GET | `/api/v1/admin/classification/dry-run` | Non-mutating suggestions |
| GET | `/api/v1/admin/classification/options` | Enum list |

```nginx
    # FashionRise Admin 2.0 console (username allowlist + is_admin on API)
    location = /api/v1/admin/overview {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/reports {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/metrics/dictionary {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/customers {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/classification/dry-run {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/classification/options {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    # Customer detail + classification PATCH (UUID path)
    location ~ ^/api/v1/admin/customers/[0-9a-fA-F-]{36}$ {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ ^/api/v1/admin/customers/[0-9a-fA-F-]{36}/classification$ {
        limit_except PATCH OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ^~ /api/v1/admin/ { return 403; }
```

SPA route: `https://fashionrise.app/admin` (web only; Capacitor redirects away).

Cloudflare: mirror the same path allowlist if API is fronted by CF Access / WAF exact-path rules. Do not broaden `/api/v1/admin/` to a prefix proxy without the trailing deny.
