# Proposed Nginx allowlist — FashionRise Runway (gallery / social)

**Status:** required for web Runway feed (`GET /api/v1/gallery`).

## Intent

- Permit public community feed + item detail (auth optional for `liked_by_me`).
- Permit like / unlike, comments, ratings, and profile follow routes used by social phase.
- Keep the default `/api/` deny rule intact.

## Smallest FashionRise-only change

```nginx
    # FashionRise Runway — public gallery feed + social actions
    location = /api/v1/gallery {
        limit_except GET POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/gallery/user/[0-9a-fA-F-]{36}$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/gallery/[0-9a-fA-F-]{36}/comments$" {
        limit_except GET POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/gallery/[0-9a-fA-F-]{36}/like$" {
        limit_except POST DELETE { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/gallery/[0-9a-fA-F-]{36}$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/ratings {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/ratings/gallery/[0-9a-fA-F-]{36}$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/profiles/me {
        limit_except GET PUT { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/profiles/me/following-ids {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/profiles/[0-9a-fA-F-]{36}/follow-status$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/profiles/[0-9a-fA-F-]{36}/follow$" {
        limit_except POST DELETE { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/profiles/[0-9a-fA-F-]{36}$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }
```

Insert these blocks **above** the final `location /api/ { return 403; }` catch-all.
