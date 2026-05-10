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
            FrUiFactory.AddLabel(col, "Brand", "FashionRise", t, Mathf.RoundToInt(t.TitleSize + 8), FontStyle.Bold,
                TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(col, "Tag", "Premium fashion creation", t, Mathf.RoundToInt(t.SubtitleSize),
                FontStyle.Italic, TextAnchor.MiddleCenter);
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
            yield return new WaitForSeconds(1.15f);
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.Welcome);
        }
    }
}
