# Create My Croquis V1 — Implementation-Ready Design

**Status:** DESIGN ONLY — Technical PM **PARTIAL PASS** · Stage A **HOLD** pending corrections below (2026-10-30 follow-up)  
**Issue:** [#135](https://github.com/perielad2-netizen/FashionRise/issues/135)  
**PR:** [#138](https://github.com/perielad2-netizen/FashionRise/pull/138) (docs-only draft, stacked on #137)  
**Date:** 2026-10-30  
**Base lineage:** PR [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) tip (accepted production FE recovery `2dfcaba0`)  
**Production baseline (do not assume = `main`):** FE `2dfcaba0` / source `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` · BE+worker `6cc317ec` · Alembic `011`  
**Gates:** FRONT_BACK/MAGIC/DUAL ON · REGISTRATION OFF · API `/api/v1` · CF Access + AOP unchanged  
**This document authorizes nothing:** no Stage A implementation, migration, deploy, paid AI, real-photo collection, or production flag changes until separately accepted after final PM PASS.

---

## 1. Executive decision and recommended architecture

**Product promise:** Generate a **personal fashion illustration reference** (front-facing line-art croquis) from a fully clothed photo, then use it as the Studio drawing underlay. Not a body scan, measurement source, fit simulator, or manufacturing POM input.

**Recommended V1 architecture (simplest secure path on current VPS):**

1. **Consent-gated private media** — photos stay **local in the browser** until the user records **storage/privacy consent**; only then may bytes hit the server. **AI/provider consent** is a separate later step before generation. Adults-only beta attestation required (does **not** prove age).
2. **Dedicated private croquis storage** — new `LocalStorageBackend` methods rooted at `private_croquis/` (sibling of `private_fabrics/`). Current `save_private_file` is **hardwired to fabrics** and must **not** be reused under a croquis key. Never `/static/uploads`.
3. **Append-only immutable versions** — `personal_croquis` (library identity) + `personal_croquis_version` rows. Each accepted generation is a new immutable `(croquis_id, version) → generated_asset_id` mapping. Drafts/Saved Designs pin exact version; regeneration never mutates older pins.
4. **Studio reference** — durable `model=personal` + `personalCroquisId` + `personalCroquisVersion`. Legacy builtins/`custom`/`blank` unchanged. Front-only V1.
5. **Fail-closed gates (independent):**
   - `MY_CROQUIS_UPLOAD_ENABLED=false` — blocks production photo upload/storage API
   - `MY_CROQUIS_AI_ENABLED=false` — blocks provider generation
   - `VITE_MY_CROQUIS_UI_ENABLED=false` — hides wizard entry
   - Stage B mocks are **test/offline only**, never a public bypass
6. **Geometry** — EXIF orientation → then strip/re-encode → **deterministic full-body fit-contain** into 768×1024 with transparent padding (**no center-crop** of the subject). Paper 1280×1536 / origin (-256,-256) unchanged.
7. **Phased delivery** — A gated private storage → B Studio + offline mock → C spend-reserved AI → D controlled release.

**Rejected shortcuts:** upload-before-consent; mutable single-row version repoint; fabric `save_private_file` for croquis; public uploads; Magic look-write path; Magic’s lack of spend ceiling; Stage B mock as production path; silent model remapping after erasure.

---

## 2. Product UX

### 2.1 Happy path (consent-first)

1. Creator Studio → Models → **Create My Croquis** (requires UI gate on).
2. Requirements + privacy overview (no file transmission yet): fully clothed, full-body, front-facing, standing, good light; private storage; optional later AI provider processing; not for measurements; adults-only beta.
3. **Adults-only acknowledgment** (checkbox): “I confirm I am 18+ and have the rights to use this photo.” *Self-attestation does not independently verify age* — see §13.
4. User **selects/captures** a photo. Image stays as a **local blob** for on-device preview only (client MIME/size precheck). **No network upload.**
5. Explicit **storage/privacy consent** (versioned text): permission to store the photo privately on FashionRise servers for croquis creation; retention summary; how to delete. CTA **“Upload securely”** enabled only after consent.
6. Authenticated upload (server validates consent proof + upload gate + image rules) → server returns croquis draft id + source asset id.
7. User reviews server-normalized preview (orientation-corrected, EXIF stripped).
8. Explicit **AI/provider-processing consent** (separate versioned text) + cost/quota summary when AI gate is on. CTA **“Generate My Croquis”** — no provider call before this.
9. Progress: queued / running / failed with safe messages.
10. Preview generated line-art fit-contained on the 768×1024 plane.
11. **Accept** → creates a **new immutable version** in the library; **Reject** → discard that generation attempt (source retention per §6).
12. Selecting a library croquis sets `model=personal` with pinned id+version; drawing tools unchanged.
13. Save / refresh / reopen / Saved Design restore the **exact** pinned version.

### 2.2 Desktop / tablet / mobile

| Surface | Pattern |
|---|---|
| Desktop | Models panel + wizard modal: eligibility → local select → storage consent → upload → AI consent → generate → preview. |
| Tablet landscape | Full-height sheet; sticky primary CTA per step. |
| Mobile | Full-screen steps; camera capture preferred; one primary CTA. |

Footholds: Models CTA; optional later **My Gallery** tab. Do not invent a second Studio shell. Do not call `uploadReferenceImage` / public uploads.

### 2.3 Front/Back

- V1 personal croquis is **front-only**.
- Back side: blank / existing ink only + optional “Front-only croquis” notice.
- Never mirror/flip front as a fake back.
- Built-in rear croquis unchanged.

### 2.4 Library management

- List accepted versions (latest per croquis or flat version cards — PM prefer **latest accepted per croquis** in picker, with version pin retained in designs).
- **Archive (soft-hide):** remove from picker; historical pins still resolve if bytes retained.
- **Permanent delete:** user-initiated erasure (§6) — historical designs show unavailable reference without remapping or wiping ink.

---

## 3. Existing-code findings (verified)

### 3.1 Frontend

| Area | Finding | Path |
|---|---|---|
| Model library | 10 selectable builtins + legacy `female`/`male` + `custom`/`blank`. `custom` has **no** rear. | `modelLibrary.ts` |
| Custom upload | Blob URL only; refuses persistence — `/static/uploads` not owner-private. | `useStudioEditor.ts` |
| Saved designs | `snapshotFromDocument` drops custom URL/key. | `savedDesign.ts` |
| Geometry | Design 768×1024; paper 1280×1536 origin (-256,-256). | `paperBounds.ts` |
| Flags | Studio VITE gates independent; croquis flags must not weaken #136 asserts. | `assert-prod-vite-flags.mjs` |
| Private image precedent | Fabrics / Magic job image via Bearer blob fetch. | fabric/ai FE services |
| Unused upload API | `uploadsApi.uploadReferenceImage` must stay unused for croquis. | `uploadsApi.ts` |

### 3.2 Backend

| Area | Finding | Path |
|---|---|---|
| Private fabrics | Owner-scoped; `private_fabrics/`; soft-delete; auth image; not under static. | fabric model/service/routes |
| **Storage API semantics** | `LocalStorageBackend.save_private_file` / `resolve_private_file` are **hardwired to `private_fabric_root()`**, not a generic private namespace. Croquis needs **dedicated** `save_private_croquis_file` / `resolve_private_croquis_file` (or equivalent) rooted at `private_croquis_subdir`. | `storage/local.py` |
| Public mount | `upload_subdir` → `/static/uploads` — forbidden for croquis. | `main.py` |
| Upload validation | MIME sniff, size, dimension probe, PNG re-encode. | `upload_validation.py` |
| Magic | `images.edit`; look bytes still under public uploads; **no** Magic spend ceiling. | `sketch_openai.py` |
| Magic allowlist | `reference_croquis` builtins/`custom`/`blank` only. | `reference_croquis.py` |
| Techpack spend | Operator/user/run ceilings — pattern to **copy for croquis**, not Magic. | `techpack_ai.py`, config |
| Alembic | Head **011**; next would be `012_*` — not in this docs PR. | `alembic/versions/` |

### 3.3 Production hygiene

- #136 **CLOSED** (owner acceptance on `2dfcaba0`). #127/#128 **CLOSED**. #137 deployed, **unmerged**.
- Design stacks on #137 lineage; `main` ≠ live FE/BE.

---

## 4. Component / data-flow architecture

```
┌──────────── FE Studio wizard ────────────┐
│ local File/blob preview (no upload)      │
│ storage consent ──POST /consent/storage  │
│ upload ───────────POST /photos           │  (requires storage consent + UPLOAD gate)
│ AI consent ───────POST /consent/ai       │
│ generate ─────────POST /versions:generate│  (requires AI consent + AI gate + reservation)
│ accept ───────────POST /versions/{v}/accept
│ select pin ─────── model=personal + id+ver
│ paint ← GET /assets/{id}/image (auth)    │
└──────────────────┬───────────────────────┘
                   │ JWT + CF Access
┌──────────────────▼───────────────────────┐
│ FastAPI: ownership, rate limits, gates   │
│ consent proofs, spend reservation (C)    │
│ LocalStorageBackend croquis root         │
│ private_croquis/{user}/{asset}.png       │
│ Postgres: croquis + versions + assets    │
└──────────────────────────────────────────┘
```

**Filenames:** client filenames are **never** used as storage keys, prompt identities, or log fields. Display names are sanitized separately.

---

## 5. Privacy and threat model (P0)

### 5.1 Invariants

- No photo bytes leave the browser before **storage consent** + upload gate.
- No provider call before **AI consent** + AI gate + spend reservation (Stage C).
- Owner-only auth media; `Cache-Control: private, no-store`.
- No public URL, CDN cache, or logging of images/base64/paths/tokens.
- Adults-only attestation recorded; not age verification.
- #136 Studio compiled-gate asserts remain mandatory for FE releases.

### 5.2 Threats (selected)

| Threat | Mitigation |
|---|---|
| Upload without consent | Server rejects photo POST lacking valid, current `storage_consent_id` for this user/session |
| Generate without AI consent | Server rejects generate lacking `ai_consent_id` bound to same croquis/source |
| IDOR | Owner filter; cross-user → 404 |
| Path traversal / symlink | Resolve under croquis root only; reject escapes & public-root aliases |
| Mutable version repoint | Append-only version rows; drafts pin exact version |
| Orphan bytes | Atomic write + DB commit; cleanup on failure; scheduled sweeper |
| Backup exposure | Private dirs in backups; restore ACLs; expiry policy (§6) |
| Stage B bypass | Mocks only in tests / `TESTING`; not routable in prod |
| Magic-like unlimited spend | Dedicated croquis ceilings + reservation |
| Cache / static leak | Probe `/static/uploads/...` → 404 in tests; Nginx deny public static for private trees |

---

## 6. Storage implementation and deletion / retention

### 6.1 Dedicated croquis storage (correcting fabric hardwire)

**Fact:** `save_private_file` writes under `private_fabric_root()` only.

**Required implementation (Stage A):**

```text
settings.private_croquis_subdir = "private_croquis"   # sibling of private_fabrics
LocalStorageBackend.private_croquis_root()
LocalStorageBackend.save_private_croquis_file(key=..., data=...)
LocalStorageBackend.resolve_private_croquis_file(key=...)
LocalStorageBackend.delete_private_croquis_file(key=...)  # secure unlink
```

Rules:

- Key = `croquis/{owner_id}/{asset_id}.png` (UUIDs only).
- Resolve path; require `path.relative_to(private_croquis_root)`; reject if also under `public_upload_root`.
- Reject `..`, absolute paths, symlink escapes.
- **Atomic write:** write temp file in same directory → `fsync` → `rename`.
- On DB commit failure after write: best-effort unlink; enqueue sweeper retry.
- Size bounds at read and after normalize; never mount croquis root as StaticFiles.
- Image GET: owner auth + `Cache-Control: private, no-store`.

Optional later: generalize a `PrivateStore(kind=fabrics|croquis|techpacks)` — **not required** for V1 if dedicated methods are clear and tested.

### 6.2 Recommended retention defaults (owner/legal must still approve before live photos)

| Asset / event | Recommended default | Notes |
|---|---|---|
| Local blob pre-consent | Never uploaded | Browser-only |
| Source photo after successful upload | Retain **7 days** or until accept+user deletes, whichever first | Auto-expire job |
| Source after **accept** | Delete source within **24h** (keep generated only) | Reduces sensitive retention |
| Abandoned upload (no generate within 24h) | Delete source + draft croquis row | Sweeper |
| Failed generation | Keep source until expire window; no auto paid retry | |
| **Archive** (library hide) | Soft `archived_at`; bytes kept so pinned designs render | Distinct from erase |
| **Permanent delete** (user) | Tombstone row; unlink generated (+ source if any); pins → unavailable | Not silent remap |
| Account deletion | Cascade DB + **scheduled filesystem unlink** of owner croquis keys | FK cascade ≠ disk cleanup |
| Backups | Include private dirs; retain backups **≤ 30 days** then expire; restores keep ACLs | Operator runbook |
| Erasure vs backup lag | User erasure marks `erase_requested_at`; sweeper + next backup expiry removes residual copies | Disclose in privacy copy |

**Historical designs after permanent erasure:** keep strokes/fills/`model=personal`+pinned ids; reference paint fails closed with “Croquis unavailable”; **never** switch to another croquis or builtin automatically.

**Failure retry:** deletion/unlink failures logged with asset id only; exponential backoff sweeper; alert on persistent orphans.

---

## 7. Data model and API contracts (immutable versions)

### 7.1 Tables (illustrative — migration 012 only after Stage A auth)

**`private_media_assets`**

| Column | Notes |
|---|---|
| `id` UUID PK | |
| `owner_id` UUID FK | |
| `kind` | `croquis_source` \| `croquis_generated` |
| `content_type`, `width`, `height`, `byte_size`, `sha256` | |
| `storage_key` | under `private_croquis/` |
| `created_at`, `deleted_at`, `erase_requested_at` | |

**`personal_croquis`** (library identity / conversation about one subject photo lineage)

| Column | Notes |
|---|---|
| `id` UUID PK | Stable library id |
| `owner_id` UUID FK | |
| `display_name` | sanitized |
| `source_asset_id` UUID FK nullable | may be null after source expiry |
| `status` | `draft_local` semantics server-side start at `awaiting_upload` → `uploaded` → … |
| `storage_consent_id`, `adults_attestation_at` | |
| `archived_at`, `deleted_at`, `erase_requested_at` | archive ≠ erase |
| `created_at`, `updated_at` | |

**`personal_croquis_version`** (**append-only**, immutable)

| Column | Notes |
|---|---|
| `id` UUID PK | Optional surrogate |
| `croquis_id` UUID FK | |
| `owner_id` UUID FK | denormalized for ownership checks |
| `version` INT | monotonic per croquis_id starting at 1 |
| `generated_asset_id` UUID FK | **immutable** after insert |
| `status` | `generating` \| `failed` \| `rejected` \| `accepted` |
| `ai_consent_id` | required before generate |
| `provider_job_id`, `cost_cents`, `idempotency_key` | |
| `prompt_version`, `geometry_profile` | e.g. `fit_contain_768x1024_v1` |
| `created_at`, `accepted_at` | |
| **UNIQUE** `(croquis_id, version)` | |
| **UNIQUE** `(owner_id, idempotency_key)` where not null | |

**Rules:**

- Accepting a generation **INSERTs** a new version row (or transitions `generating`→`accepted` **without** changing `generated_asset_id`).
- Re-generate always allocates `version = max+1` with a **new** asset id.
- **Never UPDATE** `generated_asset_id` on an accepted row.
- Drafts/Saved Designs store `{ personalCroquisId, personalCroquisVersion }` and resolve:

```text
SELECT * FROM personal_croquis_version
 WHERE croquis_id = :id AND version = :ver AND owner_id = :user
```

Missing/erased → unavailable reference UI; ink untouched.

### 7.2 Draft / Saved Design fields

```ts
model: ... | 'personal'
personalCroquisId: string | null
personalCroquisVersion: number | null  // exact pin; required when model=personal
```

Fingerprint/OCC must include both ids. Legacy models unchanged.

### 7.3 Consent records

**`user_consent_events`** (or croquis-scoped consent table):

| Field | Notes |
|---|---|
| `id` UUID | returned to client as consent proof |
| `owner_id` | |
| `purpose` | `croquis_storage` \| `croquis_ai_provider` |
| `consent_version` | string, e.g. `storage-2026-10-30` |
| `adults_attested` | bool (required true for beta) |
| `text_hash` | hash of shown consent copy |
| `created_at` | |

**Server enforcement:**

- `POST /photos` requires `storage_consent_id` owned by user, purpose=`croquis_storage`, consent_version in allowlist, adults_attested, age < e.g. 1 hour (or bound to croquis draft id).
- `POST …/generate` requires `ai_consent_id` purpose=`croquis_ai_provider`, bound to same croquis/source, allowlisted version; UI disabled state is insufficient alone.

### 7.4 API sketch (`/api/v1/personal-croquis`)

All routes: auth, rate limits, ownership. Upload/generate additionally require gates.

| Method | Path | Gate / consent |
|---|---|---|
| POST | `/attestations/adults` | record adults attestation |
| POST | `/consent/storage` | returns `storage_consent_id` |
| POST | `/consent/ai` | returns `ai_consent_id` |
| POST | `/photos` | **UPLOAD gate** + storage consent + multipart |
| GET | `` | list non-archived croquis + latest accepted version summary |
| GET | `/{id}` | metadata |
| GET | `/{id}/versions/{version}` | exact version resolver |
| POST | `/{id}/versions/generate` | **AI gate** + AI consent + spend reservation |
| POST | `/{id}/versions/{version}/accept` | pin into library |
| POST | `/{id}/versions/{version}/reject` | |
| POST | `/{id}/archive` | hide from picker |
| DELETE | `/{id}` | permanent erase request |
| GET | `/assets/{asset_id}/image` | owner auth bytes |

### 7.5 Feature / activation gates

| Flag | Default | Controls |
|---|---|---|
| `MY_CROQUIS_UPLOAD_ENABLED` | **false** | Production photo upload/storage API |
| `MY_CROQUIS_AI_ENABLED` | **false** | Provider generation / spend |
| `VITE_MY_CROQUIS_UI_ENABLED` | **false** | Wizard visibility |
| Stage B mock provider | test/offline only | `TESTING` or non-mounted test double — **not** a public route |

AI gate **must not** alone enable photo collection. Upload gate **must not** alone enable paid generation. Keep #136 FRONT_BACK/MAGIC/DUAL/REGISTRATION assert suite intact and independent.

---

## 8. Studio reference geometry / persistence

| Rule | Spec |
|---|---|
| Design plane | 768×1024 unchanged |
| Paper | 1280×1536, origin (-256,-256) unchanged |
| EXIF | Apply orientation transform **before** metadata strip / PNG re-encode |
| Placement | **Deterministic full-body fit-contain** into 768×1024; transparent letterbox/pillarbox; **no subject center-crop** |
| Provider output | If provider returns opaque/non-alpha or different size, post-process with same fit-contain profile `fit_contain_768x1024_v1`; do not assume lossless alpha from provider |
| Live / preview / export | Same geometry profile id stored on version row |
| Layer order | Croquis under fills under ink |
| Pan/zoom/Fill/eraser | Unchanged |
| Front/Back | Front reference only |

---

## 9. AI provider, cost, Stage C spend controls

### 9.1 Provider

- Prefer existing `images.edit` + `gpt-image-2.5-sunburst` (official rates 2026-10-30: text in $5/M, image in $8/M, image out $30/M).
- Per-request croquis cost **unknown** until fixture measurement; historical Magic edit ≈$0.05 order is **not** a guarantee.
- **0** live calls in design work.

### 9.2 Stage C concurrency-safe spend (required design)

Do **not** inherit Magic’s unlimited budget. Follow techpack-style ceilings with croquis-specific settings, e.g.:

- `MY_CROQUIS_AI_SPEND_CEILING_USD` (operator, default 0 → fail closed)
- `MY_CROQUIS_AI_MAX_USD_PER_USER_DAY`
- `MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY` (suggest **3**)
- `MY_CROQUIS_AI_MAX_USD_PER_RUN` soft estimate gate

**Reservation protocol:**

1. Begin DB transaction; lock user spend row / advisory lock.
2. Sum settled + **open reservations**; reject if estimate would exceed ceilings.
3. Insert `spend_reservation` (`open`, estimate_cents, idempotency_key).
4. Enqueue job; commit.
5. On success: settle actual `cost_cents` (from usage if present); close reservation.
6. On failure with **no** provider call: release reservation ($0).
7. On **unknown** provider outcome (timeout after send): mark `reconciliation_required`; count estimate against ceiling until reconciled; **no automatic paid retry**.
8. User-visible retry only after explicit new authorization; new idempotency key or documented replay rules that cannot double-charge.

Idempotent generate: same key returns same version/job; never a second paid call.

---

## 10. Test / acceptance matrix (future)

Includes prior T1–T21 plus:

| # | Case |
|---|---|
| T22 | Photo POST without storage consent → 400; no bytes stored |
| T23 | Generate without AI consent → 400; no provider mock call |
| T24 | Upload gate off → 403/404 even if AI gate on |
| T25 | AI gate off → generate refused even if upload gate on |
| T26 | Accept v1; regenerate v2; draft pinned to v1 still resolves v1 asset |
| T27 | UPDATE of accepted `generated_asset_id` impossible / constrained |
| T28 | Permanent erase → design shows unavailable; ink preserved |
| T29 | `save_private_file` (fabric) cannot write croquis keys into fabric root under croquis API |
| T30 | Croquis path traversal / public-root alias rejected |
| T31 | Atomic write + failed commit leaves no orphan (or sweeper removes) |
| T32 | Abandoned source expired by sweeper |
| T33 | Stage B mock not reachable when `TESTING` false / prod config |
| T34 | Spend reservation blocks concurrent double-spend |
| T35 | Unknown provider outcome → reconciliation, no auto retry |
| T36 | EXIF orientation applied; GPS absent after normalize |
| T37 | Fit-contain padding stable across canvas/preview/export (no crop) |
| T38 | Adults attestation required; missing → blocked |

---

## 11. Phased delivery plan

### Stage A — Private storage foundation (**HOLD** until final PM PASS + auth)

- Consent APIs (storage) + adults attestation; upload API behind **`MY_CROQUIS_UPLOAD_ENABLED=false`**.
- Dedicated croquis storage methods; assets + croquis + version tables (version table ready even if generate is stubbed).
- IDOR / static / atomic-write / cleanup tests.
- **No** public photo collection in prod until upload gate explicitly authorized later.

### Stage B — Studio + **offline/test-only** mock

- FE wizard consent-first UX; draft pins; geometry profile tests.
- Mock generator **only** in unit/integration tests or local `TESTING` harness — **not** exposed as a production generate path that bypasses AI consent/cost.

### Stage C — AI integration

- AI consent + `MY_CROQUIS_AI_ENABLED`; reservation/quotas/idempotency/unknown-outcome handling.
- Provider adapter; still default OFF; **no** live paid calls without separate owner auth.

### Stage D — Controlled release

- Separate authorizations for: upload gate ON (photo collection), AI gate ON, paid test gens, FE UI gate.
- Owner mobile QA; privacy copy approved.

Rollback: flags off; prior immutable FE/BE releases; sweeper continues erase requests.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Consent UI-only | Server consent ids |
| Mutable version bug | Append-only table + tests T26/T27 |
| Fabric storage misuse | Dedicated croquis methods + tests |
| Backup retains erased photos | Short backup TTL + erase disclosure |
| Stage B prod bypass | Mock not mounted in prod |
| Cost runaway | Reservations; not Magic model |
| Geometry crop regression | Locked fit-contain fixtures |
| Weakening #136 gates | Independent assert suite |

---

## 13. Explicit decisions — recommended defaults vs owner/legal approval

### 13.1 Recommended engineering defaults (pending owner/legal sign-off before live photos)

| Topic | Recommended default |
|---|---|
| Minors / eligibility | **Adults-only beta**; require 18+ attestation; feature blocked without it. **Attestation ≠ age verification.** |
| Storage before AI | Local preview → storage consent → upload |
| AI consent | Separate step; versioned |
| Source retention | 7 days max; delete within 24h after accept |
| Abandoned uploads | Delete after 24h |
| Archive vs erase | Archive keeps bytes for pins; erase unlinks + unavailable UI |
| Account delete | DB cascade + filesystem sweeper |
| Backup retention | ≤ 30 days |
| Daily gens | 3 / user / day (when AI on) |
| Operator croquis ceiling | Explicit >0 required (fail closed at 0) |
| Geometry | fit_contain_768x1024_v1; no subject crop |
| Magic interoperability | **Studio-underlay only in V1**; no `reference_croquis` extension yet |
| Session `custom` upload | Keep for now; durable path is Create My Croquis |
| Provider | `gpt-image-2.5-sunburst` |

### 13.2 Must have explicit owner / legal approval before production photo collection

1. Final consent copy (storage + AI) and privacy policy URL.  
2. Adults-only policy and attestation wording (and whether stronger age checks are required).  
3. Retention/erasure/backup timelines (confirm or override §6.2).  
4. Whether source may be retained longer for dispute/safety.  
5. Quota and spend ceiling dollar amounts.  
6. Authorization to turn **`MY_CROQUIS_UPLOAD_ENABLED`** on in any environment with real users.  
7. Authorization for any paid Stage D generation tests.  
8. Canonical merge strategy for #137 vs continued stacks.

---

## 14. Recommended first implementation PR (after final PM PASS)

**Stage A only**, still fail-closed:

- Alembic `012` with assets + croquis + **version** + consent tables  
- Dedicated `private_croquis` storage API  
- Consent + gated upload routes (upload gate default false)  
- Exact-version read APIs  
- Tests T1–T6, T22, T24, T26–T32, T36 (orientation/strip unit)  
- No FE wizard required in A (or UI gate false)  
- No provider calls  

---

## Appendix A — Non-goals (V1)

- Measurements / POM / fit  
- Synthetic back croquis  
- Public sharing  
- Magic allowlist extension  
- Using `/static/uploads` or fabric `save_private_file` for croquis  
- Production Stage B mock generate  
- Live paid calls during design / Stage A  

## Appendix B — PM correction traceability (2026-10-30)

| PM item | Section |
|---|---|
| P0-A consent before upload; separate AI consent; adults-only | §2.1, §7.3, §13 |
| P0-B append-only immutable versions | §7.1, §7.2, T26–T27 |
| P0-C fabric hardwire; dedicated croquis store; retention/erasure | §3.2, §6 |
| P0-D upload gate ≠ AI gate; mock test-only; spend reservation | §7.5, §9.2, §11 |
| P1 fit-contain not crop; EXIF before strip | §8 |

## Appendix C — Verification of this docs checkpoint

- Documentation-only amendments on PR #138  
- **0** provider/paid calls · **0** production modifications · **0** migrations/runtime code  
- Stage A **not** started  
