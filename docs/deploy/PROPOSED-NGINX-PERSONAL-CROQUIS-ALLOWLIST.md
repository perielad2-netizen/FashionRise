# Nginx allowlist — personal croquis / Create Model

**Status:** production FashionRise — applied live on `fashionrise.app` (2026-11-21). Keep in sync with the VPS `sites-enabled/fashionrise.app` personal-croquis block.

## Incident (Create Model “Unable to reach FashionRise”)

Android Create Model called `POST /api/v1/personal-croquis/consent/upload` after adults + storage consent. That path was **missing** from the nginx allowlist and fell through to:

```nginx
location /api/v1/personal-croquis/ { return 403; }
```

Browser CORS preflight (`OPTIONS`) got nginx 403 HTML → fetch failed as a network error → UI showed **“Unable to reach FashionRise. Check that the API is running.”** API journals never saw `/photos` because upload never started.

**Fix:** exact `location = /api/v1/personal-croquis/consent/upload` (POST/OPTIONS) proxied to `:8010`, same shape as `consent/storage` / `consent/ai`. Also added `…/{uuid}/publish` (POST/DELETE/OPTIONS) which FE uses and was previously catch-all denied.

## Required locations (FashionRise HTTPS server)

```nginx
    location = /api/v1/personal-croquis {
        limit_except GET POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        # … headers / timeouts …
        client_max_body_size 12m;
    }

    location = /api/v1/personal-croquis/attestations/adults {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/personal-croquis/consent/storage {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/personal-croquis/consent/ai {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/personal-croquis/consent/upload {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location = /api/v1/personal-croquis/photos {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        client_max_body_size 25m;
    }

    location ~ "^/api/v1/personal-croquis/assets/[0-9a-fA-F-]{36}/image$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}$" {
        limit_except GET DELETE OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/archive$" {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/publish$" {
        limit_except POST DELETE OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    # Try On Person male/female chooser for older Create Model rows without sex.
    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/sex$" {
        limit_except PATCH OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/versions/generate$" {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/versions/[0-9]+$" {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/versions/[0-9]+/(accept|reject)$" {
        limit_except POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
    }

    # Non-matching personal-croquis suffixes denied.
    location /api/v1/personal-croquis/ { return 403; }
```

## Matrix

| Request | Expected |
|---|---|
| `POST/OPTIONS …/consent/upload` | Proxied (Create Model agreement) |
| `POST/OPTIONS …/consent/storage` | Proxied |
| `POST/OPTIONS …/consent/ai` | Proxied |
| `POST/OPTIONS …/photos` | Proxied (body ≤ 25m) |
| `POST/DELETE/OPTIONS …/{uuid}/publish` | Proxied (My Models) |
| `PATCH/OPTIONS …/{uuid}/sex` | Proxied (Try On male/female chooser) |
| Unknown `…/personal-croquis/…` suffix | 403 |

Offline structural check: `backend/scripts/verify_nginx_personal_croquis_allowlist.py`.

## Live verification

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X OPTIONS \
  -H 'Origin: https://localhost' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type' \
  https://fashionrise.app/api/v1/personal-croquis/consent/upload
# expect 200 (not nginx 403 HTML)
```
