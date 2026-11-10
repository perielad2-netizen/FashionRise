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
| Publish | ASC upload via `publishing.app_store_connect` (`auth: integration`, **`codemagic access`**) — **no** beta review / App Store review / `beta_groups` |
| Build number | `CFBundleVersion = PROJECT_BUILD_NUMBER + IOS_BUILD_NUMBER_OFFSET(100)`; require positive `PROJECT_BUILD_NUMBER`; **fail closed** if ASC/TestFlight latest ≥ stamp (raise offset). Marketing version stays **1.0**. Exactly **one** IPA artifact (no staging copies — avoids 90189 duplicate upload) |
| Helpers | `scripts/codemagic-set-ios-build-number.sh` · `scripts/codemagic-verify-ios-ipa.sh` · `scripts/assert-codemagic-ios-yaml.py` |

**Codemagic env group `fashionrise_native` (required):** production-approved croquis notice texts that `assert-prod-vite-flags` hashes:

- `VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT`
- `VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT`
- `VITE_MY_CROQUIS_AI_NOTICE_TEXT`

(same copy / SHA256 as live web production builds; see `web-ui/scripts/assert-prod-vite-flags.mjs`)

## Server config before live IAP credits

```env
# backend/.env — do not commit secrets
# Phase A: StoreKit 2 JWS via App Store Server Library (legacy shared secret unused).
IAP_APPLE_BUNDLE_ID=app.fashionrise.studio
IAP_APPLE_APP_APPLE_ID=6832116469
IAP_APPLE_ONLINE_CHECKS=true
# Both default OFF until Phase B.
# purchasing = initiate new StoreKit buys; credit = confirm/reconcile completed Apple txns.
IAP_APPLE_PURCHASING_ENABLED=false
IAP_APPLE_CREDIT_ENABLED=false
# Designated FashionRise emails that may Buy + confirm while public gates stay OFF.
# Keep short (sandbox Testers only). Empty = no allowlist bypass.
IAP_APPLE_SANDBOX_TESTER_EMAILS=
IAP_APPLE_SHARED_SECRET=
# ASC In-App Purchase API key (outbound Server API / TEST notifications). .p8 outside repo.
IAP_APPLE_ASC_ISSUER_ID=
IAP_APPLE_ASC_KEY_ID=
IAP_APPLE_ASC_PRIVATE_KEY_PATH=/var/lib/fashionrise/secrets/apple-iap/AuthKey_<KEYID>.p8
IAP_GOOGLE_SERVICE_ACCOUNT_JSON=
# Forced off in production. Phase A also refuses unverified Apple credits in non-prod.
IAP_ALLOW_UNVERIFIED_SANDBOX=false
```

**Controlled sandbox (public purchasing stays OFF):** set `IAP_APPLE_SANDBOX_TESTER_EMAILS` to the FashionRise account email(s) used on the TestFlight device. Authenticated `GET /shop/iap/apple/status` returns `purchasing_enabled`/`credit_enabled` true only for those emails; anonymous and other users still see gates OFF. Do **not** flip the public `IAP_APPLE_*_ENABLED` flags until the sandbox matrix passes.

See `docs/deploy/APPLE-IAP-ASC-API-KEY.md` for secure `.p8` install steps.

Also add Capacitor origins to production `CORS_ORIGINS` if the WebView origin is not already covered (e.g. `capacitor://localhost`, `https://localhost`).

Nginx: allowlist `POST /api/v1/shop/iap/confirm`, `POST /api/v1/shop/iap/restore`, and `GET /api/v1/shop/iap/app-account-token` (same pattern as other `/shop` routes).

Apple root CAs for chain verify ship in-repo at `backend/app/certs/apple/*.cer` (public PKI — not secrets).

## Submission checklist (first release)

- [ ] Privacy policy URL (required by both stores)  
- [ ] Screenshots (phone + tablet)  
- [ ] Age rating / content questionnaire  
- [ ] IAP products created & approved as **Consumable** (`stars_50` / `stars_150` / `stars_500`)  
- [ ] Test on TestFlight + Play internal testing  
- [x] Phase A: Apple JWS verification foundation (purchasing + credit gates still **OFF**)  
- [x] Phase B: ASN refunds + native shop UI deployed (public gates still **OFF**)  
- [ ] Controlled sandbox via `IAP_APPLE_SANDBOX_TESTER_EMAILS` (public gates stay OFF)  
- [ ] After sandbox matrix: enable public `IAP_APPLE_CREDIT_ENABLED` then `IAP_APPLE_PURCHASING_ENABLED`  
- [ ] Submit FashionRise **1.0** with consumables `stars_50` / `stars_150` / `stars_500` together  


## What we are not doing

- No Stripe / custom card UI in the store apps  
- No Unity republish — `FashionRise/` Unity plugins are legacy  
- Web PWA remains for browser; store apps are the Capacitor shell
