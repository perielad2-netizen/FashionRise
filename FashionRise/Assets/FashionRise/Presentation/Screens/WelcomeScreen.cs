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

            FrUiFactory.AddOverline(col, "Ov", "Atelier · AI · Couture", t);
            FrUiFactory.AddBrandLogoRow(col, t, 320f, 118f);
            FrUiFactory.AddEditorialLabel(col, "H", "Design what you\nwant to wear.", t,
                Mathf.RoundToInt(t.DisplaySize), true, TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(col, "B",
                "Sketch on a fashion figure. Magic turns it into a look.\nCreate Real Design builds a production tech pack.",
                t, Mathf.RoundToInt(t.SubtitleSize), FontStyle.Normal, TextAnchor.MiddleCenter,
                useSecondaryTextColor: true);

            FrUiFactory.AddButton(col, "Enter the atelier", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.LoginChoice);
            }, FrButtonEmphasis.AiAction);
        }
    }
}
