# Push destination contract (cross-platform)

Single source of truth for notification tap URLs across **Android FCM**, **iOS APNs**,
**browser Web Push**, and **installed PWA**.

Implementations (must stay in lockstep):

- Backend: `backend/app/services/push_destinations.py`
- SPA: `web-ui/src/services/native/pushDestination.ts`
- Service worker: `web-ui/public/push-sw-handlers.js`

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

- Paths: `/studio…`, `/privacy` only
- Hostnames (absolute URLs): `fashionrise.app`, `www.fashionrise.app` (parsed hostname)
- Reject token/credential query keys, auth routes, protocol-relative hosts, path traversal
- FashionRise query keys are typed; duplicate keys / contradictory `item`+`friends` → strip to path
- Other studio paths: queries stripped

## Grouping tags

Entity-scoped collapse keys (examples): `fr-like-<item>`, `fr-comment-<comment>`,
`fr-friend-request-<friendship>`. Recipient-level tags must not collapse unrelated designs.

## Cross-channel delivery

Web Push and native both fan out when registered. UA/platform matching is **not**
reliable physical-device association — do not suppress Web Push solely because a
native token exists. Prefer an explicit user preference or future device-binding
before same-device dedupe.

## Auth / lifecycle

Pending destinations use `notificationNavigation.ts` (native cold/warm + post-auth flush).
ProtectedRoute preserves `pathname+search`. Login honors `state.from` / pending push
destinations. Logout clears pending destinations.

## Rollout

1. Deploy **backend** first (new destination payloads).
2. Deploy **web** (SPA + SW) — Workbox `importScripts` picks up `push-sw-handlers.js`.
3. Ship native AAB/IPA when bundled FE is required for cold-start pending-nav + exact focus
   (older clients still open FashionRise feed safely after sanitizer fallback).
4. Do **not** merge/deploy until PM authorization for this PR.
