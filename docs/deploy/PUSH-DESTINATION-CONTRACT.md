# Push destination contract (cross-platform)

Single source of truth for notification tap URLs across **Android FCM**, **iOS APNs**,
**browser Web Push**, and **installed PWA**.

Implementations (must stay in lockstep):

- Backend: `backend/app/services/push_destinations.py`
- SPA: `web-ui/src/services/native/pushDestination.ts`
- Service worker: `web-ui/public/push-sw-handlers.js`
- Shared fixtures: `backend/tests/fixtures/push_destination_contract_cases.json`
  (copied under `web-ui/.../__fixtures__/` for FE/SW tests)

## Destinations

| Event | URL |
| --- | --- |
| Design like / score | `/studio/fashionrise?item=<GALLERY_UUID>` |
| New comment / comment like | `/studio/fashionrise?item=<GALLERY_UUID>&comments=1&comment=<COMMENT_UUID>` |
| Friend request | `/studio/fashionrise?friends=1&section=requests&friendship=<FRIENDSHIP_UUID>` |
| Friend accepted | `/studio/fashionrise?friends=1&section=accepted&friendship=<FRIENDSHIP_UUID>` |
| Legacy / rankings | `/studio/runway` (no item query) |
| Fallback | `/studio/fashionrise` |

IDs are **public GalleryItem** / comment / friendship UUIDs. Never MagicLook IDs
(`?look=` is My Looks only and is **not** a push destination).

## Validation rules

Sanitizers **reject** (fallback `/studio/fashionrise`):

- Protocol-relative URLs (`//…`)
- Unsupported schemes (`javascript:`, `data:`, …) — only `http`/`https` absolute URLs
- Path traversal (raw `..` and encoded `%2e` forms)
- Backslash path manipulation
- Credential-bearing URLs (`user:pass@host`)
- Duplicate or contradictory FashionRise query keys (`item`+`friends`, unknown keys)
- Token/credential query keys and auth routes

Paths allowed: `/studio…`, `/privacy` only. Absolute hosts: `fashionrise.app`,
`www.fashionrise.app` (parsed hostname). Other studio paths: queries stripped.
SPA (`StudioPage`) consumes focus **only** via `parsePushDestination` — never raw
search params alone.

## Grouping tags

Entity-scoped collapse keys (examples): `fr-like-<item>`, `fr-comment-<comment>`,
`fr-friend-request-<friendship>`. Recipient-level tags must not collapse unrelated designs.

## Cross-channel delivery

Web Push and native both fan out when registered. **Physical same-device dedupe is
not automatic** — UA/OS/IP/fingerprint matching is unreliable and must not delete
subscriptions or suppress unrelated channels.

**Per-browser opt-out:** Settings → Notifications toggles **this browser’s** Web Push
subscription only (`deletePushSubscription` for the current endpoint). Desktop and
other devices keep their own subscriptions. Native Settings toggle affects only the
installed app token. There is **no** account-wide `prefer_native_push` preference.

Automatic physical-device Web Push ↔ native deduplication is a **future** improvement.

## Auth / lifecycle

- Pending destinations: `notificationNavigation.ts` (TTL **30 minutes**, latest tap wins)
- Logout / account switch clears pending destinations
- ProtectedRoute preserves `pathname+search`
- Login email/password and Google OAuth preserve the full validated destination via
  signed OAuth `next` (backend re-sanitizes) — no strip-to-path for FashionRise queries
- Android Google OAuth handoff carries the same sanitized `next`

## Capability negotiation (native)

`native_push_devices.destination_contract_version` (migration **048**):

| Version | Payload URL |
| --- | --- |
| **1** (default / existing installs before this FE) | Keep `/studio/fashionrise?friends=1…` (already supported). Item/comment social deep-links → `/studio/fashionrise` Social feed. Other sanitized `/studio…` / `/privacy` paths preserved (operator / rankings). |
| **2** (this FE registers on upsert) | Full typed FashionRise query destinations |

Upgraded installs **re-register the existing FCM/APNs token** with
`destination_contract_version=2` after login/resume — no logout, reinstall, or
notification-permission change required. `app_version` is populated from Capacitor
`App.getInfo()` (`version` + `build`) when available.

## Rollout

1. **Web SPA + SW** — exact focus for browsers / PWA; SW fixtures pass.
2. **Backend** — producers emit typed FashionRise URLs; `notify_user` maps per
   `destination_contract_version`; migration `048` adds the column only.
3. **Native AAB** — bundled FE registers v2 + pending-nav; preserves FCM tap-open,
   R8, signing. **No Play upload / no iOS IPA** in this release — published iOS stays
   on the v1 compatibility contract until a later IPA.
4. Ordinary Runway rankings navigation and billing / Stars / reconcile gates **unchanged**.
