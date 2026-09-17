using System.Collections.Generic;
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
        /// <summary>
        /// Single source of truth for the screen hierarchy. A scene saved before a screen existed
        /// is repaired at runtime from this list — otherwise navigating to the new screen would
        /// find nothing and simply hide the whole UI.
        /// </summary>
        static readonly System.Type[] ScreenTypes =
        {
            typeof(SplashScreen),
            typeof(WelcomeScreen),
            typeof(LoginChoiceScreen),
            typeof(HomeDashboardScreen),
            typeof(CreateDesignScreen),
            typeof(MaterialSelectionScreen),
            typeof(ModelPreviewScreen),
            typeof(GalleryScreen),
            typeof(ProfileScreen),
            typeof(DesignDetailScreen),
            typeof(SettingsScreen),
            typeof(SketchCanvasScreen),
            typeof(ImportSketchScreen),
            typeof(SketchEnhancementScreen),
            typeof(ConceptResultScreen),
            typeof(TechPackScreen)
        };

        public static void EnsureEventSystem()
        {
            if (Object.FindObjectOfType<EventSystem>() != null)
                return;

            var esGo = new GameObject("EventSystem");
            esGo.AddComponent<EventSystem>();
            esGo.AddComponent<StandaloneInputModule>();
        }

        /// <summary>
        /// Returns every screen under <paramref name="uiRoot"/>, creating any screen type that is
        /// missing (stale saved scene, hand-edited hierarchy). Newly created screens start hidden.
        /// </summary>
        public static ScreenBase[] EnsureScreens(Transform uiRoot)
        {
            var found = uiRoot.GetComponentsInChildren<ScreenBase>(true);
            var list = new List<ScreenBase>(found.Length + 4);
            foreach (var s in found)
                if (s != null)
                    list.Add(s);

            foreach (var type in ScreenTypes)
            {
                var present = false;
                foreach (var s in list)
                {
                    if (s.GetType() != type)
                        continue;
                    present = true;
                    break;
                }

                if (present)
                    continue;

                var screen = CreateScreen(uiRoot, type);
                if (screen == null)
                    continue;
                list.Add(screen);
                Debug.Log($"FashionRise: added missing screen '{type.Name}' to the UI hierarchy. " +
                          "Save the scene (Ctrl+S) to keep it.");
                FrDiag.Step($"repaired hierarchy: added {type.Name}");
            }

            return list.ToArray();
        }

        static ScreenBase? CreateScreen(Transform uiRoot, System.Type type)
        {
            var go = new GameObject(type.Name, typeof(RectTransform));
            go.transform.SetParent(uiRoot, false);
            var rt = go.GetComponent<RectTransform>();
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var screen = go.AddComponent(type) as ScreenBase;
            if (screen == null)
            {
                Object.Destroy(go);
                return null;
            }

            go.SetActive(false);
            return screen;
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

            EnsureScreens(canvasGo.transform);

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
