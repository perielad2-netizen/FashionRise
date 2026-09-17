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
        public string ApiBaseUrl { get; }
        public IAuthService Auth { get; }
        public IUserProfileService UserProfile { get; }
        public IDesignSaveService DesignSave { get; }
        public IDesignHandoffService Handoff { get; }
        public IMaterialCatalogService Materials { get; }
        public IColorPaletteService Palettes { get; }
        public IGarmentTemplateService Templates { get; }
        public IGalleryService Gallery { get; }
        public IFollowService Follow { get; }
        public IRatingService Ratings { get; }
        public IExportService Export { get; }
        public IAIEnhancementService Ai { get; }
        public ISketchProcessingService SketchClean { get; }
        public IConceptPolishService ConceptPolish { get; }
        public IStyleSuggestionService StyleSuggest { get; }
        public IImageRefinementService ImageRefine { get; }
        public ITechPackService TechPack { get; }
        public IShareLinkService ShareLinks { get; }
        public CreateDesignSession CreateDesign { get; }
        public INavigationService? Navigation { get; private set; }

        public AppServices(
            bool isApiBackend,
            IAuthService auth,
            IUserProfileService userProfile,
            IDesignSaveService designSave,
            IDesignHandoffService handoff,
            IMaterialCatalogService materials,
            IColorPaletteService palettes,
            IGarmentTemplateService templates,
            IGalleryService gallery,
            IFollowService follow,
            IRatingService ratings,
            IExportService export,
            IAIEnhancementService ai,
            ISketchProcessingService sketchClean,
            IConceptPolishService conceptPolish,
            IStyleSuggestionService styleSuggest,
            IImageRefinementService imageRefine,
            ITechPackService techPack,
            IShareLinkService shareLinks,
            CreateDesignSession createDesign,
            string apiBaseUrl = "")
        {
            IsApiBackend = isApiBackend;
            ApiBaseUrl = apiBaseUrl ?? "";
            Auth = auth;
            UserProfile = userProfile;
            DesignSave = designSave;
            Handoff = handoff;
            Materials = materials;
            Palettes = palettes;
            Templates = templates;
            Gallery = gallery;
            Follow = follow;
            Ratings = ratings;
            Export = export;
            Ai = ai;
            SketchClean = sketchClean;
            ConceptPolish = conceptPolish;
            StyleSuggest = styleSuggest;
            ImageRefine = imageRefine;
            TechPack = techPack;
            ShareLinks = shareLinks;
            CreateDesign = createDesign;
        }

        public void BindNavigation(INavigationService navigation) => Navigation = navigation;

        public static AppServices CreateDefaultMocks()
        {
            var auth = new MockAuthService();
            var follow = new MockFollowService(auth);
            var gallery = new MockGalleryService(auth, follow);
            var sketch = new MockSketchPipelineService();
            var designSave = new MockDesignSaveService();
            var handoff = new MockDesignHandoffService(designSave);
            return new AppServices(
                false,
                auth,
                new MockUserProfileService(auth),
                designSave,
                handoff,
                new MockMaterialCatalogService(),
                new MockColorPaletteService(),
                new MockGarmentTemplateService(),
                gallery,
                follow,
                new MockRatingService(gallery),
                new MockExportService(),
                new MockAIEnhancementService(),
                sketch,
                sketch,
                sketch,
                sketch,
                sketch,
                new MockShareLinkService(),
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
            var handoff = new DesignHandoffApiService(client);
            var materials = new MaterialApiService(client);
            var templates = new TemplateApiService(client);
            var palettes = new PaletteApiService(client);
            var gallery = new GalleryApiService(client);
            var follow = new FollowApiService(client);
            var ratings = new RatingApiService(client);
            var uploads = new UploadApiService(client);
            var exports = new ExportApiService(client);
            var ai = new AIJobApiService(client);
            var sketchApi = new SketchPipelineApiService(client);
            var sketch = new TokenAwareSketchPipelineService(auth, sketchApi);
            var innerCapture = new UnityPngExportService();
            var export = new PublishingExportService(innerCapture, uploads, exports, auth);
            var shareLinks = new ShareLinkService(config);
            return new AppServices(
                true,
                auth,
                profiles,
                designs,
                handoff,
                materials,
                palettes,
                templates,
                gallery,
                follow,
                ratings,
                export,
                ai,
                sketch,
                sketch,
                sketch,
                sketch,
                sketch,
                shareLinks,
                new CreateDesignSession(),
                config.BaseUrl ?? "");
        }

        /// <summary>Build from inspector flags on <see cref="ApiConfig"/>.</summary>
        public static AppServices CreateFromConfig(ApiConfig config)
        {
            if (config.ShouldUseApiBackend())
            {
                if (string.IsNullOrWhiteSpace(config.BaseUrl))
                    Debug.LogError(
                        "FashionRise: ApiConfig.BaseUrl is empty. Set it on FashionRiseApp (e.g. http://127.0.0.1:8001/api/v1) or use menu FashionRise → Use Local API.");
                return CreateForApi(config);
            }

            return CreateDefaultMocks();
        }
    }
}
