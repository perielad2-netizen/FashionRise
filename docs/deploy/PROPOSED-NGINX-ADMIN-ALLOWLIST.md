# Nginx allowlist — Admin console API (Admin 2.0)

**Status:** **APPLIED to production** (2026-11-25 / Admin 2.0 #503+#504 joint deploy). Keep this file as the canonical allowlist reference; do not broaden to unrestricted `/api/v1/admin/` prefix proxying.

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
| GET | `/api/v1/admin/stars/grants/config` | Effective grant limits (any AdminUser) |
| GET | `/api/v1/admin/stars/grants` | Grant aggregates (AdminUser; not revenue) |
| GET | `/api/v1/admin/stars/grants/idempotency/{key}` | Read-only grant reconciliation (**FinancialAdminUser**; actor-owned) |
| GET | `/api/v1/admin/users/{uuid}/stars/grants` | Per-recipient grant history |
| POST | `/api/v1/admin/users/{uuid}/stars/grants` | ADD-ONLY grant (**FinancialAdminUser** + UUID allowlist) |

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

    # Customer detail + classification PATCH (UUID path).
    # Quote regexes that contain `{n}` quantifiers — unquoted `{` is parsed as an nginx block.
    location ~ "^/api/v1/admin/customers/[0-9a-fA-F-]{36}$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/admin/customers/[0-9a-fA-F-]{36}/classification$" {
        limit_except PATCH OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/stars/grants/config {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/admin/stars/grants {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/admin/stars/grants/idempotency/[^/]+$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/admin/users/[0-9a-fA-F-]{36}/stars/grants$" {
        limit_except GET POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    # Deny-by-default for any other /api/v1/admin/* path.
    # IMPORTANT: do NOT use `^~` here. A `^~` prefix match short-circuits regex
    # evaluation and would suppress the UUID / idempotency allowlist locations
    # above. A plain prefix (no ^~) is only used after exact (=) and regex
    # locations fail to match, so allowlisted dynamic routes still win.
    location /api/v1/admin/ { return 403; }
```

SPA route: `https://fashionrise.app/admin` (web only; Capacitor redirects away).

Cloudflare: mirror the same path allowlist if API is fronted by CF Access / WAF exact-path rules. Do not broaden `/api/v1/admin/` to a prefix proxy without the trailing deny. Do not use a Cloudflare rule that prefix-matches `/api/v1/admin/` with an early deny ahead of the exact/regex allowlist.
