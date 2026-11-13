# Proposed Nginx allowlist — Google OAuth

Live FashionRise HTTPS server currently allowlists:

```nginx
location ~ ^/api/v1/auth/(login|refresh|logout|me|cf-access/status|cf-access/login)$ {
```

## Change

Replace with:

```nginx
# Authentication and session endpoints (+ Google OAuth + optional CF Access SSO).
location ~ ^/api/v1/auth/(login|refresh|logout|me|account|stars|registration/status|verify-email|resend-verification|password-reset/status|forgot-password|reset-password|cf-access/status|cf-access/login|google/status|google/start|google/callback|google/native-handoff)$ {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Cf-Access-Jwt-Assertion $http_cf_access_jwt_assertion;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    client_max_body_size 2m;
    add_header Cache-Control "no-store" always;
}
```

Keep the existing `location = /api/v1/auth/register` POST allowlist unchanged.

## Apply

1. Backup: `cp /etc/nginx/sites-enabled/fashionrise.app /var/backups/fashionrise/nginx-google-auth-$(date -u +%Y%m%dT%H%M%SZ).conf`
2. Edit the auth regex as above
3. `nginx -t && systemctl reload nginx`
4. Probe: `curl -sS https://fashionrise.app/api/v1/auth/google/status` (after API deploy + Access off / bypass)

See also `GOOGLE-AUTH-NO-CF-ACCESS.md`.
