# Android release operator checklist — FCM + Play Billing + App Links

Do **not** commit private credentials (`google-services.json`, service-account JSON, keystores).

Package: `app.fashionrise.studio` · Track: Play **Internal / closed testing** (preserve testers).

## A. Firebase native push (FCM)

**Project:** `fashionrise-e2f01` · package `app.fashionrise.studio`

### Production API (done when Cursor secrets are installed)

| Env | Value |
| --- | --- |
| `NATIVE_PUSH_ANDROID_ENABLED` | `true` |
| `NATIVE_PUSH_FCM_PROJECT_ID` | `fashionrise-e2f01` |
| `NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON` | absolute path to host file (e.g. `/var/lib/fashionrise/secrets/fcm-firebase-sa.json`) |

Cursor secret `FIREBASE_SERVICE_ACCOUNT_JSON` is written to that host path only — never committed, never put in the Android APK/AAB.

Public probe: `GET /api/v1/push/native/capability` → `android_enabled: true`.

### Codemagic Android AAB (required before FCM works on device)

Codemagic env group **`fashionrise_native`** (as of 2026-11-27 Asia/Jerusalem):

| Variable | Status |
| --- | --- |
| `ANDROID_GOOGLE_SERVICES_JSON` | **Set** (secure) from Cursor secret — client config only, no private key |
| Existing croquis notice vars | **Preserved** |

Optional aliases still accepted by the workflow: secure file `CM_GOOGLE_SERVICES_JSON`, or legacy `GOOGLE_SERVICES_JSON`.

Workflow `fashionrise-android-play-internal` injects the file into `web-ui/android/app/google-services.json`, validates project/package, builds the AAB, then deletes the file so it is not an artifact.

Do **not** start the AAB until Play Billing credentials are configured. Smoke after Internal install: signed-in → Runway bell ON → like → tap opens `/studio…`.

Do **not** change Web Push or iOS APNs flags in this checklist.

## B. Google Play Billing (Stars)

Products (consumable, same as Apple): `stars_50` · `stars_150` · `stars_500` — **ACTIVE** in Play (verified via Android Publisher `oneTimeProducts`).

### Production API (2026-11-27 Asia/Jerusalem)

| Env | Value |
| --- | --- |
| `IAP_GOOGLE_SERVICE_ACCOUNT_JSON` | `/var/lib/fashionrise/secrets/google-play-sa.json` (from Cursor `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`) |
| `IAP_GOOGLE_PACKAGE_NAME` | `app.fashionrise.studio` |
| `IAP_GOOGLE_PURCHASING_ENABLED` | `false` (public OFF) |
| `IAP_GOOGLE_CREDIT_ENABLED` | `false` (public OFF) |
| `IAP_GOOGLE_LICENSE_TESTER_EMAILS` | set FashionRise account emails when ready for license-tester smoke |
| `IAP_GOOGLE_RTDN_VERIFY_OIDC` | `true` |
| `IAP_GOOGLE_RTDN_AUDIENCE` | **pending** — full push URL `https://fashionrise.app/api/v1/shop/iap/google/notifications` |
| `IAP_GOOGLE_RTDN_EXPECTED_EMAIL` | **pending** — exact Pub/Sub push service-account email (OIDC `email` claim) |

Connectivity check (no purchase): SA mints Android Publisher token · `oneTimeProducts` lists the three SKUs · bogus purchase token returns 400 (auth OK).

1. Keep public gates **false** until license-tester validation (Sandbox purchases only for allowlisted emails).
2. RTDN: Play Console → Monetization setup → Real-time developer notifications → Pub/Sub → push to  
   `https://fashionrise.app/api/v1/shop/iap/google/notifications`  
   then set `IAP_GOOGLE_RTDN_AUDIENCE` to that exact URL **and** `IAP_GOOGLE_RTDN_EXPECTED_EMAIL` to the push SA email.
