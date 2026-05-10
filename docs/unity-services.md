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
| `IRatingService` | `MockRatingService` | `RatingApiService` |
| `IExportService` | `MockExportService` | `PublishingExportService` → `UnityPngExportService` + `UploadApiService` + `ExportApiService` |
| `IAIEnhancementService` | `MockAIEnhancementService` | `AIJobApiService` |
| `ISketchProcessingService` | `MockSketchPipelineService` (shared) | `SketchPipelineApiService` (shared) → `/ai/sketch/clean` |
| `IConceptPolishService` | same mock | same API → `/ai/sketch/polish` |
| `IStyleSuggestionService` | same mock | same API → `/ai/style/suggest` |
| `IImageRefinementService` | same mock | same API (maps to polish) |

**`IGalleryService`** (V2): `GetFeedAsync(GallerySort)`, `LikeAsync` / `UnlikeAsync`, `GetCommentsAsync`, `PostCommentAsync` (mock + `GalleryApiService`).

Supporting types: `ApiClient`, `ApiConfig`, `ApiResponse<T>`, `ApiException`, `TokenStorageService`, DTOs in `Infrastructure/Api/ApiDtos.cs`.

## Session

- `CreateDesignSession` is **not** a service interface; it holds authoring state. `DesignApiService` serializes enums and picks into `design_data` for the API.

## Composition

- **`AppServices.CreateDefaultMocks()`** — offline mocks (default).
- **`AppServices.CreateForApi(ApiConfig)`** — full HTTP stack.
- **`AppServices.CreateFromConfig(ApiConfig)`** — uses `ApiConfig.ShouldUseApiBackend()` (wired from **`FashionRiseApp`** in Play mode).

See **`docs/unity-backend-integration.md`** for inspector flags, auth, and production notes.
