# Proposed Nginx allowlist — Stars shop

Add alongside existing FashionRise HTTPS allowlists:

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
```

Also allow `GET /api/v1/auth/stars` by extending the auth regex:

```nginx
location ~ ^/api/v1/auth/(login|refresh|logout|me|stars|cf-access/status|cf-access/login|google/status|google/start|google/callback)$ {
```
