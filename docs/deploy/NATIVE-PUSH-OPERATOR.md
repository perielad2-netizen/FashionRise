# Native push — operator configuration (do not commit secrets)

FashionRise keeps **Web Push (VAPID)** unchanged for browsers. Native FCM/APNs is **fail-closed** until both a platform flag **and** credentials are present.

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
| `NATIVE_PUSH_APNS_USE_SANDBOX` | `true` for TestFlight/dev; `false` for App Store |

Incomplete config → `/push/native/capability` reports disabled → clients never register → Web Push unaffected.

## Android (Firebase / FCM)

1. Firebase project linked to Play app `app.fashionrise.studio`.
2. Download `google-services.json` into the Android app module via Codemagic/secure file — **never commit**.
3. Create a service account with Firebase Cloud Messaging Admin; store JSON on the API host only.
4. Play App Signing SHA-256 → `assetlinks.json` (see templates under `web-ui/public/.well-known/`).
5. Runtime permission `POST_NOTIFICATIONS` is requested **after authentication** when the user has not opted out.

## iOS (APNs)

1. Apple Developer: enable **Push Notifications** on App ID `app.fashionrise.studio`.
2. Create APNs Auth Key (`.p8`); store outside repo; set env paths/IDs above.
3. Xcode/Codemagic: Push capability + `App.entitlements` (`aps-environment`, associated domains).
4. Publish `apple-app-site-association` at `https://fashionrise.app/.well-known/apple-app-site-association` (no redirect, `application/json`).
5. Provisioning profile must include push + associated domains.

## Security rules

- Never put access/refresh/password-reset tokens in push payloads.
- Payload `url` is sanitized server-side and again on the client (`urlPolicy` / SW handler).
- Device token reassignment on register moves the token to the **current** account (account switch).
- Logout deletes **this** device token for the current account only — other devices stay.
- Account deletion cascades `native_push_devices` via FK.

## Enablement order (QA)

1. Ship FE/BE with flags **false** (this PR).
2. Operator places credentials; smoke `/push/native/capability`.
3. Enable Android **or** iOS flag on staging; register from a signed-in native build.
4. Trigger a Runway like; confirm single notification; tap → `/studio/runway` in-app.
5. Only then consider production flags — **separate authorization** from store submit.

## Stop line

Do **not** enable live native delivery or submit store builds until QA consolidates and an owner explicitly authorizes.
