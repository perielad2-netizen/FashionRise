# Proposed Nginx allowlist — Stars shop + Apple IAP Phase B

Add alongside existing FashionRise HTTPS allowlists. Do **not** open a broad
`/api/v1/shop/` prefix — keep exact locations.

```nginx
# Stars shop catalog (public) + cart (auth).
location = /api/v1/shop/packages {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
}

location ~ ^/api/v1/shop/cart(?:/items|/checkout)?$ {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    client_max_body_size 1m;
    add_header Cache-Control "no-store" always;
}

# Apple IAP — authenticated account token + confirm/restore (Phase A/B).
location = /api/v1/shop/iap/app-account-token {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
}

location = /api/v1/shop/iap/apple/status {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 15s;
    add_header Cache-Control "no-store" always;
}

location = /api/v1/shop/iap/confirm {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    client_max_body_size 1m;
    add_header Cache-Control "no-store" always;
}

location = /api/v1/shop/iap/restore {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
}

# App Store Server Notifications V2 — public to Apple, cryptographically authenticated.
# Keep this exact path only; do not broaden to /shop/iap/*.
location = /api/v1/shop/iap/apple/notifications {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    client_max_body_size 1m;
    add_header Cache-Control "no-store" always;
}
```

Also allow `GET /api/v1/auth/stars` by extending the auth regex:

```nginx
location ~ ^/api/v1/auth/(login|refresh|logout|me|stars|cf-access/status|cf-access/login|google/status|google/start|google/callback)$ {
```

## Cloudflare

- ASN webhook must be reachable from Apple without FashionRise user session cookies.
- Prefer a Cloudflare WAF exception / Access bypass for
  `POST /api/v1/shop/iap/apple/notifications` only (path-exact).
- Do not disable WAF globally.
- Confirm/restore/app-account-token remain authenticated FashionRise JWT routes.

## Production preflight note (2026-11-10)

Verified live nginx already allowlisted `confirm` + `restore` but **not**
`app-account-token`, `apple/status`, or `apple/notifications`. Those must be
added before Phase B deploy enablement.
