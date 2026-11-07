# FashionRise — App Store & Play Store deploy

The **web app is the product**. Capacitor wraps `web-ui/dist` for native shells.  
**Apple and Google own payments** (In‑App Purchase / Play Billing). We only verify purchases and credit Stars.

## What landed in the repo

| Piece | Path |
|--------|------|
| Capacitor config | `web-ui/capacitor.config.ts` — app id `app.fashionrise.studio` |
| Native build env | `web-ui/.env.native` — absolute API URL |
| Scripts | `npm run build:native` · `cap:sync` · `cap:android` · `cap:ios` |
| IAP client | `web-ui/src/services/native/iap.ts` (`@capgo/native-purchases`) |
| IAP server | `POST /api/v1/shop/iap/confirm` + `iap_purchases` (Alembic 024) |

## You must create (outside the repo)

1. **Apple Developer Program** ($99/yr) → App Store Connect app + IAP products  
2. **Google Play Console** ($25 one-time) → app + in-app products  
3. Signing: Apple certificates/profiles · Android upload keystore  

Product IDs (must match both stores and code). Set **price** in each store console:

| Product ID | Name | Stars | Price (USD) | Was |
|------------|------|------:|------------:|----:|
| `stars_50` | Starter | 50 | $4.99 | $5.99 |
| `stars_150` | Creator | 150 | $12.99 | $16.99 |
| `stars_500` | Studio | 500 | $34.99 | $49.99 |

## Local / CI commands

```bash
cd web-ui
npm install
npm run cap:sync          # build:native + cap sync into android/ + ios/
npm run cap:android       # opens Android Studio (needs Android SDK)
npm run cap:ios           # opens Xcode (macOS only)
```

- **Android AAB:** Android Studio → Build → Generate Signed Bundle  
- **iOS IPA:** Xcode → Product → Archive → Distribute (requires Mac)

## Server config before live IAP credits

```env
# backend/.env — do not commit secrets
IAP_APPLE_SHARED_SECRET=
IAP_GOOGLE_SERVICE_ACCOUNT_JSON=
# Dev only (never production):
IAP_ALLOW_UNVERIFIED_SANDBOX=false
```

Also add Capacitor origins to production `CORS_ORIGINS` if the WebView origin is not already covered (e.g. `capacitor://localhost`, `https://localhost`).

Nginx: allowlist `POST /api/v1/shop/iap/confirm` and `POST /api/v1/shop/iap/restore` (same pattern as other `/shop` routes).

## Submission checklist (first release)

- [ ] Privacy policy URL (required by both stores)  
- [ ] Screenshots (phone + tablet)  
- [ ] Age rating / content questionnaire  
- [ ] IAP products created & approved  
- [ ] Test on TestFlight + Play internal testing  
- [ ] Wire Apple/Google receipt verification (currently staged fail-closed)  

## What we are not doing

- No Stripe / custom card UI in the store apps  
- No Unity republish — `FashionRise/` Unity plugins are legacy  
- Web PWA remains for browser; store apps are the Capacitor shell
