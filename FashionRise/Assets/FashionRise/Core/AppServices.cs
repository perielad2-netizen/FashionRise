using FashionRise.Application;
using FashionRise.Infrastructure.Api;
using FashionRise.Infrastructure.Export;
using FashionRise.Infrastructure.Mocks;
using FashionRise.Services;
using UnityEngine;

namespace FashionRise.Core
{
    /// <summary>
    /// Composition root for service instances (mock or API).
    /// </summary>
    public sealed class AppServices
    {
        public bool IsApiBackend { get; }
        public IAuthService Auth { get; }
        public IUserProfileService UserProfile { get; }
        public IDesignSaveService DesignSave { get; }
        public IMaterialCatalogService Materials { get; }
        public IColorPaletteService Palettes { get; }
        public IGarmentTemplateService Templates { get; }
        public IGalleryService Gallery { get; }
        public IRatingService Ratings { get; }
        public IExportService Export { get; }
        public IAIEnhancementService Ai { get; }
        public ISketchProcessingService SketchClean { get; }
        public IConceptPolishService ConceptPolish { get; }
        public IStyleSuggestionService StyleSuggest { get; }
        public IImageRefinementService ImageRefine { get; }
        public CreateDesignSession CreateDesign { get; }
        public INavigationService? Navigation { get; private set; }

        public AppServices(
            bool isApiBackend,
            IAuthService auth,
            IUserProfileService userProfile,
            IDesignSaveService designSave,
            IMaterialCatalogService materials,
            IColorPaletteService palettes,
            IGarmentTemplateService templates,
            IGalleryService gallery,
            IRatingService ratings,
            IExportService export,
            IAIEnhancementService ai,
            ISketchProcessingService sketchClean,
            IConceptPolishService conceptPolish,
            IStyleSuggestionService styleSuggest,
            IImageRefinementService imageRefine,
            CreateDesignSession createDesign)
        {
            IsApiBackend = isApiBackend;
            Auth = auth;
            UserProfile = userProfile;
            DesignSave = designSave;
            Materials = materials;
            Palettes = palettes;
            Templates = templates;
            Gallery = gallery;
            Ratings = ratings;
            Export = export;
            Ai = ai;
            SketchClean = sketchClean;
            ConceptPolish = conceptPolish;
            StyleSuggest = styleSuggest;
            ImageRefine = imageRefine;
            CreateDesign = createDesign;
        }

        public void BindNavigation(INavigationService navigation) => Navigation = navigation;

        public static AppServices CreateDefaultMocks()
        {
            var auth = new MockAuthService();
            var gallery = new MockGalleryService(auth);
            var sketch = new MockSketchPipelineService();
            return new AppServices(
                false,
                auth,
                new MockUserProfileService(auth),
                new MockDesignSaveService(),
                new MockMaterialCatalogService(),
                new MockColorPaletteService(),
                new MockGarmentTemplateService(),
                gallery,
                new MockRatingService(gallery),
                new MockExportService(),
                new MockAIEnhancementService(),
                sketch,
                sketch,
                sketch,
                sketch,
                new CreateDesignSession());
        }

        /// <summary>Wires FastAPI-backed services. <paramref name="config"/> must stay alive for <see cref="ApiClient"/>.</summary>
        public static AppServices CreateForApi(ApiConfig config)
        {
            var tokens = new TokenStorageService();
            var client = new ApiClient(config, tokens);
            var auth = new AuthApiService(client, tokens);
            var profiles = new UserProfileApiService(client);
            var designs = new DesignApiService(client);
            var materials = new MaterialApiService(client);
            var templates = new TemplateApiService(client);
            var palettes = new PaletteApiService(client);
            var gallery = new GalleryApiService(client);
            var ratings = new RatingApiService(client);
            var uploads = new UploadApiService(client);
            var exports = new ExportApiService(client);
            var ai = new AIJobApiService(client);
            var sketchApi = new SketchPipelineApiService(client);
            var sketch = new GuestAwareSketchPipelineService(auth, sketchApi);
            var innerCapture = new UnityPngExportService();
            var export = new PublishingExportService(innerCapture, uploads, exports, auth);
            return new AppServices(
                true,
                auth,
                profiles,
                designs,
                materials,
                palettes,
                templates,
                gallery,
                ratings,
                export,
                ai,
                sketch,
                sketch,
                sketch,
                sketch,
                new CreateDesignSession());
        }

        /// <summary>Build from inspector flags on <see cref="ApiConfig"/>.</summary>
        public static AppServices CreateFromConfig(ApiConfig config)
        {
            if (config.ShouldUseApiBackend())
            {
                if (string.IsNullOrWhiteSpace(config.BaseUrl))
                    Debug.LogError(
                        "FashionRise: ApiConfig.BaseUrl is empty. Set it on FashionRiseApp (e.g. http://127.0.0.1:8000/api/v1) or use menu FashionRise → Use Local API.");
                return CreateForApi(config);
            }

            return CreateDefaultMocks();
        }
    }
}
