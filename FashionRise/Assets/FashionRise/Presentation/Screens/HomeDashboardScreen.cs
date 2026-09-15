using FashionRise.Application;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Kid front door: Girl / Boy → sketch → magic → share.
    /// Pro atelier (create, gallery social, settings) stays under More.
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

            FrUiFactory.AddBrandLogoRow(col, t, 280f, 96f);
            FrUiFactory.AddLabel(col, "H", "Draw. Magic. Share.", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Pick a model, draw your idea, tap Magic — then share your look.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);

            var girl = FrUiFactory.AddButton(col, "Girl model", t, () => OpenSketch(SketchFigureTemplate.Female),
                FrButtonEmphasis.Primary);
            EnlargePrimary(girl);
            var boy = FrUiFactory.AddButton(col, "Boy model", t, () => OpenSketch(SketchFigureTemplate.Male),
                FrButtonEmphasis.Primary);
            EnlargePrimary(boy);

            FrUiFactory.AddButton(col, "More…", t, ToggleMore);
            _moreHint = FrUiFactory.AddLabel(col, "MorePanel", "", t, Mathf.RoundToInt(t.BodySize * 0.95f),
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
                ? "Studio tools for growing talent — gallery, atelier, profile."
                : " ";

            // Gallery / Atelier / Profile / Settings are the last four buttons under More…
            // They stay in hierarchy; we only toggle interactable + alpha via sibling names.
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

        static void EnlargePrimary(Button btn)
        {
            var le = btn.GetComponent<LayoutElement>();
            if (le == null)
                return;
            le.minHeight = 72f;
            le.preferredHeight = 72f;
            var txt = btn.GetComponentInChildren<Text>();
            if (txt != null)
                txt.fontSize = Mathf.Max(txt.fontSize, 22);
        }
    }
}
