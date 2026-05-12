# FashionRise — Database schema (PostgreSQL)

**Implementation source of truth:** SQLAlchemy models in `backend/app/models/*.py` and Alembic revisions in `backend/alembic/versions/`. This document stays **conceptual** for onboarding; if a column name or table differs from what you see in code, trust the models and migrations.

Engine: **PostgreSQL**. Migrations: **Alembic**. Types below are conceptual — finalize in migration files.

## Supporting table (recommended)

### `refresh_tokens`

Required for production **JWT refresh** (not listed in original product tables but needed for access/refresh flow).

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `token_hash` | string | Store hash only |
| `expires_at` | timestamptz | |
| `revoked_at` | timestamptz nullable | |
| `user_agent` | text nullable | |
| `created_at` | timestamptz | |

---

## Core tables

### `users`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `email` | string unique | nullable if social auth later |
| `password_hash` | string nullable | |
| `is_active` | bool | |
| `is_email_verified` | bool | |
| `role` / `user_type` | enum | user, moderator, admin |
| `moderation_state` | enum | ok, limited, suspended |
| `moderation_reason` | text nullable | |
| `admin_notes` | text nullable | admin-only via API |
| `created_at`, `updated_at` | timestamptz | |

### `user_profiles`

1:1 with `users`.

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `user_id` | UUID FK unique | |
| `display_name` | string | |
| `bio` | text nullable | |
| `avatar_asset_id` | UUID nullable | or storage key reference |
| `is_public` | bool | |
| `public_slug` or `public_id` | string unique | shareable |
| `created_at`, `updated_at` | timestamptz | |

**API note:** `GET /profiles/me` and `GET /profiles/{user_id}` return **`ProfileRead`** with extra **computed** fields (not stored as columns on `user_profiles`): `published_count`, `likes_received_count`, `rating_count`, `reputation_score`, `reputation_tier` — see `docs/05-api.md`.

### `garment_templates`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `name`, `description` | string/text | |
| `category` | string | |
| `preview_asset_id` | UUID nullable | |
| `template_data` | JSON | panels, defaults, rig hints |
| `sort_order` | int | |
| `is_active` | bool | |
| `source` | string | system, partner |
| `created_at` | timestamptz | |

### `garment_designs`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `owner_user_id` | UUID FK | |
| `title`, `description` | string/text | |
| `status` | enum | draft, published, archived |
| `visibility` | enum | private, link_only, public |
| `template_id` | UUID FK nullable | |
| `thumbnail_asset_id` | UUID nullable | |
| `design_data` | JSON | editor state |
| `published_at` | timestamptz nullable | |
| `moderation_status` | enum | pending, approved, rejected, flagged |
| `moderation_labels` | JSON/text nullable | |
| `moderation_updated_at` | timestamptz nullable | |
| `internal_tags` | JSON nullable | admin |
| `quality_score` | numeric nullable | future |
| `created_at`, `updated_at` | timestamptz | |

### `material_definitions`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `name`, `category` | string | |
| `preview_asset_id` | UUID nullable | |
| `material_params` | JSON | PBR/drape hints for client |
| `sort_order` | int | |
| `is_active` | bool | |
| `created_at` | timestamptz | |

### `color_palettes`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `name` | string | |
| `scope` | enum | system, user |
| `owner_user_id` | UUID FK nullable | |
| `colors` | JSON | hex + labels |
| `is_active` | bool | |
| `created_at` | timestamptz | |

### `gallery_items`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `garment_design_id` | UUID FK | unique if one row per design |
| `owner_user_id` | UUID FK | |
| `title` | string nullable | display override |
| `blurb` | text nullable | |
| `is_featured` | bool | |
| `featured_rank` | int nullable | |
| `published_at` | timestamptz | |
| `visibility_override` | bool/text | hidden_from_public |
| `moderation_state` | enum | |
| `report_count` | int default 0 | |
| `created_at` | timestamptz | |

### `ratings`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `gallery_item_id` | UUID FK | preferred public surface |
| `rater_user_id` | UUID FK | |
| `score` | smallint | 1–10 |
| `comment` | text nullable | |
| `created_at`, `updated_at` | timestamptz | |

**Constraint**: unique (`gallery_item_id`, `rater_user_id`).

_Alternative_: FK to `garment_design_id` if gallery is implicit — pick one model and keep API consistent.

### `design_exports`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `garment_design_id` | UUID FK | |
| `owner_user_id` | UUID FK | |
| `export_kind` | string | png, handoff_zip, … |
| `asset_storage_key` | string | |
| `mime_type` | string | |
| `width`, `height` | int | |
| `byte_size` | bigint | |
| `checksum` | string nullable | |
| `scan_status` | enum nullable | pending, clean, rejected |
| `created_at` | timestamptz | |

### `ai_jobs`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `user_id` | UUID FK | |
| `job_type` | string | sketch_enhance, … |
| `status` | enum | queued, running, succeeded, failed, cancelled |
| `provider` | string nullable | |
| `idempotency_key` | string unique | |
| `input_payload` | JSON | |
| `output_export_id` | UUID FK nullable | → design_exports or future asset |
| `error_code`, `error_message` | string nullable | |
| `created_at`, `updated_at` | timestamptz | |

### `design_revisions`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `garment_design_id` | UUID FK | |
| `revision_index` | int | |
| `parent_revision_id` | UUID FK nullable | |
| `snapshot_data` | JSON | |
| `label` | string nullable | |
| `created_by_user_id` | UUID FK | |
| `created_at` | timestamptz | |

**Constraint**: unique (`garment_design_id`, `revision_index`).

## Indexes (initial suggestions)

- `garment_designs(owner_user_id, status)`
- `garment_designs(visibility, published_at)` for feeds
- `gallery_items(published_at)`, `gallery_items(is_featured, featured_rank)`
- `ratings(gallery_item_id)`
- `ai_jobs(user_id, status)`

_Update columns and enums here when migrations land._
