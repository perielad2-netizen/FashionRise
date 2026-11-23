# Proposed Nginx allowlist — Runway weekly competitions

**Status:** required for Runway weekly categories / awards UI (`GET /api/v1/competitions/*`).

## Intent

- Permit authenticated reads for competition status, awards, and login streak.
- Permit streak check-in POST (no Star side effects when rewards are OFF).
- Permit pending award claim reads + claim POST (`/awards/pending`, `/awards/{uuid}/claim`).
- Keep the default `/api/` deny rule intact.

## Smallest FashionRise-only change

```nginx
    # Runway weekly competitions + login streak
    location = /api/v1/competitions/status {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/competitions/awards/pending {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/competitions/awards/[0-9a-fA-F-]{36}/claim$" {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/competitions/awards {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location ~ "^/api/v1/competitions/categories/[a-z0-9_]+/board$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/competitions/streak {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/competitions/streak/check-in {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }
```

Place these **before** `location /api/ { return 403; }`.
