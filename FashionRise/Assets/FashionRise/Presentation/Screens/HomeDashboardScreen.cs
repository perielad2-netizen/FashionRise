using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class HomeDashboardScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.HomeDashboard;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Atelier", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "Start a new look, browse the gallery, or tune your profile.", t,
                Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);

            FrUiFactory.AddButton(col, "Create design", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.CreateDesign);
            });
            FrUiFactory.AddButton(col, "Sketch studio (V2)", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas);
            });
            FrUiFactory.AddButton(col, "Gallery", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Gallery);
            });
            FrUiFactory.AddButton(col, "Profile", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Profile);
            });
            FrUiFactory.AddButton(col, "Settings", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Settings);
            });
        }
    }
}
