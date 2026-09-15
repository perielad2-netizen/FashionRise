# FashionRise — Unity client (V1)

Premium tablet-first foundation: **service interfaces**, **FastAPI by default**, optional **mocks**, and **uGUI** screens wired through `FashionRiseApp` + `ScreenController`.

## Target platforms (shipping order)

1. **Windows PC** (standalone 64-bit) — primary desktop.
2. **Android** (phone / tablet) — same UX; sketch import uses the system gallery via `Assets/Plugins/Android/`.
3. **iOS / iPadOS** — sketch import uses **Photos** (`PHPicker` on iOS 14+, legacy picker on 12–13) via `Assets/Plugins/iOS/FashionRiseGalleryPickBridge.mm`; bundle id placeholder is `com.fashionrise.ios` until you finalize signing.

Use **File → Build Settings** to switch **PC** vs **Android**. For Google Play, use **IL2CPP** + **ARM64** (project sets **ARMv7 + ARM64**; adjust if you go 64-bit only).

## Quick start

1. Open the Unity project under `FashionRise/`.
2. Open a scene (e.g. **App**).
3. Press **Play**. If the scene has no `FashionRiseApp` yet, the project **creates the UI automatically** (splash → welcome → …).
4. Optional in Edit mode: menu **FashionRise → Create Bootstrap UI (Canvas + Screens)** to place the same hierarchy in the scene and **save** it (so Play does not spawn a fresh copy each time).

**Networking:** `FashionRiseApp` → **Api Config** defaults to **FastAPI** at `http://127.0.0.1:8001/api/v1` with mocks **off**. Run the backend locally or switch **Use Mock Services** only when you need offline UI work.

If the **Console** shows red errors, open **Window → General → Console**, fix compile errors first — Unity may not run scripts until the project compiles cleanly.

If UI clicks do not register, ensure **Active Input Handling** (Player Settings) includes **Input Manager** or add **Input System UI Input Module** to `EventSystem` instead of `StandaloneInputModule`.

Optional: assign a `FashionRiseTheme` asset (Create → FashionRise → UI Theme) on individual `ScreenBase` instances for branded tuning.

## Folder map

- `Core/` — `FashionRiseApp`, `AppServices`, navigation ids, helpers.
- `Domain/` — models (designs, materials, palettes, gallery, export).
- `Application/` — `CreateDesignSession`, export DTOs, **PlayerPrefs** helpers (`DesignAutosavePreferences`, `AuthoringModePreferences`, **`SketchFigurePreferences`**).
- `Services/` — interfaces only (`IAuthService`, `IUserProfileService`, `IDesignSaveService`, `IDesignHandoffService`, `IGalleryService`, `IFollowService`, `IShareLinkService`, …).
- `Infrastructure/Mocks/` — offline implementations + seed data usage.
- `Infrastructure/Api/` — `ApiClient`, `ApiConfig`, `TokenStorageService`, `*ApiService` HTTP adapters (including **`DesignHandoffApiService`**), `PublishingExportService`, `TokenAwareSketchPipelineService`.
- `Infrastructure/Platform/` — **Android** gallery (`AndroidGalleryPick`, `FashionRiseAndroidBridge`), **iOS** Photos pick (`IOSGalleryPick`, same bridge `UnitySendMessage`), PC folder launchers (`PcImportsFolderOpener`, `PcHandoffsFolderOpener`).
- `Infrastructure/Export/` — `UnityPngExportService` (screenshot placeholder).
- `Presentation/` — screens, navigation, model-preview placeholders; **Guided vs Pro** authoring via `AuthoringModePreferences` (Settings toggle; Create hides pro-only tools in Guided). **Sketch canvas:** dual-layer `UiSketchPad` (croquis/photo + ink), `SketchDefaultFigureGenerator`, `SketchFigurePreferences`.
- `UI/` — `FrUiFactory`, `FrButtonEmphasis`, **`NativeShareSheet`**, **`ShareClipboard`**, layout helpers.
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

## Shipped UX (social / gallery)

- **Gallery:** Newest, Top rated, Trending, **Following** (signed-in); optional **creator-only** list via `GalleryNavContext.OwnerUserId`; **`CommunitySort`** when opening the community feed from home (default **Gallery** = newest, **Following feed** = following); **Back** from design detail keeps creator filter + sort; **Community feed (all creators)** clears creator filter in place.
- **Design detail:** Rate **1–10**, like, **follow / unfollow**, **post comment** (typed), native share actions (link/card/PDF URL share sheet + copy fallback), handoff tools (copy JSON, generate `spec_sheet_pdf`, open/share/download PDF, **save JSON/PDF to** `persistentDataPath/Handoffs`, **Open Handoffs folder (PC)**), and **open this creator’s public gallery**.
- **Profile:** **Refresh**, **Reputation** (score + tier from API), **Following** count, **My public gallery** (filtered gallery for the signed-in user).
- **Home:** **Kid front door** — **Girl model** / **Boy model** → sketch; **More…** reveals Gallery / Atelier / Profile / Settings.
- **Sketch → Magic → Share:** canvas **Magic!** auto-runs polish; **Your look** has **Share!** (`TryShareImageFile`) + **Draw again**.
- **Settings:** **Authoring mode: Guided / Pro** toggle.
- **Create design:** revision history tools; **Pro** shows full handoff/export; **Guided** keeps the flow simpler.

## Changelog (this file)

| Date | Change |
|------|--------|
| 2026-09-07 | Kid front door Home/Sketch/Magic/Result; `SketchNavContext`; `NativeShareSheet.TryShareImageFile`. |
| 2026-05-13 | Session handoff: **`00`**, **`06`**, **`02`**, **`03`**, **`05-api`**, **`unity-backend-integration`**, root **`README`** — sketch pad v2, auth, next picks. |
| 2026-05-12 | Sketch canvas: dual-layer pad, default models **`Resources/SketchReference/female_model.png`** / **`male_model.png`** (replace to update art), reference dim, brush sizes/colors, eraser. |
| 2026-05-11 | Doc sync: folder map (handoff, share, Guided/Pro, preferences); shipped UX (reputation, home/settings mode); changelog added. |
