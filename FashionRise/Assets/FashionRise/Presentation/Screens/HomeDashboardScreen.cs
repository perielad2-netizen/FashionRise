using FashionRise.Application;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Front door — pick a fashion figure, then sketch. Magic. Share.
    /// </summary>
    public sealed class HomeDashboardScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.HomeDashboard;

        Text _moreHint = null!;
        bool _moreOpen;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);

            // Brand is the hero signal on this screen.
            FrUiFactory.AddBrandLogoRow(col, t, 300f, 108f);
            FrUiFactory.AddLabel(col, "H", "CHOOSE YOUR MODEL", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "Then draw. Magic. Share.", t, Mathf.RoundToInt(t.SubtitleSize),
                FontStyle.Bold, TextAnchor.UpperCenter, useSecondaryTextColor: true);

            var row = FrUiFactory.AddHorizontalRow(col, "ModelRow", t.ControlGap);
            FrUiFactory.AddModelChoiceTile(row, "Women", "WOMEN", SketchDefaultFigureGenerator.FemaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Female));
            FrUiFactory.AddModelChoiceTile(row, "Men", "MEN", SketchDefaultFigureGenerator.MaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Male));

            FrUiFactory.AddButton(col, "More studio…", t, ToggleMore);
            _moreHint = FrUiFactory.AddLabel(col, "MorePanel", "", t, Mathf.RoundToInt(t.CaptionSize),
                FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);

            FrUiFactory.AddButton(col, "Gallery", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Gallery,
                        new GalleryNavContext { CommunitySort = GallerySort.Newest });
            });
            FrUiFactory.AddButton(col, "Atelier (pro create)", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.CreateDesign);
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

            SetMoreVisible(false);
        }

        protected override void OnShown(object? payload)
        {
            SetMoreVisible(_moreOpen);
        }

        void OpenSketch(SketchFigureTemplate figure)
        {
            SketchFigurePreferences.DefaultTemplate = figure;
            if (App.Navigation == null)
                return;
            _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas, new SketchNavContext { Figure = figure });
        }

        void ToggleMore()
        {
            _moreOpen = !_moreOpen;
            SetMoreVisible(_moreOpen);
        }

        void SetMoreVisible(bool open)
        {
            _moreHint.text = open
                ? "Gallery, atelier, profile — when you want more."
                : " ";

            var col = transform.Find("Root/Col");
            if (col == null)
                return;
            SetSiblingActive(col, "Gallery_Btn", open);
            SetSiblingActive(col, "Atelier (pro create)_Btn", open);
            SetSiblingActive(col, "Profile_Btn", open);
            SetSiblingActive(col, "Settings_Btn", open);
        }

        static void SetSiblingActive(Transform col, string name, bool active)
        {
            var child = col.Find(name);
            if (child != null)
                child.gameObject.SetActive(active);
        }
    }
}
