# FashionRise Unity ↔ FastAPI backend

## Summary

The Unity client can run in **mock mode** (offline-friendly defaults) or **API mode** (real `http(s)://…/api/v1` calls). UI screens depend only on `AppServices` interfaces; HTTP lives under `Assets/FashionRise/Infrastructure/Api/`.

## Configuration (Unity)

On the **`FashionRiseApp`** component:

- **`Api Config`**
  - **`Base Url`**: e.g. `http://127.0.0.1:8000/api/v1` (no trailing slash required).
  - **`Request Timeout Seconds`**: default 30.
  - **`Use Mock Services`**: when **true** (default), the app uses `Mock*` services unless overridden below.
  - **`Use Api Services`**: when **true**, the app uses the HTTP stack (see resolution below).
  - **`Offline Mode Placeholder`**: if enabled, `ApiClient` throws before any network call (for future offline UX tests).
  - **`Retry Attempts Placeholder`**: reserved; `ApiClient.WithRetryPlaceholder` is currently a no-op pass-through.

**Resolution:** `ApiConfig.ShouldUseApiBackend()` returns **true** if `Use Api Services` is set, or if `Use Mock Services` is **cleared**. If both mock and API flags are **true**, API wins and a warning is logged.

**Editor shortcut:** **FashionRise → Use Local API (127.0.0.1:8000) — apply to scene** (`FashionRiseBootstrapMenu.cs`) sets `ApiConfig` on the scene’s `FashionRiseApp` for local backend work.

**Tokens:** `TokenStorageService` persists access/refresh tokens in **PlayerPrefs** (`fr_access_token`, `fr_refresh_token`). Replace with secure storage on shipping builds.

## HTTP stack (API mode)

| Type | Role |
|------|------|
| `ApiConfig` | Base URL, timeouts, mode flags, placeholders |
| `ApiClient` | GET/POST/PUT/DELETE, JSON (snake_case), multipart upload, bearer auth |
| `ApiResponse<T>` | Typed success / error wrapper for future call sites |
| `ApiException` | HTTP errors + FastAPI `detail` parsing |
| `TokenStorageService` | Load/save/clear JWT pair |
| `AuthApiService` | `IAuthService` → `/auth/*` |
| `UserProfileApiService` | `IUserProfileService` → `/profiles/*` |
| `DesignApiService` | `IDesignSaveService` → `/designs/*` |
| `MaterialApiService` | `IMaterialCatalogService` → `/materials` |
| `TemplateApiService` | `IGarmentTemplateService` → `/templates` |
| `PaletteApiService` | `IColorPaletteService` → `/palettes` |
| `GalleryApiService` | `IGalleryService` → `/gallery` |
| `RatingApiService` | `IRatingService` → `/ratings` |
| `UploadApiService` | `POST /uploads/image` |
| `ExportApiService` | `POST /exports`, `GET /exports/design/{id}` |
| `AIJobApiService` | `IAIEnhancementService` → `/ai/jobs` |
| `PublishingExportService` | `IExportService` decorator: `UnityPngExportService` then upload + register export when `IAuthService.HasBackendSession` |

JSON uses **Newtonsoft.Json** with **snake_case** naming to match FastAPI’s default payloads.

## Auth behaviour

- **Guest:** `SignInGuestAsync` sets a local guest id and **clears** tokens. `HasBackendSession` is **false**; cloud save/upload paths show a friendly message or skip upload. **Sketch / AI pipeline buttons** use **local mock** results in API mode so guests avoid **401** on `/ai/sketch/*`; after **login/register**, the same buttons call the real API.
- **Register / login:** tokens stored; `Authorization: Bearer` applied on authenticated routes.
- **Logout:** `SignOutAsync` clears tokens and guest flags on `AuthApiService`.

## Screens wired to the API (via interfaces)

| Screen | Behaviour |
|--------|-----------|
| `LoginChoiceScreen` | Guest; mock **Sign in (mock)** only when **not** using the API backend; in API mode that control is **hidden** and email/password/username + register/login are shown |
| `ProfileScreen` | Loads profile/stats; loading and error text |
| `CreateDesignScreen` | Catalogs from API when in API mode; export **saves draft first** when `HasBackendSession`, then PNG + optional upload |
| `GalleryScreen` | Public feed; empty-state and error handling |
| `DesignDetailScreen` | Gallery item + design detail + rating with error handling |

## Backend: CORS and static uploads

- **Desktop / Editor:** Unity is not a browser; CORS usually does not apply.
- **WebGL:** You must allow your hosting origin in `CORS_ORIGINS` (comma-separated) or use a gateway; `*` is only appropriate for dev.
- Uploaded images are served from **`PUBLIC_UPLOAD_BASE_URL`** (see backend `.env`); align this with where Unity resolves image URLs (e.g. `http://127.0.0.1:8000/static/uploads/...`).

## Production server

- Terminate TLS at Nginx (or cloud LB); proxy to Uvicorn/Gunicorn.
- Set **`Base Url`** on `FashionRiseApp` to `https://api.yourdomain.com/api/v1`.
- Use HTTPS-only tokens storage where the platform supports it; rotate refresh tokens (already supported server-side).

## Local development checklist

1. Start API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend/`.
2. `alembic upgrade head`; optional dev seed (materials/templates/palettes).
3. Unity: clear **`Use Mock Services`** or enable **`Use Api Services`**; set **`Base Url`** to `http://127.0.0.1:8000/api/v1` (use machine LAN IP from device builds).
4. Register a user from **Login** screen (password ≥ 8 characters).

## Contract

- OpenAPI at `/docs` is the DTO source of truth.
- Keep **domain** types stable; map in Infrastructure (`ApiDomainMapper`, DTOs in `ApiDtos.cs`).
