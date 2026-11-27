# Native push — operator configuration (do not commit secrets)

FashionRise keeps **Web Push (VAPID)** unchanged for browsers. Native FCM/APNs is **fail-closed** until both a platform flag **and** credentials are present.

**Android FCM is LIVE** on production (`fashionrise-e2f01`, 2026-11-27 Asia/Jerusalem). iOS APNs stays as previously configured — do not flip flags without an explicit ask. Incomplete native infra must not break Web Push.

## Flags (default OFF)

| Env | Purpose |
|---|---|
| `NATIVE_PUSH_ANDROID_ENABLED` | Must be `true` **and** FCM JSON + project id set |
| `NATIVE_PUSH_IOS_ENABLED` | Must be `true` **and** APNs `.p8` + key/team/topic set |
| `NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON` | Absolute path to Firebase service-account JSON **outside the repo** |
| `NATIVE_PUSH_FCM_PROJECT_ID` | Firebase / GCP project id |
| `NATIVE_PUSH_APNS_KEY_PATH` | Absolute path to AuthKey_XXXX.p8 **outside the repo** |
| `NATIVE_PUSH_APNS_KEY_ID` | Key ID from Apple Developer |
| `NATIVE_PUSH_APNS_TEAM_ID` | Apple Team ID |
| `NATIVE_PUSH_APNS_TOPIC` | Bundle id (`app.fashionrise.studio`) |
| `NATIVE_PUSH_APNS_USE_SANDBOX` | `true` only for local Debug/dev installs; **`false` for TestFlight / App Store** (production APNs) |

Incomplete config → `/push/native/capability` reports disabled → clients never register → Web Push unaffected.

## Web Push + native coexistence

| Topic | Behavior |
|---|---|
| Storage | **Separate tables**: `push_subscriptions` (VAPID endpoints) vs `native_push_devices` (FCM/APNs tokens) |
| Fan-out | `notify_user` sends to **all** of a user’s enabled destinations independently |
| Same phone, PWA + native app | Can receive **two** notifications (one Web Push, one native) if both are registered — expected; not a global disable |
| Duplicate collapse | Per-device OS collapse via `tag` / `collapse_key` / `apns-collapse-id` — collapses repeats **on that device**, never removes other devices |
| Per-device opt-out | Runway bell off → web: unsubscribe this browser endpoint; native: `disableNativePush` deletes **this** device token only |
| Logout / account switch | Unregisters **this** native token from the prior account; web subscription stays until that browser opts out; token re-register binds to the new account |
| Flags OFF | Native path is a no-op; existing Web Push continues |

Push tap destinations are **only** `/studio…` and `/privacy`. Password-reset, email-verification, and OAuth/token URLs are rejected server-side, in the service worker, and in the native tap handler.

## Android (Firebase / FCM)

| Item | Value |
| --- | --- |
| Firebase project | `fashionrise-e2f01` |
| Android package | `app.fashionrise.studio` |
| Prod SA file | `/var/lib/fashionrise/secrets/fcm-firebase-sa.json` (host only · mode 0640) |
| Prod env | `NATIVE_PUSH_ANDROID_ENABLED=true` · `NATIVE_PUSH_FCM_PROJECT_ID=fashionrise-e2f01` · `NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON=<abs path>` |
| Cursor secrets | `FIREBASE_SERVICE_ACCOUNT_JSON` (API host) · `ANDROID_GOOGLE_SERVICES_JSON` (Codemagic only) |

