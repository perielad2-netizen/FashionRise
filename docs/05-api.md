# FashionRise — API overview

**Base path (versioned):** `/api/v1`  
**Public ops (no prefix):** `/health`, `/ready`, `/static/uploads/`, `/docs`  
**Format:** JSON; **uploads:** `multipart/form-data`  
**Auth:** `Authorization: Bearer <access_token>` for protected routes.  
**Docs:** Swagger UI at **`/docs`** (restrict or disable in hardened production if desired).

---

## Auth (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Body: `email`, `username`, `password`, optional `display_name` → tokens (email stored **lowercased**; password trimmed before hash) |
| POST | `/auth/login` | Body: `email`, `password` → tokens (email matched **case-insensitively**; password **trimmed** before verify) |
| POST | `/auth/refresh` | Body: `refresh_token` → new access + refresh (rotation) |
| GET | `/auth/me` | Current user (`UserRead`) |

**Client expectations:** `401` on login = wrong password or unknown email (same error shape). `409` on register = duplicate email or username. If a row exists but login always fails, password likely does not match the stored bcrypt hash — use **`python scripts/set_user_password.py`** (`backend/README.md`) or **`alembic downgrade base` → `upgrade head`** and re-register for a clean dev DB.

**Note:** There is **no** `POST /auth/logout` yet; clients discard tokens. Refresh revocation happens on rotation.

---

## Profiles (`/api/v1/profiles`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/profiles/me` | Authenticated profile |
| PUT | `/profiles/me` | Partial update (`ProfileUpdate`) |
| GET | `/profiles/{user_id}` | Public profile by UUID |
| GET | `/profiles/me/following-ids` | UUIDs the current user follows — auth |
| GET | `/profiles/{user_id}/follow-status` | `{ "user_id", "following": bool }` — optional auth |
| POST | `/profiles/{user_id}/follow` | Follow creator — auth (**409** if self) |
| DELETE | `/profiles/{user_id}/follow` | Unfollow — auth |

**`ProfileRead` (computed, not all stored on `user_profiles`):** `designs_count`, `published_count`, `followers_count`, `likes_received_count`, `rating_average`, `rating_count`, **`reputation_score`** (0–100), **`reputation_tier`** (`newcomer` \| `rising` \| `established` \| `icon`). Derived from designs, gallery items, follows, likes, and per-item ratings.

---

## Catalogs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates` | List garment templates |
| GET | `/templates/{template_id}` | Template detail |
| GET | `/materials` | List materials |
| GET | `/materials/{material_id}` | Material detail |
| GET | `/palettes` | List color palettes |

**Note:** No **`GET /palettes/{id}`**; Unity `PaletteApiService` filters list client-side.

---

## Designs (`/api/v1/designs`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/designs` | Create draft (`DesignCreate`) |
| GET | `/designs/my` | Current user’s designs |
| GET | `/designs/{design_id}` | Detail (owner or public + `moderation_status=ok`) |
| PUT | `/designs/{design_id}` | Update (`DesignUpdate`) — owner only |
| DELETE | `/designs/{design_id}` | Delete — owner only |
| GET | `/designs/{design_id}/revisions` | List revision snapshots — owner |
| POST | `/designs/{design_id}/revisions` | Append snapshot (`design_data`, optional `notes`) — owner |
| GET | `/designs/{design_id}/revisions/{revision_number}` | Read one revision — owner |
| GET | `/designs/{design_id}/handoff` | Owner JSON handoff; query **`export_kind`**: `manifest_v1` (default), `spec_sheet_v1`, `spec_sheet_pdf` (generates placeholder PDF + export row) |

---

## Gallery (`/api/v1/gallery`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/gallery` | Create gallery item (`GalleryCreate`) — auth |
| GET | `/gallery` | Public feed; query **`sort`**: `newest` (default), `top_rated`, `trending`, **`following`** (Bearer required — **401** if anonymous); `limit`, `offset` |
| GET | `/gallery/user/{user_id}` | User’s **public** items |
| GET | `/gallery/{gallery_item_id}/comments` | List moderated comments |
| POST | `/gallery/{gallery_item_id}/comments` | Body: `{ "body": "..." }` — auth |
| POST | `/gallery/{gallery_item_id}/like` | Like — auth; **204**; duplicate → **409** |
| DELETE | `/gallery/{gallery_item_id}/like` | Unlike — auth; **204** |
| GET | `/gallery/{gallery_item_id}` | Detail; if **Bearer** sent, response includes **`liked_by_me`** (bool) |

**DB:** `gallery_likes`, `gallery_comments` (Alembic **`002`**); **`user_follows`** + profile follower counts (**`003`**) for `sort=following` and profile follow APIs.

---

## Ratings (`/api/v1/ratings`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ratings` | Body: `gallery_item_id`, `score` (1–10) — **upsert** per user |
| GET | `/ratings/gallery/{gallery_item_id}` | List ratings for item |

---

## Exports (`/api/v1/exports`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/exports` | Register export (`ExportCreate`) after upload |
| GET | `/exports/design/{design_id}` | List exports for design (authenticated owner context) |

---

## Uploads (`/api/v1/uploads`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/uploads/image` | Multipart field **`file`**; returns `url`, `stored_key`. Validates size, MIME, **magic bytes** (JPEG/PNG/WebP). |

---

## AI (`/api/v1/ai`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ai/sketch/clean` | V2: enqueue **`sketch_clean`** job; body optional `SketchPipelineBody` (`design_id`, `input_data`) |
| POST | `/ai/sketch/polish` | V2: enqueue **`sketch_polish`** |
| POST | `/ai/style/suggest` | V2: enqueue **`style_suggest`** |
| POST | `/ai/jobs` | Create job (`AIJobCreate`) — generic |
| GET | `/ai/jobs/{job_id}` | Job status |

Worker is still **placeholder** (job completes immediately with noop `result_data`); routes are stable for real providers later.

**Note:** **`GET /ai/capabilities`** is not implemented yet.

---

## System (root)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness (no DB) |
| GET | `/ready` | Readiness (DB `SELECT 1`) |

---

## Admin (future)

- Prefix e.g. `/api/v1/admin/...` with role checks.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05-10 | Initial endpoint list |
| 2026-05-10 | Aligned with implemented routes (PUT profiles, `/uploads/image`, exports paths, ratings paths); noted gaps (logout, palette by id, capabilities) |
| 2026-05-10 | V2 (Prompt 6): gallery sort, likes, comments; AI sketch/style routes; `liked_by_me` on gallery detail |
| 2026-05-11 | Gallery `sort=following` + **401** note; profile **follow** routes; DB note for **`003`** `user_follows` |
| 2026-05-11 | **Profiles:** `ProfileRead` reputation + aggregates; follow-status shape. **Designs:** revisions + **`handoff`** + **`export_kind`**. |
