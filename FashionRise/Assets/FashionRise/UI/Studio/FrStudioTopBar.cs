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

            var underline = new GameObject("Underline", typeof(RectTransform), typeof(Image));
            var underRt = underline.GetComponent<RectTransform>();
            underRt.SetParent(rt, false);
            underRt.anchorMin = new Vector2(0f, 0f);
            underRt.anchorMax = new Vector2(1f, 0f);
            underRt.pivot = new Vector2(0.5f, 0f);
            underRt.sizeDelta = new Vector2(0f, 1f);
            underRt.anchoredPosition = Vector2.zero;
            underline.GetComponent<Image>().color = new Color(theme.AccentMuted.r, theme.AccentMuted.g,
                theme.AccentMuted.b, 0.35f);
            underline.GetComponent<Image>().raycastTarget = false;

            var row = new GameObject("Row", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            var rowRt = row.GetComponent<RectTransform>();
            rowRt.SetParent(rt, false);
            rowRt.anchorMin = Vector2.zero;
            rowRt.anchorMax = Vector2.one;
            rowRt.offsetMin = new Vector2(theme.SpaceMd, 10f);
            rowRt.offsetMax = new Vector2(-theme.SpaceMd, -10f);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = theme.SpaceMd;
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
            brandHost.GetComponent<LayoutElement>().preferredWidth = DeviceLayoutPolicy.IsTabletLike() ? 280f : 210f;
            brandHost.GetComponent<LayoutElement>().flexibleWidth = 0f;
            var bv = brandHost.GetComponent<VerticalLayoutGroup>();
            bv.spacing = 2f;
            bv.childAlignment = TextAnchor.MiddleLeft;
            bv.childControlHeight = true;
            bv.childControlWidth = true;
            bv.childForceExpandHeight = false;

            var wordHost = new GameObject("Word", typeof(RectTransform), typeof(LayoutElement));
            wordHost.transform.SetParent(brandHost.transform, false);
            wordHost.GetComponent<LayoutElement>().minHeight = 30f;
            wordHost.GetComponent<LayoutElement>().preferredHeight = 30f;
            FrStudioTypography.AddLabel(wordHost.transform, "Wordmark", "FashionRise", theme,
                FrStudioTypeStyle.Display, muted: false, TextAnchor.MiddleLeft);

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
            saveHost.GetComponent<LayoutElement>().preferredWidth = 168f;
            saveHost.GetComponent<LayoutElement>().minHeight = 22f;
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
            var size = DeviceLayoutPolicy.IsTabletLike() ? 58f : 50f;
            le.preferredWidth = size;
            le.preferredHeight = size;
            le.minWidth = size;
            le.minHeight = size;
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
                img.sprite = FrStudioSprites.Rounded(64, 14, Color.white);
                img.color = theme.AccentMuted;
                img.raycastTarget = false;
            }
        }
    }
}
