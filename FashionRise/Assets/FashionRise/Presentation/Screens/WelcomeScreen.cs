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
            FrUiFactory.AddBrandLogoRow(col, t, 300f, 110f);
            FrUiFactory.AddLabel(col, "H", "WELCOME", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(col, "B",
                "Draw fashion ideas. Magic polishes them. Share your look.",
                t, Mathf.RoundToInt(t.SubtitleSize), FontStyle.Bold, TextAnchor.MiddleCenter,
                useSecondaryTextColor: true);
            FrUiFactory.AddButton(col, "LET'S GO", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.LoginChoice);
            }, FrButtonEmphasis.Primary);
        }
    }
}
