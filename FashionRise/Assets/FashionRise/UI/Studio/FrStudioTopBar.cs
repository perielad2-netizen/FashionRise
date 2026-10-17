using FashionRise.Application;
using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioTopBar
    {
        public RectTransform Root { get; }
        public Graphic ContextLabel { get; }
        public Graphic AutosaveLabel { get; }

        FrStudioTopBar(RectTransform root, Graphic context, Graphic autosave)
        {
            Root = root;
            ContextLabel = context;
            AutosaveLabel = autosave;
        }

        public static FrStudioTopBar Build(Transform parent, FashionRiseTheme theme, UnityAction onBack,
            UnityAction onImport, UnityAction onProfile)
        {
            var go = new GameObject("StudioTopBar", typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var face = go.GetComponent<Image>();
            face.color = theme.ShellPanel;
            face.raycastTarget = true;

            var row = new GameObject("Row", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            var rowRt = row.GetComponent<RectTransform>();
            rowRt.SetParent(rt, false);
            rowRt.anchorMin = Vector2.zero;
            rowRt.anchorMax = Vector2.one;
            rowRt.offsetMin = new Vector2(theme.SpaceMd, 8f);
            rowRt.offsetMax = new Vector2(-theme.SpaceMd, -8f);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = theme.SpaceSm;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            h.childForceExpandHeight = false;

            FrStudioIconButton.Build(row.transform, theme, FrStudioIconKind.Back, "", onBack);

            AddLogo(row.transform, theme);

            var brandHost = new GameObject("Brand", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(LayoutElement));
            brandHost.transform.SetParent(row.transform, false);
            brandHost.GetComponent<LayoutElement>().preferredWidth = DeviceLayoutPolicy.IsTabletLike() ? 220f : 168f;
            var bv = brandHost.GetComponent<VerticalLayoutGroup>();
            bv.spacing = 0f;
            bv.childAlignment = TextAnchor.MiddleLeft;
            bv.childControlHeight = true;
            bv.childControlWidth = true;
            bv.childForceExpandHeight = false;
            var wordHost = new GameObject("Word", typeof(RectTransform), typeof(LayoutElement));
            wordHost.transform.SetParent(brandHost.transform, false);
            wordHost.GetComponent<LayoutElement>().minHeight = 24f;
            FrStudioTypography.AddLabel(wordHost.transform, "Wordmark", "FashionRise", theme,
                FrStudioTypeStyle.PageTitle, muted: false, TextAnchor.MiddleLeft);
            var ctxHost = new GameObject("Ctx", typeof(RectTransform), typeof(LayoutElement));
            ctxHost.transform.SetParent(brandHost.transform, false);
            ctxHost.GetComponent<LayoutElement>().minHeight = 18f;
            var context = FrStudioTypography.AddLabel(ctxHost.transform, "Context", "Creator Studio", theme,
                FrStudioTypeStyle.Metadata, muted: true, TextAnchor.MiddleLeft);

            var spacer = new GameObject("Flex", typeof(RectTransform), typeof(LayoutElement));
            spacer.transform.SetParent(row.transform, false);
            spacer.GetComponent<LayoutElement>().flexibleWidth = 1f;

            var saveHost = new GameObject("SaveHost", typeof(RectTransform), typeof(LayoutElement));
            saveHost.transform.SetParent(row.transform, false);
            saveHost.GetComponent<LayoutElement>().preferredWidth = 150f;
            saveHost.GetComponent<LayoutElement>().minHeight = 20f;
            var autosave = FrStudioTypography.AddLabel(saveHost.transform, "Autosave", AutosaveCopy(), theme,
                FrStudioTypeStyle.Metadata, muted: true, TextAnchor.MiddleRight);

            FrStudioIconButton.Build(row.transform, theme, FrStudioIconKind.Import, "", onImport);
            FrStudioIconButton.Build(row.transform, theme, FrStudioIconKind.Profile, "", onProfile);

            return new FrStudioTopBar(rt, context, autosave);
        }

        public void RefreshAutosave() => FrStudioTypography.SetText(AutosaveLabel, AutosaveCopy());

        static string AutosaveCopy() =>
            DesignAutosavePreferences.IsEnabled
                ? $"Autosave on · {DesignAutosavePreferences.GetIntervalSeconds()}s"
                : "Autosave off";

        static void AddLogo(Transform parent, FashionRiseTheme theme)
        {
            var sprite = Resources.Load<Sprite>("Branding/fashion_rise_logo");
            var tex = sprite == null ? Resources.Load<Texture2D>("Branding/fashion_rise_logo") : null;
            var go = new GameObject("Logo", typeof(RectTransform), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var le = go.GetComponent<LayoutElement>();
            le.preferredWidth = 44f;
            le.preferredHeight = 44f;
            le.minWidth = 40f;
            le.minHeight = 40f;
            if (sprite != null)
            {
                var img = go.AddComponent<Image>();
                img.sprite = sprite;
                img.preserveAspect = true;
                img.raycastTarget = false;
            }
            else if (tex != null)
            {
                var raw = go.AddComponent<RawImage>();
                raw.texture = tex;
                raw.raycastTarget = false;
            }
            else
            {
                var img = go.AddComponent<Image>();
                img.sprite = FrStudioSprites.Rounded(48, 12, Color.white);
                img.color = theme.AccentMuted;
                img.raycastTarget = false;
            }
        }
    }
}
