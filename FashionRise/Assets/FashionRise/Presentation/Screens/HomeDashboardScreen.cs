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
    /// Premium atelier home — brand + two full-height model stages. Secondary studio links stay quiet.
    /// </summary>
    public sealed class HomeDashboardScreen : ScreenBase
    {
        RectTransform _morePanel = null!;

        public override ScreenId Id => ScreenId.HomeDashboard;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);

            // Top brand bar
            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 118f);
            var topV = top.GetComponent<VerticalLayoutGroup>();
            topV.padding = new RectOffset(28, 28, 18, 4);
            topV.spacing = 2f;
            topV.childAlignment = TextAnchor.UpperCenter;
            topV.childControlWidth = true;
            topV.childForceExpandWidth = true;
            topV.childControlHeight = true;
            topV.childForceExpandHeight = false;
            FrUiFactory.AddOverline(top.transform, "Ov", "FashionRise atelier", t);
            FrUiFactory.AddBrandLogoRow(top.transform, t, 220f, 56f);

            // Bottom quiet actions — not a button farm in the hero
            const float bottomH = 88f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var bottomRt = bottom.GetComponent<RectTransform>();
            bottomRt.SetParent(root, false);
            bottomRt.anchorMin = new Vector2(0f, 0f);
            bottomRt.anchorMax = new Vector2(1f, 0f);
            bottomRt.pivot = new Vector2(0.5f, 0f);
            bottomRt.sizeDelta = new Vector2(0f, bottomH);
            var bottomV = bottom.GetComponent<VerticalLayoutGroup>();
            bottomV.padding = new RectOffset(24, 24, 4, 16);
            bottomV.spacing = 4f;
            bottomV.childAlignment = TextAnchor.LowerCenter;
            bottomV.childControlWidth = true;
            bottomV.childForceExpandWidth = true;

            // Icon tab bar — no stacked text buttons.
            _morePanel = new GameObject("NavBar", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement)).GetComponent<RectTransform>();
            _morePanel.SetParent(bottom.transform, false);
            var moreLe = _morePanel.GetComponent<LayoutElement>();
            moreLe.minHeight = 56f;
            moreLe.preferredHeight = 56f;
            var moreH = _morePanel.GetComponent<HorizontalLayoutGroup>();
            moreH.spacing = 26f;
            moreH.childAlignment = TextAnchor.MiddleCenter;
            moreH.childForceExpandWidth = false;
            moreH.childControlWidth = true;
            moreH.childControlHeight = true;

            FrUiFactory.AddIconButton(_morePanel, "Gallery", FrUiSprites.IconGallery, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Gallery,
                        new GalleryNavContext { CommunitySort = GallerySort.Newest });
            }, 50f);
            FrUiFactory.AddIconButton(_morePanel, "Atelier", FrUiSprites.IconAtelier, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.CreateDesign);
            }, 50f);
            FrUiFactory.AddIconButton(_morePanel, "Profile", FrUiSprites.IconProfile, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Profile);
            }, 50f);
            FrUiFactory.AddIconButton(_morePanel, "Settings", FrUiSprites.IconSettings, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.Settings);
            }, 50f);

            foreach (var img in _morePanel.GetComponentsInChildren<Image>())
                if (img.sprite == FrUiSprites.Circle)
                    img.color = new Color(1f, 1f, 1f, 0f);

            // Hero stage — two tall model columns fill the viewport
            var hero = new GameObject("Hero", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var heroRt = hero.GetComponent<RectTransform>();
            heroRt.SetParent(root, false);
            heroRt.anchorMin = Vector2.zero;
            heroRt.anchorMax = Vector2.one;
            heroRt.offsetMin = new Vector2(20f, bottomH + 4f);
            heroRt.offsetMax = new Vector2(-20f, -122f);
            var heroV = hero.GetComponent<VerticalLayoutGroup>();
            heroV.spacing = 14f;
            heroV.childAlignment = TextAnchor.UpperCenter;
            heroV.childControlWidth = true;
            heroV.childForceExpandWidth = true;
            heroV.childControlHeight = true;
            heroV.childForceExpandHeight = false;

            FrUiFactory.AddEditorialLabel(hero.transform, "H", "Choose your model", t,
                Mathf.RoundToInt(t.TitleSize), true, TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(hero.transform, "B", "Tap a figure to open the sketch studio.", t,
                Mathf.RoundToInt(t.SubtitleSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);

            var row = new GameObject("ModelRow", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(hero.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.flexibleHeight = 1f;
            rowLe.minHeight = 420f;
            rowLe.preferredHeight = 560f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 16f;
            rowH.childAlignment = TextAnchor.MiddleCenter;
            rowH.childControlWidth = true;
            rowH.childForceExpandWidth = true;
            rowH.childControlHeight = true;
            rowH.childForceExpandHeight = true;

            FrUiFactory.AddModelChoiceTile(row.transform, "Women", "Women",
                SketchDefaultFigureGenerator.FemaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Female), tall: true);
            FrUiFactory.AddModelChoiceTile(row.transform, "Men", "Men",
                SketchDefaultFigureGenerator.MaleResourcePath, t,
                () => OpenSketch(SketchFigureTemplate.Male), tall: true);
        }

        void OpenSketch(SketchFigureTemplate figure)
        {
            SketchFigurePreferences.DefaultTemplate = figure;
            if (App.Navigation == null)
                return;
            _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas, new SketchNavContext { Figure = figure });
        }
    }
}
