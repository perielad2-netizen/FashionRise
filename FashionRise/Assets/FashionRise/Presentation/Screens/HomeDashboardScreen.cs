using FashionRise.Application;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Front door — pick a fashion figure, then sketch. Magic. Tech pack.</summary>
    public sealed class HomeDashboardScreen : ScreenBase
    {
        Text _moreHint = null!;
        bool _moreOpen;

        public override ScreenId Id => ScreenId.HomeDashboard;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);

            FrUiFactory.AddOverline(col, "Ov", "Fashion atelier", t);
            FrUiFactory.AddBrandLogoRow(col, t, 280f, 96f);
            FrUiFactory.AddEditorialLabel(col, "H", "Choose your model", t,
                Mathf.RoundToInt(t.DisplaySize * 0.72f), true, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "Sketch. Magic. Create Real Design.", t,
                Mathf.RoundToInt(t.SubtitleSize), FontStyle.Normal, TextAnchor.UpperCenter,
                useSecondaryTextColor: true);

            var row = FrUiFactory.AddHorizontalRow(col, "ModelRow", t.ControlGap);
            FrUiFactory.AddModelChoiceTile(row, "Women", "WOMEN", SketchDefaultFigureGenerator.FemaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Female));
            FrUiFactory.AddModelChoiceTile(row, "Men", "MEN", SketchDefaultFigureGenerator.MaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Male));

            FrUiFactory.AddButton(col, "More studio…", t, ToggleMore, FrButtonEmphasis.Ghost);
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

        protected override void OnShown(object? payload) => SetMoreVisible(_moreOpen);

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

        void SetMoreVisible(bool visible)
        {
            _moreHint.text = visible
                ? "Gallery · Atelier · Profile · Settings"
                : "";
            SetBtn("Gallery", visible);
            SetBtn("Atelier (pro create)", visible);
            SetBtn("Profile", visible);
            SetBtn("Settings", visible);
        }

        void SetBtn(string label, bool on)
        {
            var tr = transform.Find($"Root/Col/{label}_Btn");
            if (tr != null)
                tr.gameObject.SetActive(on);
        }
    }
}
