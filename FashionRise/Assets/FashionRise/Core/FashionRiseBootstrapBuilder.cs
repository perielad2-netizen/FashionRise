using FashionRise.Presentation.Screens;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.Core
{
    /// <summary>
    /// Shared setup for editor menu and first-run Play mode (empty template scenes).
    /// </summary>
    public static class FashionRiseBootstrapBuilder
    {
        public static void EnsureEventSystem()
        {
            if (Object.FindObjectOfType<EventSystem>() != null)
                return;

            var esGo = new GameObject("EventSystem");
            esGo.AddComponent<EventSystem>();
            esGo.AddComponent<StandaloneInputModule>();
        }

        /// <summary>
        /// Builds canvas, FashionRiseApp, ScreenController, and all screen roots.
        /// </summary>
        public static GameObject CreateUiRoot()
        {
            EnsureEventSystem();

            var canvasGo = new GameObject("FashionRise_UI");
            var rtRoot = canvasGo.AddComponent<RectTransform>();
            rtRoot.anchorMin = Vector2.zero;
            rtRoot.anchorMax = Vector2.one;
            rtRoot.offsetMin = Vector2.zero;
            rtRoot.offsetMax = Vector2.zero;

            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1200, 1920);
            scaler.matchWidthOrHeight = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();

            // ScreenController before FashionRiseApp: AddComponent runs Awake immediately; Start runs after all children exist.
            canvasGo.AddComponent<ScreenController>();

            ScreenBase AddScreen<T>(string name) where T : ScreenBase
            {
                var go = new GameObject(name, typeof(RectTransform));
                go.transform.SetParent(canvasGo.transform, false);
                var rt = go.GetComponent<RectTransform>();
                rt.anchorMin = Vector2.zero;
                rt.anchorMax = Vector2.one;
                rt.offsetMin = Vector2.zero;
                rt.offsetMax = Vector2.zero;
                return go.AddComponent<T>();
            }

            AddScreen<SplashScreen>("SplashScreen");
            AddScreen<WelcomeScreen>("WelcomeScreen");
            AddScreen<LoginChoiceScreen>("LoginChoiceScreen");
            AddScreen<HomeDashboardScreen>("HomeDashboardScreen");
            AddScreen<CreateDesignScreen>("CreateDesignScreen");
            AddScreen<MaterialSelectionScreen>("MaterialSelectionScreen");
            AddScreen<ModelPreviewScreen>("ModelPreviewScreen");
            AddScreen<GalleryScreen>("GalleryScreen");
            AddScreen<ProfileScreen>("ProfileScreen");
            AddScreen<DesignDetailScreen>("DesignDetailScreen");
            AddScreen<SettingsScreen>("SettingsScreen");
            AddScreen<SketchCanvasScreen>("SketchCanvasScreen");
            AddScreen<ImportSketchScreen>("ImportSketchScreen");
            AddScreen<SketchEnhancementScreen>("SketchEnhancementScreen");
            AddScreen<ConceptResultScreen>("ConceptResultScreen");
            AddScreen<TechPackScreen>("TechPackScreen");

            canvasGo.AddComponent<FashionRiseApp>();

            return canvasGo;
        }

        /// <summary>
        /// If the loaded scene has no <see cref="FashionRiseApp"/>, creates the full UI hierarchy.
        /// </summary>
        public static void CreateBootstrapIfMissing()
        {
            if (Object.FindObjectOfType<FashionRiseApp>() != null)
                return;

            CreateUiRoot();
        }
    }
}
