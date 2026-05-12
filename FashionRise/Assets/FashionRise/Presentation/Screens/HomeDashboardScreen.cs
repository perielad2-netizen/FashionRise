using FashionRise.Application;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class HomeDashboardScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.HomeDashboard;
        UnityEngine.UI.Text _modeLine = null!;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Atelier", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "Start a new look, browse the gallery, or tune your profile.", t,
                Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);
            _modeLine = FrUiFactory.AddLabel(col, "Mode", "", t, Mathf.RoundToInt(t.BodySize * 0.95f),
                FontStyle.Italic, TextAnchor.UpperCenter, useSecondaryTextColor: true);

            FrUiFactory.AddButton(col, "Create design", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.CreateDesign);
            }, FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(col, "Sketch studio (V2)", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas);
            });
            FrUiFactory.AddButton(col, "Gallery", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Gallery,
                        new GalleryNavContext { CommunitySort = GallerySort.Newest });
            });
            FrUiFactory.AddButton(col, "Following feed (gallery)", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Gallery,
                        new GalleryNavContext { CommunitySort = GallerySort.Following });
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

        protected override void OnShown(object? payload)
        {
            _modeLine.text = $"Authoring mode: {(AuthoringModePreferences.IsProMode ? "Pro" : "Guided")}";
        }
    }
}
