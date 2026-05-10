using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class WelcomeScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.Welcome;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(col, "H", "Welcome", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(col, "B",
                "Design realistic garments, refine fabrics, and preview in a studio setting — built for tablets, ready for what is next.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.MiddleCenter);
            FrUiFactory.AddButton(col, "Continue", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.LoginChoice);
            });
        }
    }
}
