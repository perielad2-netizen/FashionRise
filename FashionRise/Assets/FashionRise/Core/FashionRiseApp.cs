using FashionRise.Core.Navigation;
using FashionRise.Infrastructure.Api;
using FashionRise.Infrastructure.Platform;
using FashionRise.Presentation;
using FashionRise.Presentation.Navigation;
using FashionRise.Presentation.Screens;
using UnityEngine;

namespace FashionRise.Core
{
    /// <summary>
    /// Scene entry: wires API services by default (FastAPI); toggle Api Config for mocks.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public sealed class FashionRiseApp : MonoBehaviour
    {
        [SerializeField] ScreenController? screenController;
        [SerializeField] ApiConfig apiConfig = new();

        NavigationService _nav = null!;

        void Awake()
        {
            FrDiag.Install();
#if (UNITY_ANDROID || UNITY_IOS) && !UNITY_EDITOR
            if (FindObjectOfType<FashionRiseAndroidBridge>() == null)
            {
                var go = new GameObject(FashionRiseAndroidBridge.GameObjectName);
                go.AddComponent<FashionRiseAndroidBridge>();
            }
#endif
        }

        void Start()
        {
            var sc = screenController != null ? screenController : GetComponent<ScreenController>();
            if (sc == null)
            {
                Debug.LogError("FashionRiseApp requires a ScreenController on this object or via assign field.");
                return;
            }

            FashionRiseBootstrapBuilder.EnsureAllScreens(sc.transform);

            var app = AppServices.CreateFromConfig(apiConfig);
            Debug.Log($"FashionRise API BaseUrl = '{apiConfig.BaseUrl}' (api={app.IsApiBackend})");
            sc.Initialize(app);
            _nav = new NavigationService(sc);
            app.BindNavigation(_nav);
            var autosave = GetComponent<DesignAutosaveDriver>();
            if (autosave == null)
                autosave = gameObject.AddComponent<DesignAutosaveDriver>();
            autosave.Init(app);
            FrDiag.Fire(_nav.NavigateToAsync(ScreenId.Splash), "navigate Splash");
        }
    }
}