3. Optional backfill: call `reconcile_voided_purchases` (Voided Purchases API, ≤30 days).
   For a **single PM-authorized** order while the persistent apply gate stays OFF, use
   `backend/scripts/run_google_play_recover_order.py --order-id GPA.… --authorize-recovery-stars N --apply`
   (process-local `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID` only — never write the global apply flag).
4. Financial reconcile (preferred): `orders.get` + `products.get` via
   `google_play_reconcile.reconcile_android_purchases(dry_run=True)` /
   Admin `GET /admin/iap/google/reconcile`. Google may refund without RTDN/voided rows.
   Recover Stars only when order is fully **REFUNDED** **and** entitlement is canceled/404.
   Partial / pending / refund-without-revoke → **review** (never blind deduct).
   Mutations require `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true` (default **false**).
   For a **PM-authorized** single-order validation of the automated path (persistent apply stays OFF):
   `scripts/run_google_play_reconcile_once.py --order-id GPA.… --authorize-apply-stars N --apply`
   (process-local `APPLY_ORDER_ID` + cluster lock; same service as the hourly tick).
5. Nginx must allowlist `POST` on that path (see shop allowlist docs).
6. Native push nginx: keep `deploy/nginx-allowlists/native-push.conf.snippet` in the live
   `fashionrise.app` allowlist; assert with `scripts/assert_nginx_native_push_allowlist.sh`.
7. Admin revenue: Play license-test purchases map to `environment=Sandbox` and stay excluded from Production revenue.
8. External Play ops (15% fee program / payments bank verification) are separate from IAP reconcile and FCM.

Never trust client Stars/price. Credit only after `purchases.products.get` · purchaseState=Purchased · account bind · durable purchase-token idempotency · then client `consumePurchase`.

## C. Android App Links (Digital Asset Links)

**Live (2026-11-27 Asia/Jerusalem):** Play App Signing SHA-256  
`D8:2D:D6:16:40:F9:4E:39:5E:30:14:08:04:41:8D:87:C6:D6:D5:78:B9:70:48:1E:6A:13:08:F2:53:A1:79:16`  
at `/var/www/fashionrise/well-known/assetlinks.json` (nginx alias for apex + www).

1. Verify: `https://fashionrise.app/.well-known/assetlinks.json` and `https://www.fashionrise.app/.well-known/assetlinks.json` → **200** JSON.
2. DAL: `https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://fashionrise.app&relation=delegate_permission/common.handle_all_urls`
3. If Play Console shows a **previous** app signing certificate, append its SHA-256 to `sha256_cert_fingerprints` (array supports multiple) for older installs — do not remove the current Play App Signing fingerprint.
4. Cloudflare: exclude Access/WAF challenge on `/.well-known/*` if needed.

Repo keeps `web-ui/public/.well-known/*.template` — live host file is authoritative.

## D. Codemagic AAB

- Workflow: `fashionrise-android-play-internal`
- `versionName=1.0` · `versionCode=PROJECT_BUILD_NUMBER+ANDROID_VERSION_CODE_OFFSET` (offset **30** for this release)
- Signing: existing `fashionrise_android_upload`
- Release R8: `minifyEnabled true` + `shrinkResources true` (Play DEX obfuscation)
- Android 15: `EdgeToEdge.enable` in `MainActivity` + transparent system bars / cutout
- Upload AAB manually to **Internal testing** — do not publish production track; do not recreate the tester track.
- Do **not** start AAB until RTDN env (`AUDIENCE` + `EXPECTED_EMAIL`) is set.

## E. Enablement order

1. Ship FE/BE with Google gates **false** and Android push **false** until secrets exist.
2. Publish assetlinks + fix nginx.
3. Place FCM + Play SA files; inject `google-services.json` in Codemagic.
4. Build signed Internal AAB; install on license testers.
5. Enable Android push on staging/prod API; then Play license-tester emails; then public Play gates if authorized.
