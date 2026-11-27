# Proposed Nginx allowlist — Native Push devices

**Status:** required for Capacitor Android/iOS device registration.  
**Root cause (2026-11-27):** production nginx allowlisted only `GET /api/v1/push/native/capability`.  
`POST|GET|DELETE /api/v1/push/native/devices` fell through to `location /api/ { return 403; }`, so Capacitor CORS preflight (`OPTIONS`, Origin `https://localhost`) returned **nginx 403** and the authenticated POST never reached FastAPI.  
Web Push (`/push/vapid-public-key`, `/push/subscriptions`) was already allowlisted and unaffected.

## Required block (insert next to capability / web push)

```nginx
    # Native push — FCM/APNs device registration (Capacitor)
    location = /api/v1/push/native/capability {
        limit_except GET OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }

    location = /api/v1/push/native/devices {
        limit_except GET POST DELETE OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }
```

Insert **above** the final `location /api/ { return 403; }` catch-all. Do not broaden to a `/api/v1/push/` prefix.

## Smoke (after reload)

```bash
# Must be 204/200 with CORS Allow-Origin for Capacitor
curl -sS -o /dev/null -w '%{http_code}\n' -X OPTIONS \
  'https://fashionrise.app/api/v1/push/native/devices' \
  -H 'Origin: https://localhost' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type'

# Unauthenticated POST should reach FastAPI (401), not nginx 403
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  'https://fashionrise.app/api/v1/push/native/devices' \
  -H 'Origin: https://localhost' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Expected: OPTIONS **200** (CORS OK); POST without auth **401** (app), never nginx HTML 403.
