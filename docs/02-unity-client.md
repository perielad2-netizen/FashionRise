# FashionRise — Unity client architecture

## Root folder layout

All project code and content under **`Assets/FashionRise/`**:

| Path | Responsibility |
|------|----------------|
| **`Core/`** | App lifecycle, composition root, DI installers, logging, errors/results, main-thread helpers, global constants. |
| **`Domain/`** | Entities, value objects (e.g. design ids, rating scores), validation that must hold on-device; minimize `UnityEngine` in pure types. |
| **`Application/`** | Use-cases: guest/login, home dashboard, create-design flow, save/publish, gallery, ratings, PNG export, AI job requests. |
| **`Services/`** | **Interfaces only**: `IAuthService`, `IUserProfileService`, `IDesignSaveService`, `IMaterialCatalogService`, `IGarmentTemplateService`, `IColorPaletteService`, `IGalleryService`, `IRatingService`, `IExportService`, `IAIEnhancementService`, `INavigationService`. HTTP/upload wiring lives in Infrastructure (`*ApiService`, `ApiClient`). |
| **`Infrastructure/`** | **Adapters**: HTTP client, auth/refresh, JSON, DTO↔domain mappers, file IO, PNG encoding; `Api/` routes; `Mocks/` offline implementations. |
| **`UI/`** | Reusable controls: buttons, cards, sliders, palette widgets, typography; touch-friendly; **no** business rules. |
| **`Presentation/`** | Screens/flows: onboarding, guest/login placeholder, home, create flow, template picker, fabric/material picker, color palette, model preview placeholder, gallery/profile, export. |
| **`Data/`** | Client DTOs if kept here, cache models, catalog merge, optional offline queue. |
| **`Content/`** | ScriptableObjects: style tokens, default catalogs, feature flags. |
| **`Config/`** | Endpoints per environment, build flavor, tablet/phone breakpoints. |
| **`Editor/`** | Editor-only tools; no runtime dependency. |
| **`ArtPlaceholders/`** | Temporary art for vertical slices. |

## Feature ↔ layer mapping

| System | Where it lives |
|--------|----------------|
| App startup | `Core/` + `Application/` bootstrap + presentation entry |
| Navigation | `Services/INavigationService` + presentation flow coordinators |
| Onboarding | `Presentation/` + use-cases |
| Guest / login placeholder | `Presentation/` + `IAuthService` (mock vs API) |
| Home dashboard | `Presentation/Home` + `LoadHomeDashboard` use-case |
| Create design flow | `Presentation/Design` + orchestrating use-cases |
| Garment template selection | Presentation + `ICatalogService` + `Content` defaults |
| Fabric / material selection | Same + materials API |
| Color palette selection | Same + palettes API |
| Realistic model preview (placeholder) | `Presentation/Preview` + URP scene hooks |
| Gallery / profile | `IGalleryService`, `IUserProfileService` |
| PNG export | Export use-case + infrastructure encode + upload/register export |

## Design principles

- **Tablet-first**, **mobile-supported**, **desktop-ready** layout strategy (single codebase, policy-driven density).
- **Touch-friendly**, **premium** visual language — aspirational, realistic fashion, not childish.
- **Modular services**: UI depends on interfaces; swap mock/API at composition root.
- **URP** for rendering; keep preview/scene setup isolated from business logic.

## Implementation status (V1)

- **Source:** `FashionRise/Assets/FashionRise/` (see `README_Unity.md` in that folder).
- **Composition:** `FashionRiseApp` + `AppServices` (mocks **or** HTTP API via `ApiConfig`) + `ScreenController` + `NavigationService`.
- **Docs:** `unity-architecture-notes.md`, `unity-screen-flow.md`, `unity-services.md`, `unity-backend-integration.md` in this `docs/` folder.

_Add assembly definitions, scene names, and URP asset paths as you lock the project._
