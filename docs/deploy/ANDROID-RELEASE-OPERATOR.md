# Android release operator checklist — FCM + Play Billing + App Links

Do **not** commit private credentials (`google-services.json`, service-account JSON, keystores).

Package: `app.fashionrise.studio` · Track: Play **Internal / closed testing** (preserve testers).

## A. Firebase native push (FCM)

1. Firebase Console → add Android app `app.fashionrise.studio` (or confirm existing).
2. Download `google-services.json`.
3. Codemagic → team/group `fashionrise_native`:
   - Secure file **or** env `GOOGLE_SERVICES_JSON` / path `CM_GOOGLE_SERVICES_JSON`.
   - Workflow injects into `web-ui/android/app/google-services.json` before `bundleRelease` (never artifacts).
4. Create GCP/Firebase service account with **Firebase Cloud Messaging Admin**.
5. On API host only (outside repo), e.g. `/var/lib/fashionrise/secrets/fcm-sa.json`.
6. Production `.env` (fail-closed until both flag + files):
   - `NATIVE_PUSH_ANDROID_ENABLED=true`
   - `NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON=/var/lib/fashionrise/secrets/fcm-sa.json`
   - `NATIVE_PUSH_FCM_PROJECT_ID=<firebase-project-id>`
7. Restart `fashionrise-api` + `fashionrise-ai-worker@{1..3}`.
8. Smoke: signed-in Android build → Runway bell ON → capability `android_enabled=true` → like → tap opens `/studio…`.

Do **not** change Web Push or iOS APNs flags in this checklist.

## B. Google Play Billing (Stars)

Products (consumable, same as Apple): `stars_50` · `stars_150` · `stars_500`.

1. Play Console → Monetize → create/activate the three in-app products (consumable).
2. Link a Play Developer API service account (Android Publisher) with access to this app.
3. Store JSON on API host: `IAP_GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/play-sa.json`.
4. Gates (default OFF in code; set only when ready):
   - License testers first: `IAP_GOOGLE_LICENSE_TESTER_EMAILS=you@…` (FashionRise account emails).
   - Keep `IAP_GOOGLE_PURCHASING_ENABLED=false` / `IAP_GOOGLE_CREDIT_ENABLED=false` until license-tester smoke passes.
   - Then enable public gates if authorized.
5. RTDN: Play Console → Monetization setup → Real-time developer notifications → Pub/Sub topic → push subscription to  
   `https://fashionrise.app/api/v1/shop/iap/google/notifications`  
   Set `IAP_GOOGLE_RTDN_AUDIENCE` to that exact URL; leave `IAP_GOOGLE_RTDN_VERIFY_OIDC=true`.
6. Nginx must allowlist `POST` on that path (see shop allowlist docs).
7. Admin revenue: Play license-test purchases map to `environment=Sandbox` and stay excluded from Production revenue.

Never trust client Stars/price. Credit only after `purchases.products.get` · purchaseState=Purchased · account bind · durable purchase-token idempotency · then client `consumePurchase`.

## C. Android App Links (Digital Asset Links)

1. Play Console → App integrity → **App signing key certificate** → copy **SHA-256** (not upload key).
2. Write `/var/www/fashionrise/well-known/assetlinks.json` with that fingerprint and package `app.fashionrise.studio`.
3. Nginx must serve `/.well-known/assetlinks.json` (and AASA) with **200**, JSON, **no redirect**, before any `location ~ /\.` deny.
4. Same file for `www.fashionrise.app` (both hosts declared in the manifest).
5. Cloudflare: exclude Access/WAF challenge on `/.well-known/*` if needed.
6. Verify: Digital Asset Links API / `adb shell pm get-app-links app.fashionrise.studio`.

Repo keeps `web-ui/public/.well-known/*.template` only — live fingerprints stay on the host.

## D. Codemagic AAB

- Workflow: `fashionrise-android-play-internal`
- `versionName=1.0` · `versionCode=PROJECT_BUILD_NUMBER+ANDROID_VERSION_CODE_OFFSET` (offset **30** for this release)
- Signing: existing `fashionrise_android_upload`
- Upload AAB manually to **Internal testing** — do not publish production track; do not recreate the tester track.

## E. Enablement order

1. Ship FE/BE with Google gates **false** and Android push **false** until secrets exist.
2. Publish assetlinks + fix nginx.
3. Place FCM + Play SA files; inject `google-services.json` in Codemagic.
4. Build signed Internal AAB; install on license testers.
5. Enable Android push on staging/prod API; then Play license-tester emails; then public Play gates if authorized.
