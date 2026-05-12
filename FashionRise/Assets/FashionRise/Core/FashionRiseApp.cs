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

            var app = AppServices.CreateFromConfig(apiConfig);
            sc.Initialize(app);
            _nav = new NavigationService(sc);
            app.BindNavigation(_nav);
            var autosave = GetComponent<DesignAutosaveDriver>();
            if (autosave == null)
                autosave = gameObject.AddComponent<DesignAutosaveDriver>();
            autosave.Init(app);
            _ = _nav.NavigateToAsync(ScreenId.Splash);
        }
    }
}
