# Create My Croquis V1 — Implementation-Ready Design

**Status:** DESIGN ONLY — Technical PM review checkpoint  
**Issue:** [#135](https://github.com/perielad2-netizen/FashionRise/issues/135)  
**Date:** 2026-10-30  
**Base lineage:** PR [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) tip (accepted production FE recovery `2dfcaba0`)  
**Production baseline (do not assume = `main`):** FE `2dfcaba0` / source `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` · BE+worker `6cc317ec` · Alembic `011`  
**Gates:** FRONT_BACK/MAGIC/DUAL ON · REGISTRATION OFF · API `/api/v1` · CF Access + AOP unchanged  
**This document authorizes nothing:** no implementation, migration, deploy, paid AI, real-photo handling, or production flag changes until separately accepted.

---

## 1. Executive decision and recommended architecture

**Product promise:** Generate a **personal fashion illustration reference** (front-facing line-art croquis) from a fully clothed photo, then use it as the Studio drawing underlay. Not a body scan, measurement source, fit simulator, or manufacturing POM input.

**Recommended V1 architecture (simplest secure path on current VPS):**

1. **Private media store** — extend the proven fabric pattern (`private_fabrics` + owner-auth `GET …/image` + `Cache-Control: private, no-store`). Add a sibling root `private_croquis/` via `LocalStorageBackend`. **Never** write source photos or generated croquis under `/static/uploads`.
2. **Domain tables** — `personal_croquis` (versioned generation record) + `private_media_assets` (or two typed asset FKs) for source photo and generated PNG, soft-delete aware.
3. **Studio reference** — new durable model choice `personal` (keep legacy `custom` as session-only blob for temporary overlays if desired, or deprecate upload-to-custom in favor of Create My Croquis). Persist `personalCroquisId` + `personalCroquisVersion` in draft/saved snapshots so reopen binds the **exact** accepted generation.
4. **AI** — separate gate `MY_CROQUIS_AI_ENABLED=false` (independent of Magic / Dual Magic / Professional). Provider adapter reuses existing `images.edit` + `gpt-image-2.5-sunburst` path patterns with **mock-first** Stage B; Stage C wires live provider only after PM/owner auth.
5. **Front-only V1** — no synthesized back from a single front photo. Back side uses blank / “Front-only croquis” notice; Dual Magic / rear croquis remain for built-ins only.
6. **Phased delivery** — A private storage → B Studio + mock → C gated AI → D controlled release.

**Rejected shortcuts:** public `/static/uploads` for photos; browser-only blob URLs as the durable reference; silent model remapping when assets disappear; fabricating a back view; piggybacking Magic spend ceilings without a separate croquis budget.

---

## 2. Product UX

### 2.1 Happy path

1. Creator Studio → Models → **Create My Croquis** (beta entry, visually distinct from the 10 built-ins).
2. Requirements + privacy sheet (before file picker): fully clothed, full-body, front-facing, standing, good light; photo is private; processing may use an AI provider; not for measurements; minors policy (see §13).
3. Upload or capture → client MIME/size precheck → server authoritative validation.
4. Review crop/preview of the **uploaded** photo + explicit consent checkbox (versioned consent text).
5. **Generate My Croquis** (explicit CTA; no AI call on file select alone).
6. Progress: queued / running / failed with safe messages; cost/quota surfaced before confirm when AI gate is on.
7. Preview generated line-art on the 768×1024 reference plane (paper chrome unchanged).
8. Accept → save personal croquis to library; Reject → keep photo for retry or discard generation.
9. Selecting the croquis sets Studio model to `personal` with pinned version; drawing tools work as today.
10. Save / refresh / reopen / Saved Design restore the **same** croquis version.

### 2.2 Desktop / tablet / mobile

| Surface | Pattern |
|---|---|
| Desktop | Models sheet/panel: built-ins grid + footer CTA “Create My Croquis”. Modal wizard (requirements → upload → consent → generate → preview). |
| Tablet landscape | Same wizard as full-height sheet; large preview; sticky Generate/Accept. |
| Mobile | Full-screen wizard steps; camera capture preferred; one primary CTA per step; avoid nested cards. |

Reuse existing Models / My Fabrics interaction language (list + authenticated image URL fetch via API, not static paths). Do not invent a second Studio shell.

### 2.3 Front/Back

- V1 personal croquis is **front-only**.
- When `activeSide === 'back'`: show blank paper or existing strokes/fills only; optional non-blocking notice “This personal croquis is front-only.”
- Do **not** mirror/flip the front croquis as a fake back.
- Built-in rear croquis (`backCanvasSrc`) unchanged for library models.

### 2.4 Library management

- “My Croquis” list under Models (or sibling of My Fabrics): thumbnail via owner-auth image route, rename, soft-delete.
- Soft-delete removes from picker; historical drafts still resolve bytes when `include_deleted` on asset GET (same as fabrics).

---

## 3. Existing-code findings (verified)

### 3.1 Frontend

| Area | Finding | Path |
|---|---|---|
| Model library | 10 selectable builtins + legacy `female`/`male` + `custom`/`blank`. `custom` has **no** rear croquis. | `web-ui/src/assets/modelLibrary.ts` |
| Custom upload | `onCustomFile` validates then uses **blob URL only**; explicitly refuses persistence because `/static/uploads` is not owner-private. | `web-ui/src/hooks/useStudioEditor.ts` |
| Saved designs | `snapshotFromDocument` **drops** `customReferenceUrl` / `customReferenceKey`. Custom imagery does **not** survive Saved Design reopen. | `web-ui/src/lib/savedDesign.ts` |
| Draft doc | Fields `customReferenceUrl`, `customReferenceKey` exist but are session-oriented. V2 holds front/back ink. | `web-ui/src/lib/draftDocument.ts` |
| Geometry | Legacy design plane **768×1024**; extended paper **1280×1536** with origin **(-256,-256)**. Croquis must remain fit/aligned in the legacy plane. | `web-ui/src/lib/paperBounds.ts` |
| Export | Front/Back PNG export fit-contains reference into design plane; paper frame when ink exceeds legacy box. | `web-ui/src/lib/exportCanvas.ts`, extended-paper tests |
| Client validation | `validateReferenceImageFile` MIME allowlist helper (server must still sniff bytes). | `web-ui/src/lib/referenceFile.ts` |
| Feature flags | `VITE_STUDIO_FRONT_BACK_ENABLED`, `VITE_MAGIC_UI_ENABLED`, `VITE_STUDIO_DUAL_MAGIC_ENABLED`, `VITE_REGISTRATION_UI_ENABLED` — defaults OFF; prod recovery asserts compiled values. New croquis AI gate must **not** couple to these. | `assert-prod-vite-flags.mjs` |
| Private images (precedent) | Uploaded fabrics fetched via authenticated API + `Cache-Control: private, no-store`. | FE fabric services + BE fabrics routes |

### 3.2 Backend

| Area | Finding | Path |
|---|---|---|
| Private fabrics | `FabricAsset` owner-scoped; bytes under `private_fabrics/`; soft-delete; owner-only image route; tests assert **not** under `/static/uploads`. | `backend/app/models/fabric_asset.py`, `services/fabric_asset_service.py`, `api/v1/routes/fabrics.py`, `tests/test_fabric_assets.py` |
| Storage | `LocalStorageBackend.save_private_file` / `resolve_private_file`; public mount is `upload_subdir` → `/static/uploads`. | `backend/app/storage/local.py`, `main.py` |
| Upload validation | MIME sniff, size limits, dimension probe before full decode, PNG re-encode (strips EXIF via re-encode). | `core/upload_validation.py`, fabric service |
| Magic / looks | Paid `images.edit` via worker; authenticated job image routes preferred over public static; spend ceilings for techpack Professional separate. | `services/sketch_openai.py`, `api/v1/routes/ai_routes.py`, config |
| Image model | Config default `openai_image_model=gpt-image-2.5-sunburst`, size `1024x1536`, quality `high`, `max_retries=0` pattern for edits. | `core/config.py`, P1-54 docs |
| Alembic | Head **`011`**. Next migration would be `012_*` — **not in this design PR**. | `alembic/versions/` |
| Auth | JWT `CurrentUser`; ownership filters on every private resource. | `app/auth/dependencies.py` |
| Rate limits | SlowAPI `@limiter.limit` on fabric/AI routes. | fabrics / ai routes |

### 3.3 Production hygiene

- `#136` CLOSED after owner six-point acceptance on FE `2dfcaba0`.
- `#127` / `#128` CLOSED — do not reopen.
- `#137` deployed, **not merged**; `main` ≠ live FE/BE.
- Design branch must stack on `#137` lineage, not assume `main`.

---

## 4. Component / data-flow architecture

```
┌──────────── FE Studio ────────────┐
│ Models → Create My Croquis wizard │
│  upload ──POST /personal-croquis/photos
│  consent+generate ──POST …/generate
│  poll ──GET …/{id}
│  accept ──POST …/{id}/accept
│  select ── set model=personal + ids
│  draw / fill / save (draft V2 + Saved Design)
│  reference paint ← GET …/assets/{id}/image (auth)
└───────────────┬───────────────────┘
                │ /api/v1 (CF Access + JWT)
┌───────────────▼───────────────────┐
│ FastAPI                             │
│  ownership + rate limit + quotas    │
│  validate image → private store     │
│  personal_croquis row + job enqueue │
│  (Stage C) worker adapter           │
└───────────────┬───────────────────┘
                │
┌───────────────▼───────────────────┐
│ Disk: local_storage_root/           │
│  private_croquis/{user}/{asset}.png │  ← NOT static-mounted
│  uploads/ …                         │  ← public mount; forbidden for croquis
│ Postgres: personal_croquis + assets │
└─────────────────────────────────────┘
```

**FE modules to reuse:** Models UI, `useStudioEditor` reference pipeline, `draftDocument` / `draftPersistence`, `savedDesign`, `referenceFile`, fabric authenticated image fetch pattern, paperBounds / exportCanvas.

**BE modules to reuse:** `FabricAsset` service patterns, `LocalStorageBackend` private roots, `upload_validation`, auth deps, rate limiter, AI worker job skeleton (Stage C), spend/idempotency patterns from techpack/Magic **without sharing the same enable flag**.

**New (proposed):**  
FE: `CreateMyCroquisWizard`, `personalCroquisApi`, modelLibrary `personal` choice, draft fields.  
BE: `personal_croquis` models/routes/services, `private_croquis` storage root, Stage C `MyCroquisProvider` + worker hook, settings `MY_CROQUIS_AI_ENABLED`.

---

## 5. Privacy and threat model (P0)

### 5.1 Invariants

- Source photos and generated croquis are **owner-private**.
- Serve only via authenticated routes with ownership check.
- Responses: `Cache-Control: private, no-store` (match fabrics).
- No public URL, no CDN cache of private bytes, no logging of image/base64/private paths/tokens.
- Consent version recorded before any provider call.
- Quota + rate limits; fail closed when AI gate off.

### 5.2 Threats and mitigations

| Threat | Mitigation |
|---|---|
| IDOR on asset/croquis UUID | Every GET/DELETE filters `owner_id == current_user`; cross-user → 404 (not 403) to avoid existence leaks where fabrics already do |
| Guessable sequential IDs | UUIDv4 primary keys |
| Access-token leakage in image URLs | No query-string tokens; cookie/Authorization header only; short-lived browser memory of blob from authenticated fetch if needed |
| Stale signed URLs | **Do not use** long-lived signed public URLs in V1; auth each request |
| Cross-user retrieval via static mount | Bytes outside `upload_subdir`; Nginx keep denying public static for private trees; tests probe `/static/uploads/...` → 404 |
| Cache exposure (shared browser/CDN) | `private, no-store`; no `public`/`max-age` on private images |
| Deletion race while design open | Soft-delete; image GET allows `include_deleted` for owner; UI shows “Croquis unavailable” without remapping model or wiping strokes |
| Replay of generate | Idempotency key per (user, source_asset, consent_version, prompt_version); duplicate returns same job |
| Malicious upload (polyglot, bomb) | Sniff magic bytes; size cap; dimension probe pre-decode; re-encode PNG; pixel caps |
| EXIF/GPS leak | Re-encode strips metadata (same as fabrics) |
| Provider prompt injection via filename | Ignore client filenames for storage keys; sanitize display names |
| Log leakage | Structured logs: ids, status, bytes counts — never payloads |
| Abuse / cost runaway | Separate croquis quotas + `MY_CROQUIS_AI_ENABLED`; per-user daily gens; operator ceiling |
| Minors | See §13 — block or disable until policy approved |
| Moderation refusal | Map provider policy errors to safe UI; retain photo; no silent retry spend |

### 5.3 Storage options compared

| Option | Pros | Cons | V1 verdict |
|---|---|---|---|
| **A. Local private dir + auth FileResponse** (fabrics) | Already in prod; simple VPS; tested IDOR suite | Single-host; backup ops manual | **Recommend** |
| B. S3/MinIO private bucket + short signed GET | Better multi-host | New infra, IAM, URL expiry bugs | Later if multi-node |
| C. `/static/uploads` + obscure names | Easy | **Public**; CF/Nginx may expose | **Forbidden** |
| D. DB BYTEA | Simple backup story | Bloats Postgres; bad for large photos | Reject |

---

## 6. Storage and deletion lifecycle

| Event | Source photo | Generated croquis | Drafts / Saved Designs |
|---|---|---|---|
| Upload | Create asset `kind=source` | — | — |
| Generate accept | Retained (default) or user opt-out later | Create asset `kind=generated`, pin version | References `personalCroquisId`+`version` |
| Soft-delete croquis from library | Unchanged | `deleted_at` set; hidden from picker | Still renders for owner via include_deleted image GET |
| Soft-delete source only | `deleted_at`; cannot regenerate from it | Generated remains | Designs unaffected |
| Hard-delete (future / GDPR) | Secure unlink + tombstone | Same; designs show unavailable placeholder **without** switching to another model or clearing ink | Explicit PM-approved flow |
| User account delete | Cascade per existing user FK policy | Cascade | Existing design ownership rules |

**Critical:** Deletion must **never** silently change `model` to a builtin or wipe strokes/fills.

---

## 7. Data model and API contracts (proposed — no migration in this PR)

### 7.1 Tables (illustrative)

**`private_media_assets`**

- `id` UUID PK  
- `owner_id` UUID FK users  
- `kind` enum: `croquis_source` \| `croquis_generated`  
- `content_type`, `width`, `height`, `byte_size`  
- `storage_key` (under `private_croquis/…`)  
- `sha256` (optional integrity)  
- `created_at`, `deleted_at`

**`personal_croquis`**

- `id` UUID PK  
- `owner_id` UUID FK  
- `source_asset_id` UUID FK  
- `generated_asset_id` UUID FK nullable until success  
- `status` enum: `uploaded` \| `consent_recorded` \| `queued` \| `running` \| `succeeded` \| `failed` \| `rejected` \| `accepted`  
- `version` int (increment on re-generate accept)  
- `consent_version` str  
- `provider_job_id` / `provider_generation_id` nullable  
- `cost_cents` nullable  
- `idempotency_key` unique per owner  
- `error_code` safe nullable  
- `created_at`, `updated_at`, `deleted_at`

### 7.2 Draft / Saved Design reference

Extend `StudioDraftDocument` / Saved snapshot:

```ts
model: ... | 'personal'
personalCroquisId: string | null
personalCroquisVersion: number | null
```

- Legacy `female`/`male`/builtins/`blank`/`custom` unchanged.
- `custom` remains session-only blob path (or UI redirects users to Create My Croquis for durability).
- Fingerprint/serialization must include personal ids so OCC/cloud sync does not drop them.
- Preview/export resolve reference via authenticated fetch → object URL; if 404, paint without reference + non-destructive notice.

### 7.3 API sketch (`/api/v1/personal-croquis`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/photos` | Upload source (no AI) |
| GET | `` | List accepted croquis (library) |
| GET | `/{id}` | Status / metadata |
| POST | `/{id}/consent` | Record consent version |
| POST | `/{id}/generate` | Enqueue generation (requires consent + gate) |
| POST | `/{id}/accept` | Pin as library croquis |
| POST | `/{id}/reject` | Discard generation; keep source optional |
| DELETE | `/{id}` | Soft-delete library entry |
| GET | `/assets/{asset_id}/image` | Owner-auth bytes |

All routes: auth required, rate-limited, ownership enforced.

### 7.4 Feature flags

| Flag | Default | Notes |
|---|---|---|
| `MY_CROQUIS_AI_ENABLED` (BE) | `false` | Fail closed; Stage B uses mock provider regardless |
| `VITE_MY_CROQUIS_UI_ENABLED` (FE) | `false` | UI entry visibility; independent of Magic/FrontBack/Registration |
| Existing Magic / Dual / Professional flags | unchanged | No coupling |

Prod assert scripts must be extended in implementation stages so croquis UI flag defaults stay fail-closed and **#136 Studio gates remain enforced**.

---

## 8. Studio reference geometry / persistence

| Rule | Spec |
|---|---|
| Design plane | 768×1024 (unchanged) |
| Paper | 1280×1536, origin (-256,-256) |
| Placement | Fit-contain generated PNG into 768×1024; letterbox transparent; do not stretch to paper |
| Layer order | Croquis under fills under ink (existing) |
| Pan/zoom/Fill/eraser | Unchanged coordinate math |
| Thumbnails / PNG export | Use same reference resolver as live canvas |
| Front/Back | Personal croquis on front only; back has no fabricated reference |
| Reopen fidelity | Bind `personalCroquisId`+`version`; never remap to another croquis |

Generated asset target raster: prefer **768×1024** PNG with transparency, or 1024×1536 provider output center-cropped/fit into 768×1024 at accept time (deterministic preprocess). Exact preprocess pipeline is an implementation detail; acceptance tests lock visual plane alignment.

---

## 9. AI provider alternatives and cost

### 9.1 Options

| Approach | Fit | Privacy | Cost | V1 |
|---|---|---|---|---|
| **OpenAI `images.edit` + `gpt-image-2.5-sunburst`** (existing Magic path) | Strong style control from photo+prompt | Photo leaves VPS to provider — disclose in consent | Token-priced | **Recommend Stage C** |
| `gpt-image-2.5-flare` | Faster everyday | Same | Same rates | Optional A/B later |
| Local CV only (pose/edge) | Weak fashion croquis quality | Stays on-box | ~$0 | Insufficient alone for product promise |
| Third-party specialty | Unknown | Extra vendor review | Unknown | Out of scope V1 |

### 9.2 Official pricing (retrieved 2026-10-30)

Source: [OpenAI Pricing](https://developers.openai.com/api/docs/pricing) · [GPT Image 2.5 Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)

| Token class | Standard price |
|---|---|
| Text input | $5 / 1M |
| Image input | $8 / 1M |
| Image output | $30 / 1M |

Notes:

- GPT Image 2 calculator **does not** estimate GPT Image 2.5 token use.
- Direct `/v1/images/edits` does **not** use cached image-input pricing.
- FashionRise historical isolated Sunburst edit (synthetic, short brief) ≈ **$0.048** (`docs/incidents/P1-54-LIVE-SUNBURST-VALIDATION.md`) — **not** a guarantee for personal croquis; real cost **unknown** until offline measurement with representative fixtures.
- Optional vision/chat preprocessing (if used) adds `gpt-6-luna` tokens — separate line item.
- **No live provider calls in this design assignment.**

### 9.3 Cost / abuse controls (proposed)

- `MY_CROQUIS_AI_ENABLED=false` until owner auth.
- Per-user: e.g. N generations / day (PM pick; suggest **3**/day beta).
- Per-run soft estimate shown pre-confirm; hard reject if operator croquis ceiling exceeded.
- Idempotent generate; explicit user retry only.
- `max_retries=0` at provider client (match Magic edit discipline).
- Record `cost_cents` from usage when available; else mark unknown.

---

## 10. Test / acceptance matrix (future implementation)

| # | Case | Stage |
|---|---|---|
| T1 | User A cannot GET User B croquis/asset (404) | A |
| T2 | Anon GET asset → 401 | A |
| T3 | Asset id under `/static/uploads` → 404 | A |
| T4 | Soft-deleted still owner-retrievable for historical design | A |
| T5 | Oversized / wrong MIME / dimension bomb rejected | A |
| T6 | EXIF GPS absent after normalize | A |
| T7 | Generate without consent → 400 | B/C |
| T8 | AI gate off → no provider call (mock asserts) | B/C |
| T9 | Idempotent generate returns same job | C |
| T10 | Failed generation: safe error; photo retained; $ recorded only if spent | C |
| T11 | Quota / ceiling exceeded → no call | C |
| T12 | Source deleted: cannot regenerate; accepted croquis still paints | A/B |
| T13 | Croquis library soft-delete: drafts reopen with same ink + reference if bytes kept | B |
| T14 | Save/refresh/reopen retains exact croquis version | B |
| T15 | Front/Back isolation — no fake back reference | B |
| T16 | Legacy builtin/legacy female/male drafts untouched | B |
| T17 | Draw / Fill / eraser / pan / zoom regressions | B |
| T18 | Desktop / tablet / mobile wizard smoke | B/D |
| T19 | Error paths non-destructive to draft ink | B |
| T20 | Prod Vite assert still enforces #136 Studio gates | B/D |
| T21 | Minors policy enforcement (once decided) | C/D |

Offline fixtures/mocks only until Stage D authorized paid tests.

---

## 11. Phased delivery plan

### Stage A — Private asset / storage foundation

- **Scope:** BE models + migration `012`, private_croquis storage, upload/list/get/delete image routes, ownership tests. No Studio UI AI.
- **Reuse:** fabric_asset_service, LocalStorageBackend, upload_validation.
- **New:** personal_croquis models/routes/services; alembic 012.
- **Tests:** T1–T6, T12 (storage half).
- **Security:** static-path probe, cache headers, log redaction.
- **Accept:** IDOR suite green; bytes never public.
- **Rollback:** drop routes/flag; migration reverse if unused.
- **Blockers:** none beyond PM design accept.

### Stage B — Studio integration + mock generation

- **Scope:** FE wizard, `VITE_MY_CROQUIS_UI_ENABLED`, mock generator (deterministic PNG fixture), draft/saved persistence fields, geometry tests, Front-only behavior.
- **Reuse:** useStudioEditor, modelLibrary, savedDesign, paperBounds.
- **DB/API:** consume Stage A; mock sets `generated_asset_id` without provider.
- **Tests:** T7–T8 (mock), T13–T20.
- **Accept:** end-to-end with mock; reopen fidelity; no paid calls.
- **Rollback:** FE flag off.
- **Depends:** A.

### Stage C — AI generation integration

- **Scope:** `MY_CROQUIS_AI_ENABLED`, worker/provider adapter, consent enforcement, idempotency, quotas, failure mapping.
- **Reuse:** sketch_openai images.edit patterns, worker queue patterns — **new job type**, not Magic look jobs.
- **Tests:** T8–T11 with provider mocks; contract tests for usage/cost fields.
- **Accept:** mock provider suite; live calls **forbidden** until Stage D auth.
- **Rollback:** BE flag false.
- **Depends:** A+B; PM prompt/policy decisions (§13).

### Stage D — Controlled release + owner acceptance

- **Scope:** Prod readiness checklist; Nginx/Access unchanged; staged FE/BE deploy plan; owner mobile QA; **separately authorized** single paid generation tests.
- **Accept:** owner checklist (§10 product) + privacy smoke.
- **Rollback:** prior immutable FE/BE releases; flags off.
- **Depends:** C + owner auth for paid + deploy.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Provider sends photo off-box | Explicit consent; retention disclosure; minimize source retention |
| Quality ≠ fashion croquis | Prompt fixtures; accept/reject UX; mock-first |
| Cost surprise | Separate ceilings; estimate UI; low daily quota |
| Geometry drift vs #134 paper | Lock tests to 768×1024 fit-contain on 1280×1536 paper |
| Breaking #136 gates | Keep assert-prod-vite-flags; croquis flags independent |
| Deletion breaks designs | Soft-delete + include_deleted; never silent model swap |
| Scope creep (measurements, back view) | Explicit V1 non-goals |
| Branching from `main` loses FE recovery | Stack on #137 lineage until canonical merge strategy decided |

---

## 13. Explicit decisions requiring PM / owner approval

1. **Minors:** Block uploads under 18 (self-attestation + policy) vs disable feature until legal review — **recommend: disable Create My Croquis for anyone who does not attest “I am 18+ and have rights to this photo”; no child-photo pipeline in V1**.
2. **Source retention default:** Keep source until user deletes vs auto-delete source N days after accept.
3. **Daily generation quota** and operator croquis spend ceiling amounts.
4. **Whether session `custom` upload remains** alongside Create My Croquis or is removed from Models UI.
5. **Provider model:** lock `gpt-image-2.5-sunburst` vs allow flare.
6. **Back-side UX copy** when personal croquis selected.
7. **Hard-delete / GDPR export** timeline beyond soft-delete.
8. **Canonical git strategy:** when/how #137 recovery merges vs continuing stacked FE PRs.
9. **Stage D paid test authorization** — never implied by design accept.
10. **Consent copy / privacy policy URL** final legal text.

---

## 14. Recommended first implementation PR scope

**After design acceptance, first code PR = Stage A only:**

- Alembic `012_personal_croquis` (+ private media assets as designed)
- `LocalStorageBackend` private_croquis root
- Owner-auth CRUD + image routes
- Focused IDOR / static-path / validation tests
- `MY_CROQUIS_AI_ENABLED` setting present and **false**
- No FE wizard, no worker provider calls, no production deploy

Base that PR on the then-current accepted lineage (prefer #137 recovery line until PM says otherwise). Keep docs-only vs code PRs separate.

---

## Appendix A — Non-goals (V1)

- Body measurements / POM / size prediction  
- Synthetic back croquis from one front photo  
- Public sharing of personal croquis  
- Replacing builtin library  
- Coupling to Magic Dual generation  
- Using `/static/uploads`  
- Live paid calls during design or Stage A/B  

## Appendix B — Verification of this design checkpoint

- Code inspection of FE/BE paths listed above  
- Official OpenAI pricing pages retrieved 2026-10-30  
- **0** provider/paid calls  
- **0** production changes  
- **0** migrations / runtime code in this PR  
- Docs-only draft PR stacked on #137 lineage  
