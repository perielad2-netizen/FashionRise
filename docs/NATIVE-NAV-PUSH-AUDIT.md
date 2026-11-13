# Native navigation & push audit (2026-11-13)

**Baseline:** `main` `d7f61f9e`  
**Branch:** `cursor/web-native-nav-push-77c6`  
**Stop line:** No Play/App Store submit · no production native-push enablement until separately authorized.

## Part A — Native → web escape audit

| Entry point | Current (pre-fix) behavior | Expected | Severity | Change |
|---|---|---|---|---|
| Capacitor `allowNavigation` fashionrise.app | Absolute https links could load the **remote website inside the WebView** | Stay on local SPA for FashionRise paths | **P0** | `allowNavigation: []`; `urlPolicy` + click guard + deep-link router |
| PrivacyPolicyPage `https://fashionrise.app/privacy` | Absolute anchor → WebView/remote | Relative `/privacy` SPA | **P0** | Relative href |
| Password-reset / verify email (`PUBLIC_APP_URL` https + `#token`) | Opens Safari/Chrome without App Links | Prefer Universal/App Link → in-app; keep hash token; never log token | **P1** | Intent filters + AASA/assetlinks **templates**; runtime `classifyFashionRiseUrl` preserves hash; live association files still **operator** |
| Android Google OAuth | Custom Tabs → `app.fashionrise.studio://auth/google/native?code=` → redeem | Unchanged secure handoff | OK | Reused via deepLinks `oauth_handoff` |
| Login/Register Google on web / latent iOS | `location.assign` start URL | iOS Google hidden for review; web OK; Android Custom Tabs | OK / latent | No weaken; iOS still product-gated |
| Forgot Password / Contact | `mailto:` | System mail client | OK | `external_ok` |
| ShareSheet WhatsApp | `window.open(wa.me…)` | System / WhatsApp | OK | `external_ok` |
| Stars Shop / IAP | StoreKit / gated Play; web checkout gated | Native purchase UIs only when flags on | OK | No unsupported purchasing activation |
| Runway Web Push click | SW `clients.navigate(url)` | Allowlisted path only | **P2** | SW `sanitizePushUrl` |
| Shared looks / designs links | https fashionrise.app without verified App/Universal Links | Browser fallback until association live; if opened in app → SPA | **P1** | Manifest App Links + entitlements; router |
| Cold start / `appUrlOpen` | Partial (OAuth only on Android) | All FashionRise allowlisted URLs | **P1** | `installNativeDeepLinkRouter` + `App.getLaunchUrl` |
| iOS associated domains | Missing | `applinks:fashionrise.app` | **P1** | `App.entitlements` + operator AASA |
| Android assetlinks | Missing | Signed Digital Asset Links | **P1** | Intent filter + template; operator SHA-256 |
| Settings / privacy / account | Mix of relative + one absolute privacy | All FashionRise in-SPA | Fixed | Privacy relative |

### Intentional system interfaces (not defects)

- Google OAuth Custom Tabs / system browser  
- `mailto:` / WhatsApp  
- App Store / Play purchase sheets when IAP flags allow  
- Unverified App/Universal Links falling back to browser until association files are live  

## Part B — Native push readiness

| Layer | Status |
|---|---|
| Web Push VAPID | Unchanged · still works when VAPID set |
| `@capacitor/push-notifications` | Wired in `nativePush.ts` · listeners · tap → `urlPolicy` |
| API `native_push_devices` | Alembic **030** · register/list/delete · capability probe |
| Fan-out | `notify_user` → web + native (per-platform fail-closed) |
| Android FCM | Code path present; needs `google-services.json` + SA JSON + flag |
| iOS APNs | Entitlements + background mode; needs `.p8` + httpx http2 + flag |
| Permission timing | After auth only · desired opt-out · capability gate |
| Account isolation | Token upsert reassigns to current user; logout removes this device only |
| Duplicate delivery | Collapse/tag per device; does **not** disable other devices |

**Operator doc:** `docs/deploy/NATIVE-PUSH-OPERATOR.md`

## Part C — Tests & verification

- FE: `urlPolicy.test.ts`, `nativePush.test.ts`  
- BE: `test_native_push.py` (+ existing `test_push_subscriptions.py` regression)  
- Manual next: signed native build QA after operator credentials (not this PR)

## Exact next QA actions

1. Merge/deploy BE+FE with **native push flags false**.  
2. Confirm Web Push still works on PWA.  
3. Operator: publish AASA + assetlinks; place FCM/APNs secrets.  
4. Staging enable one platform; signed-in register → Runway like → tap stays in-app.  
5. One consolidated iOS release after broader QA — **no store submit in this work**.
