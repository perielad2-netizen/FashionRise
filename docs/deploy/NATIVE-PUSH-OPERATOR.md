# Native push — operator configuration (do not commit secrets)

FashionRise keeps **Web Push (VAPID)** unchanged for browsers. Native FCM/APNs is **fail-closed** until both a platform flag **and** credentials are present.

**Flags remain OFF** until separately authorized. Incomplete native infra must not break Web Push.

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

1. Firebase project linked to Play app `app.fashionrise.studio`.
2. Download `google-services.json` into the Android app module via Codemagic/secure file — **never commit**.
3. Create a service account with Firebase Cloud Messaging Admin; store JSON on the API host only.
4. Play App Signing SHA-256 → `assetlinks.json` (see templates under `web-ui/public/.well-known/`).
5. Runtime permission `POST_NOTIFICATIONS` is requested **after authentication** when the user has not opted out.

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
