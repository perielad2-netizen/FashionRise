# Legal consent notice rotation — 2026-11-17

**Status:** PR ready — **DO NOT DEPLOY** without PM approval.

## What changed

| Surface | Short checkbox | Full terms | Backend purpose / version |
| --- | --- | --- | --- |
| Create Model upload | Rights + private storage + AI | 7-point upload terms + Privacy Policy link + approved adults/storage/AI notices | `adults_beta` `adults-beta-2026-11-17` · `croquis_storage` `storage-2026-11-17` · `croquis_ai_provider` `ai-provider-2026-11-17` |
| Public publish (Runway look publish; My Models API when used) | Rights to publish + public display | 8-point public-publish terms | `runway_share` `runway-share-2026-11-17` · `croquis_public_share` `croquis-public-share-2026-11-17` |

Upload consent does **not** authorize public publishing.

## Production SHA256 (UTF-8)

| Notice | SHA256 |
| --- | --- |
| Adults | `579a9d61e0b18be316f095068b651e4cfc0ac7c83c545cc086d45f83e5f581bd` |
| Storage | `0bf393b8738c0e612955a614fb9d011cc361eb3e134f1adb920a12d180e8163b` |
| AI | `5cdb56d7edf5f4a3f9e2e9f6b0cfa25ce9a7b3347cb352bd60a179d606149949` |
| Public publish body (Runway + croquis public) | `bac028289f6a6b489cf378e8e060f6b8d427932dca09f78020774736bc7128bb` |

Bodies: `web-ui/.env.production.example` + `web-ui/.env.native` (Create Model). Public-publish body: `web-ui/src/lib/publicPublishConsent.ts` ↔ `backend/app/core/config.py`.

## Deploy checklist (when approved)

1. Set API host `MY_CROQUIS_ADULTS_NOTICE_TEXT` / `STORAGE` / `AI` to the example bodies; bump attestation/consent version env if overridden.
2. Confirm `runway_share_*` / `croquis_public_share_*` defaults from config (or matching env overrides).
3. Build FE with exported `VITE_MY_CROQUIS_*_NOTICE_TEXT` matching the SHA pins.
4. Restart API after BE checkout; smoke Create Model agree + Runway publish agree; stale old versions must 4xx.

## Legal-readiness gaps (not invented)

- **No Terms of Service page** (`/privacy` only). Do not link ToS until a real page exists.
- **No documented public content-reporting / takedown workflow** in-product. Do not claim one exists until built and operated.
