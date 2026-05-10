# FashionRise — Unity client (V1)

Premium tablet-first foundation: **mock services**, **service interfaces**, **API stubs**, and **uGUI** screens wired through `FashionRiseApp` + `ScreenController`.

## Target platforms (shipping order)

1. **Windows PC** (standalone 64-bit) — primary desktop.
2. **Android** (phone / tablet) — same UX; sketch import uses the system gallery via `Assets/Plugins/Android/`.
3. **iOS / iPadOS** — not configured yet; bundle id placeholder is `com.fashionrise.ios` for when you add an Apple build target.

Use **File → Build Settings** to switch **PC** vs **Android**. For Google Play, use **IL2CPP** + **ARM64** (project sets **ARMv7 + ARM64**; adjust if you go 64-bit only).

## Quick start

1. Open the Unity project under `FashionRise/`.
2. Open a scene (e.g. **App**).
3. Press **Play**. If the scene has no `FashionRiseApp` yet, the project **creates the UI automatically** (splash → welcome → …).
4. Optional in Edit mode: menu **FashionRise → Create Bootstrap UI (Canvas + Screens)** to place the same hierarchy in the scene and **save** it (so Play does not spawn a fresh copy each time).

**Networking:** `FashionRiseApp` → **Api Config** defaults to **FastAPI** at `http://127.0.0.1:8000/api/v1` with mocks **off**. Run the backend locally or switch **Use Mock Services** only when you need offline UI work.

If the **Console** shows red errors, open **Window → General → Console**, fix compile errors first — Unity may not run scripts until the project compiles cleanly.

If UI clicks do not register, ensure **Active Input Handling** (Player Settings) includes **Input Manager** or add **Input System UI Input Module** to `EventSystem` instead of `StandaloneInputModule`.

Optional: assign a `FashionRiseTheme` asset (Create → FashionRise → UI Theme) on individual `ScreenBase` instances for branded tuning.

## Folder map

- `Core/` — `FashionRiseApp`, `AppServices`, navigation ids, helpers.
- `Domain/` — models (designs, materials, palettes, gallery, export).
- `Application/` — `CreateDesignSession`, export DTOs.
- `Services/` — interfaces only (`IAuthService`, `IGalleryService`, …).
- `Infrastructure/Mocks/` — offline implementations + seed data usage.
- `Infrastructure/Api/` — `ApiClient`, `ApiConfig`, `TokenStorageService`, `*ApiService` HTTP adapters, `PublishingExportService`.
- `Infrastructure/Export/` — `UnityPngExportService` (screenshot placeholder).
- `Presentation/` — screens, navigation, model-preview placeholders.
- `UI/` — `FrUiFactory`, layout helpers.
- `Data/` — static seeds (materials, templates, palettes).
- `Content/` — `FashionRiseTheme` ScriptableObject.
- `Config/` — `DeviceLayoutPolicy` (tablet vs phone heuristics).
- `Editor/` — bootstrap menu item.

## Compiler / nullable warnings

Unity 2022 may still report **CS8632** for `string?` etc. even with `"nullable": true` on the `.asmdef`. This repo adds **`Assets/csc.rsp`** with `-nullable:enable` so nullable annotations are valid project-wide. Template **TutorialInfo** scripts use `#nullable disable` so they stay quiet.

## Architecture rules

- UI calls **interfaces** on `AppServices`, not HTTP.
- Toggle **mock vs API** on the **`FashionRiseApp`** → `Api Config` (see `docs/unity-backend-integration.md`).
- Search tags in code: `[API_READY]`, `[V2_READY]`, `[AI_READY]`, `[DESKTOP_READY]`.

## Backend

REST integration: `docs/unity-backend-integration.md` (inspector setup, auth, CORS, production) and `docs/05-api.md`.
