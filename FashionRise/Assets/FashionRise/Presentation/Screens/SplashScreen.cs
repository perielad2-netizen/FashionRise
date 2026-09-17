using System.Collections;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class SplashScreen : ScreenBase
    {
        bool _armed;

        public override ScreenId Id => ScreenId.Splash;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.MiddleCenter);
            FrUiFactory.AddOverline(col, "Ov", "FashionRise", t);
            FrUiFactory.AddBrandLogoRow(col, t, 360f, 132f);
            FrUiFactory.AddEditorialLabel(col, "Tag", "Choose exactly what you want.", t,
                Mathf.RoundToInt(t.TitleSize), true, TextAnchor.MiddleCenter);
        }

        protected override void OnShown(object? payload)
        {
            if (_armed)
                return;
            _armed = true;
            StartCoroutine(Advance());
        }

        IEnumerator Advance()
        {
            yield return new WaitForSeconds(1.25f);
            var task = App.Auth.TryRestorePersistedSessionAsync();
            while (!task.IsCompleted)
                yield return null;
            if (App.Navigation == null)
                yield break;
            if (App.Auth.IsSignedIn)
                _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            else
                _ = App.Navigation.NavigateToAsync(ScreenId.Welcome);
        }
    }
}
