# FashionRise Unity — services (V1)

| Interface | Mock | API implementation |
|-----------|------|---------------------|
| `IAuthService` | `MockAuthService` | `AuthApiService` |
| `IUserProfileService` | `MockUserProfileService` | `UserProfileApiService` |
| `IDesignSaveService` | `MockDesignSaveService` | `DesignApiService` |
| `IMaterialCatalogService` | `MockMaterialCatalogService` | `MaterialApiService` |
| `IColorPaletteService` | `MockColorPaletteService` | `PaletteApiService` |
| `IGarmentTemplateService` | `MockGarmentTemplateService` | `TemplateApiService` |
| `IGalleryService` | `MockGalleryService` | `GalleryApiService` |
| `IFollowService` | `MockFollowService` | `FollowApiService` |
| `IRatingService` | `MockRatingService` | `RatingApiService` |
| `IExportService` | `MockExportService` | `PublishingExportService` → `UnityPngExportService` + `UploadApiService` + `ExportApiService` |
| `IAIEnhancementService` | `MockAIEnhancementService` | `AIJobApiService` |
| `ISketchProcessingService` | `MockSketchPipelineService` (shared) | `SketchPipelineApiService` (shared) → `/ai/sketch/clean` |
| `IConceptPolishService` | same mock | same API → `/ai/sketch/polish` |
| `IStyleSuggestionService` | same mock | same API → `/ai/style/suggest` |
| `IImageRefinementService` | same mock | same API (maps to polish) |
| `IShareLinkService` | `MockShareLinkService` | `ShareLinkService` |

**`IGalleryService`**: `GetFeedAsync(GallerySort)`, **`GetUserPublicGalleryAsync(ownerUserId)`** → `GET /gallery/user/{id}`, `GetByIdAsync`, `LikeAsync` / `UnlikeAsync`, `GetCommentsAsync`, `PostCommentAsync`, **`PublishDesignAsync`** (`POST /gallery`).  

**`IFollowService`**: `FollowAsync` / `UnfollowAsync`, `IsFollowingAsync`, `GetFollowedUserIdsAsync` → profile follow routes.

**`IShareLinkService`**: `BuildGalleryItemUrl`, `BuildShareCardText` for copy/share actions used by Create/Gallery detail flows.

Supporting types: `ApiClient`, `ApiConfig`, `ApiResponse<T>`, `ApiException`, `TokenStorageService`, DTOs in `Infrastructure/Api/ApiDtos.cs`.

## Platform helpers (non-service)

- `NativeShareSheet`: opens iOS/Android native share chooser; falls back to clipboard where unavailable.
- `PcImportsFolderOpener`: opens `persistentDataPath/Imports` in desktop file manager.
- `PcHandoffsFolderOpener`: opens `persistentDataPath/Handoffs` in desktop file manager.

## Session

- `CreateDesignSession` is **not** a service interface; it holds authoring state. `DesignApiService` serializes enums and picks into `design_data` for the API.

## Composition

- **`AppServices.CreateDefaultMocks()`** — offline mocks (default).
- **`AppServices.CreateForApi(ApiConfig)`** — full HTTP stack.
- **`AppServices.CreateFromConfig(ApiConfig)`** — uses `ApiConfig.ShouldUseApiBackend()` (wired from **`FashionRiseApp`** in Play mode).

See **`docs/unity-backend-integration.md`** for inspector flags, auth, and production notes.
