# FashionRise Unity ↔ FastAPI backend

## Summary

The Unity client can run in **mock mode** (offline-friendly defaults) or **API mode** (real `http(s)://…/api/v1` calls). UI screens depend only on `AppServices` interfaces; HTTP lives under `Assets/FashionRise/Infrastructure/Api/`.

## Configuration (Unity)

On the **`FashionRiseApp`** component:

- **`Api Config`**
  - **`Base Url`**: e.g. `http://127.0.0.1:8000/api/v1` (no trailing slash required).
  - **`Request Timeout Seconds`**: default 30.
  - **`Use Mock Services`**: when **true**, the app uses `Mock*` services (**default: false** — day-to-day dev uses FastAPI).
  - **`Use Api Services`**: when **true**, the app uses the HTTP stack (**default: true**).
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
| `UserProfileApiService` | `IUserProfileService` → `/profiles/*` (includes **reputation** + aggregate fields on `ProfileRead`) |
| `DesignApiService` | `IDesignSaveService` → `/designs/*` (revisions + save) |
| `DesignHandoffApiService` | `IDesignHandoffService` → `/designs/{id}/handoff?export_kind=…` |
| `MaterialApiService` | `IMaterialCatalogService` → `/materials` |
| `TemplateApiService` | `IGarmentTemplateService` → `/templates` |
| `PaletteApiService` | `IColorPaletteService` → `/palettes` |
| `GalleryApiService` | `IGalleryService` → `/gallery`, `/gallery/user/{user_id}`, item comments/likes, `POST /gallery` |
| `FollowApiService` | `IFollowService` → `/profiles/.../follow`, `/profiles/me/following-ids`, follow-status |
| `RatingApiService` | `IRatingService` → `/ratings` |
| `UploadApiService` | `POST /uploads/image` |
| `ExportApiService` | `POST /exports`, `GET /exports/design/{id}` |
| `AIJobApiService` | `IAIEnhancementService` → `/ai/jobs` |
| `PublishingExportService` | `IExportService` decorator: `UnityPngExportService` then upload + register export when `IAuthService.HasBackendSession` |

JSON uses **Newtonsoft.Json** with **snake_case** naming to match FastAPI’s default payloads.

## Share links (Unity)

- **`ApiConfig`**: optional **Share Web Base Url** (e.g. `https://fashionrise.app`) → links look like `{base}/gallery/item/{gallery_item_uuid}`. If empty, **`Share Url Scheme`** (default `fashionrise`) → `fashionrise://gallery/{uuid}` for future Android / universal links.
- **`IShareLinkService`**: `BuildGalleryItemUrl`, `BuildShareCardText` (title + URL + optional image URL for chat rich previews).
- After **Publish to gallery**, the client tries a **native share sheet** (iOS/Android) for the share card, else **clipboard**; **Design detail** has **Copy** and **Share…** for link and card. Same pattern for **spec-sheet PDF URL** where supported.
- **Gallery preview capture:** `UnityPngExportService` saves the screenshot with a **full path** under `Application.persistentDataPath` (required on Windows/macOS Editor so `PublishingExportService` reads the same file for `POST /uploads/image`).

## Auth behaviour

- **No guest mode:** QA and dev use **register/login** (or **mock sign-in** when the app is in mock backend mode). There is no tokenless “continue as guest” on the API stack.
- **Cold start:** if PlayerPrefs still holds access/refresh tokens, `SplashScreen` calls `TryRestorePersistedSessionAsync` (`GET /auth/me`); on success navigation skips **Welcome** and opens **Home**.
- **Register / login:** tokens stored; `Authorization: Bearer` applied on authenticated routes.
- **Sketch / AI pipeline:** `TokenAwareSketchPipelineService` calls FastAPI when `HasBackendSession` (tokens present); otherwise local mocks (offline or mock backend).
- **Logout:** `SignOutAsync` clears tokens and cached user id on `AuthApiService`.

## Screens wired to the API (via interfaces)

| Screen | Behaviour |
|--------|-----------|
| `LoginChoiceScreen` | Mock **Sign in (mock)** only when **not** using the API backend; in API mode that control is **hidden** and email/password/username + register/login are shown |
| `ProfileScreen` | Profile/stats; **Reputation** (score + tier) + followers; **Refresh**; **Following: N**; **My public gallery** → `Gallery` + `GalleryNavContext`; draft list when API + signed in |
| `HomeDashboardScreen` | Shows **Authoring mode: Guided / Pro** (from `AuthoringModePreferences`) |
| `SettingsScreen` | **Toggle Guided / Pro mode**; draft autosave controls; **Sign out** |
| `CreateDesignScreen` | Catalogs from API when in API mode; **Guided** hides pro-only buttons; **Publish to gallery** runs PNG export + upload (no `POST /exports` for that preview — `SkipExportRegistration`) then `POST /gallery` with `image_url` when `HasBackendSession`; handoff **copy / spec / PDF** tools in **Pro**; **Export PNG** still registers exports |
| `GalleryScreen` | Community feed (`GallerySort`: newest / top rated / trending / **following**); optional **creator filter** via `GalleryNavContext`; **Community feed (all creators)** clears filter; **401** hint for anonymous following feed |
| `DesignDetailScreen` | Item + design summary + **rating 1–10** + like + **follow/unfollow** + **comment** + **share (native / copy)** + owner **handoff** (copy / save / spec / PDF open+share+download) + **Open creator's public gallery** |

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
