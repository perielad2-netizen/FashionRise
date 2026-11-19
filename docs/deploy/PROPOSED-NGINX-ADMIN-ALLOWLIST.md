# Nginx allowlist — Admin console API

Add **before** the catch-all `location /api/ { return 403; }` on `fashionrise.app`.

```nginx
    # FashionRise web admin console (username allowlist on API)
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

    location ^~ /api/v1/admin/ { return 403; }
```

SPA route: `https://fashionrise.app/admin` (web only; Capacitor redirects away).
