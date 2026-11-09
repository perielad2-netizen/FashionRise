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

| Product ID | Name | Stars | Price (USD) |
|------------|------|------:|------------:|
| `stars_50` | Starter | 50 | $5.99 |
| `stars_150` | Creator | 150 | $16.99 |
| `stars_500` | Studio | 500 | $49.99 |

## Local / CI commands

```bash
cd web-ui
npm install
npm run cap:sync          # build:native + cap sync into android/ + ios/
npm run cap:android       # opens Android Studio (needs Android SDK)
npm run cap:ios           # opens Xcode (macOS only)
```

- **Android AAB:** Android Studio → Build → Generate Signed Bundle  
- **iOS IPA (local):** Xcode → Product → Archive → Distribute (requires Mac)  
- **iOS IPA (Codemagic):** root `codemagic.yaml` → workflow **FashionRise iOS (App Store IPA)** — manual start only; no TestFlight / App Store submit

### Codemagic iOS (first App Store IPA)

| Item | Value (from repo — do not guess) |
|------|----------------------------------|
| Config | `/codemagic.yaml` |
| Workflow | `fashionrise-ios-app-store` |
| Working dir | `web-ui` |
| Workspace | `web-ui/ios/App/App.xcworkspace` |
| Scheme / target | `App` |
| Bundle ID | `app.fashionrise.studio` |
| ASC Apple ID | `6832116469` |
| Signing | Codemagic `ios_signing` `app_store` + ASC API key integration `codemagic access` (credentials in Codemagic UI, not GitHub) |
| Trigger | Manual only (no `triggering:` block) |
| Publish | None — download IPA from the build page |
| Build number floor | Codemagic stamps **ASC/TestFlight latest + 1** (primary). Repo `MIN_IOS_BUILD_NUMBER=13` is a safety floor, auto-bumped on each `main` merge (workflow + `./scripts/bump-min-ios-build-number.sh`) |

**Codemagic env group `fashionrise_native` (required):** production-approved croquis notice texts that `assert-prod-vite-flags` hashes:

- `VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT`
- `VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT`
- `VITE_MY_CROQUIS_AI_NOTICE_TEXT`

(same copy / SHA256 as live web production builds; see `web-ui/scripts/assert-prod-vite-flags.mjs`)

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
