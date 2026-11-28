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
subscriptions.

**User-controlled preference:** `PUT /api/v1/push/delivery-preference`
`{ "prefer_native_push": true }` — when the account has ≥1 native device, Web Push
fan-out is skipped; subscriptions remain. Desktop / other browsers keep their own
local notification toggle. Settings UI exposes this on the native shell.

## Auth / lifecycle

- Pending destinations: `notificationNavigation.ts` (TTL **30 minutes**, latest tap wins)
- Logout / account switch clears pending destinations
- ProtectedRoute preserves `pathname+search`
- Login email/password and Google OAuth preserve the full validated destination via
  signed OAuth `next` (backend re-sanitizes) — no strip-to-path for FashionRise queries
- Android Google OAuth handoff carries the same sanitized `next`

## Capability negotiation (native)

`native_push_devices.destination_contract_version`:

| Version | Payload URL |
| --- | --- |
| **1** (default / installed clients without this PR) | `/studio/fashionrise` only — preserves open + FCM/APNs; no typed query |
| **2** (this FE registers) | Full typed FashionRise query destinations |

New clients POST `destination_contract_version: 2` on device upsert. This avoids
backend-first regressions on older Android/iOS builds whose sanitizers strip queries.

## Rollout (PM-gated — do not merge/deploy until authorized)

1. **Web SPA + SW first** — exact focus for browsers / PWA; SW fixtures pass.
2. **Backend** — producers emit typed FashionRise URLs; `notify_user` sends **v1**
   devices the root path only; **v2** devices get full URLs; migration `048`
   (`prefer_native_push`, `destination_contract_version`).
3. **Native AAB / IPA after PM approval** — bundled FE registers v2 + pending-nav;
   preserves FCM tap-open, APNs, R8, signing. **No AAB/IPA until notification PM OK.**
4. Ordinary Runway rankings navigation and billing / Stars / reconcile gates **unchanged**.

Do **not** merge/deploy this PR until PM authorization.
