# Legal consent notice rotation — 2026-11-17

**Status:** PR ready — **DO NOT DEPLOY** without PM approval.

## What changed

| Surface | Short checkbox | Full terms | Backend purpose / version |
| --- | --- | --- | --- |
| Create Model upload | Rights + private storage + AI | 7-point upload terms + Privacy Policy link + approved adults/storage/AI notices | `adults_beta` · `croquis_storage` · `croquis_ai_provider` · **`create_model_upload` `create-model-upload-2026-11-17`** (short+7-point hash) |
| Public publish (Runway look publish; legacy `POST /gallery` public; My Models API) | Rights to publish + public display | 8-point public-publish terms | `runway_share` `runway-share-2026-11-17` · `croquis_public_share` `croquis-public-share-2026-11-17` |

Upload consent does **not** authorize public publishing. Photo upload requires a current `create_model_upload` event (Alembic **036**). Public `POST /gallery` requires the public-publish notice/version/hash (private visibility still allowed without it).

## Production SHA256 (UTF-8)

| Notice | SHA256 |
| --- | --- |
| Adults | `579a9d61e0b18be316f095068b651e4cfc0ac7c83c545cc086d45f83e5f581bd` |
| Storage | `0bf393b8738c0e612955a614fb9d011cc361eb3e134f1adb920a12d180e8163b` |
| AI | `5cdb56d7edf5f4a3f9e2e9f6b0cfa25ce9a7b3347cb352bd60a179d606149949` |
| Create Model upload agreement (short + 7 points) | `1134d15624e474a8e0763268843cccbabc574d16050ce8e666088f98205376da` |
| Public publish body (Runway + croquis public + gallery) | `bac028289f6a6b489cf378e8e060f6b8d427932dca09f78020774736bc7128bb` |

Bodies: `web-ui/.env.production.example` + `web-ui/.env.native` (adults/storage/AI). Upload agreement + public-publish: FE format helpers ↔ `backend/app/core/config.py`.

## Native / installed-client compatibility

**New backend versions reject older clients.** Installed Android/iOS builds that still send `runway-share-2026-11-08`, `adults-beta-2026-11-01`, or omit `POST /personal-croquis/consent/upload` will get **400/422** on Create Model upload and Runway publish. Consent enforcement is **not** weakened for compatibility.

**Safe rollout (no native build triggered by this PR):**
1. Merge #411 → deploy **FE + BE together** (Alembic **036**, notice env rotate).
2. Web users pick up the new consent UX immediately.
3. Then rebuild Android/iOS from the same tip so Capacitor shells send the new versions.
4. Until native rebuild ships, old store builds may fail Create Model / Runway publish consent — communicate before cutting the BE tip if store users are active.

## Deploy checklist (when approved)

1. Alembic upgrade **036** on API host.
2. Set API host `MY_CROQUIS_ADULTS/STORAGE/AI_NOTICE_TEXT` to the example bodies; bump attestation/consent version env if overridden.
3. Confirm `create_model_upload_*` / `runway_share_*` / `croquis_public_share_*` defaults from config (or matching env overrides).
4. Build FE with exported `VITE_MY_CROQUIS_*_NOTICE_TEXT` matching the SHA pins.
5. Restart API after BE checkout; smoke Create Model agree + Runway publish agree + `POST /gallery` without consent → 422; stale old versions must 4xx.

## Legal-readiness gaps (not invented)

- **No Terms of Service page** (`/privacy` only). Do not link ToS until a real page exists.
- **No documented public content-reporting / takedown workflow** in-product. Do not claim one exists until built and operated.