1. Codemagic group `fashionrise_native`: secret env `ANDROID_GOOGLE_SERVICES_JSON` is **configured** (client config — **no** private key; existing group vars preserved). Workflow injects `web-ui/android/app/google-services.json`, validates project/package, then deletes after `bundleRelease`. Do not start AAB until Play Billing is ready.
2. Never commit `google-services.json` or the FCM service-account private key; never ship the SA inside the AAB.
3. Play App Signing SHA-256 → `assetlinks.json` (see templates under `web-ui/public/.well-known/`). Also add the **Play App Signing SHA-1** (and upload-key SHA-1 if used for sideload) under Firebase Console → Project settings → Your apps → `app.fashionrise.studio` → Add fingerprint — required for some FCM / Installations edge cases.
4. Runtime permission `POST_NOTIFICATIONS` is requested **after authentication** when the user has not opted out.
5. Smoke: `GET /api/v1/push/native/capability` → `android_enabled: true`; Internal AAB → Runway bell ON → like → tap `/studio…`.
6. Registration diagnostics (client): failing stage is recorded via `getLastNativePushDiagnostic()` / Settings notice (`token_timeout`, `token_error`, `backend_post`, …). Console logs use token **fingerprints only** — never full FCM tokens. Auto + Settings share `syncNativePushAfterAuth`.
7. Prod QA (2026-11-27 Asia/Jerusalem):
   - VC **219** failed **before** `POST /push/native/devices` (FCM token stage). Diagnostics + retry shipped in **#534**; Internal AAB **VC 230** (`0b197880`).
   - VC **230** then acquired an FCM token but Settings showed *server rejected registration*: nginx had allowlisted only `/push/native/capability` — `OPTIONS/POST /push/native/devices` hit `location /api/ { return 403 }` (Capacitor Origin `https://localhost`). **No POST reached FastAPI**; `native_push_devices` stayed **0**. Sign-in-again was **not** applicable.
   - Fix: **LIVE** allowlist + repo SoT `deploy/nginx-allowlists/native-push.conf.snippet` (assert via `deploy/nginx-allowlists/assert_native_push_allowlist.sh`). Backup `nginx-fashionrise.app.bak-native-devices-20261127T130828Z`. Smoke: OPTIONS **200**, unauth POST **401**, unknown path **403**. **No AAB rebuild required**; VC 230 can retest now.
   - After registration succeeds: inspect `native_push_devices`, then run a **separately controlled** delivery test to that device only. Do not declare push operational until real delivery is verified.
   - Do not declare fixed until Notifications **ON** + DB row + preference survives restart/re-login + gated real push.

## iOS (APNs) — entitlements & provisioning

### Repo wiring (verified by `iosPushWiring.test.ts`)

| Build | Entitlements file | `aps-environment` |
|---|---|---|
| Debug | `web-ui/ios/App/App/AppDebug.entitlements` | `development` |
| Release | `web-ui/ios/App/App/AppRelease.entitlements` | `production` |

Both include Associated Domains: `applinks:fashionrise.app`, `applinks:www.fashionrise.app`.  
`AppDelegate.swift` posts Capacitor APNs success/failure notifications (required by `@capacitor/push-notifications`).

### Operator / Codemagic checklist (before any enablement)

1. Apple Developer App ID `app.fashionrise.studio`: enable **Push Notifications** and **Associated Domains**.
2. Codemagic / Xcode signing for **Release / App Store IPA** must use a **distribution** provisioning profile that includes those capabilities (not a development-only profile).
3. Confirm the signed IPA’s embedded entitlements show `aps-environment = production` (TestFlight and App Store use production APNs).
4. Create APNs Auth Key (`.p8`); store outside repo; set env paths/IDs above. Set `NATIVE_PUSH_APNS_USE_SANDBOX=false` for TestFlight/production delivery.
5. Publish `apple-app-site-association` at `https://fashionrise.app/.well-known/apple-app-site-association` (no redirect, `application/json`).

Static repo checks do **not** replace inspecting the Codemagic-signed IPA; do that on the next authorized native build.

## Security rules

- Never put access/refresh/password-reset/OAuth tokens in push payloads or tap URLs.
- Payload `url` is sanitized server-side and again on the client (push destination allowlist / SW handler).
- Device token reassignment on register moves the token to the **current** account (account switch).
- Logout deletes **this** device token for the current account only — other devices stay.
- Account deletion cascades `native_push_devices` via FK.

## Enablement order (QA)

1. Ship FE/BE with flags **false** (this PR).
2. Operator places credentials; smoke `/push/native/capability`.
3. Enable Android **or** iOS flag on staging; register from a signed-in native build.
4. Trigger a Runway like; confirm delivery; tap → `/studio/runway` in-app.
5. Only then consider production flags — **separate authorization** from store submit.

## Stop line

Do **not** enable live native delivery or submit store builds until QA consolidates and an owner explicitly authorizes.
