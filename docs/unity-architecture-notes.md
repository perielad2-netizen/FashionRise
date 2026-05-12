# FashionRise Unity — architecture notes (V1)

## Layers

| Layer | Role |
|--------|------|
| **Core** | `FashionRiseApp` composition root, `AppServices`, bootstrap logging |
| **Domain** | Pure models: designs, materials, palettes, gallery, export packages |
| **Application** | `CreateDesignSession`, `ExportRequest`, `UnityPngExportService` |
| **Services** | Interfaces consumed by Presentation |
| **Infrastructure** | `Mocks/*`; `Api/` — `ApiClient`, DTOs, mappers, `*ApiService` (`Auth`, `UserProfile`, `Design`, `Material`, `Template`, `Palette`, `Gallery`, `Follow`, `Rating`, `Upload`, `Export`, `AIJob`), `PublishingExportService`, `TokenStorageService` |
| **Presentation** | Screens, navigation, model preview orchestration |
| **UI** | Theme ScriptableObject + reusable uGUI components |
| **Data** | Seed data for mocks (materials, templates, palettes, gallery) |
| **Config** | `DeviceLayoutPolicy` for tablet vs phone heuristics |

## Rules

- UI **never** calls API URLs; only **interfaces** on `AppServices`.
- Lists and copy on screens come from **services** or **session**, not hardcoded business lists (enum labels for UX are allowed).
- **Navigation** is centralized: `INavigationService` + `ScreenController`.

## Extension points

- **New screen**: add `ScreenId`, `ScreenBase` subclass, register on `ScreenController`, navigate from existing UI.
- **New catalog field**: extend `MaterialDefinition` + seed + future DTO mapper `[API_READY]`.
- **Real avatar**: replace placeholder mesh/material path; keep `GarmentPreviewApplier` as the single material entry point `[V2_READY]`.
