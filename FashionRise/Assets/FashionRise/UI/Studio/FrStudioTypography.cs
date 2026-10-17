using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.UI;
#if FASHIONRISE_TMP
using TMPro;
#endif

namespace FashionRise.UI.Studio
{
    public enum FrStudioTypeStyle
    {
        Display,
        PageTitle,
        SectionHeading,
        Body,
        Button,
        Caption,
        Metadata
    }

    public enum FrStudioTypeTone
    {
        OnDark,
        OnLight
    }

    /// <summary>
    /// TMP-first Studio type. Assign <see cref="ConfiguredFont"/> or drop a TMP font under
    /// Resources. Falls back to Unity UI Text when no usable TMP font asset exists.
    /// Does not read <c>TMP_Settings.defaultFontAsset</c>: that getter throws when TMP Settings
    /// is absent (TMP 3.0.7 returns <c>instance.m_defaultFontAsset</c> with a null instance).
    /// </summary>
    public static class FrStudioTypography
    {
        public static object? ConfiguredFont;

        static Font? s_legacy;

        static Font LegacyFont =>
            s_legacy != null
                ? s_legacy
                : (s_legacy = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf")!);

        public static Graphic AddLabel(Transform parent, string name, string text, FashionRiseTheme theme,
            FrStudioTypeStyle style, bool muted = false, TextAnchor anchor = TextAnchor.MiddleLeft,
            FrStudioTypeTone tone = FrStudioTypeTone.OnDark)
        {
            var size = ResolveSize(theme, style);
            var color = ResolveColor(theme, style, muted, tone);
            var bold = style is FrStudioTypeStyle.Display or FrStudioTypeStyle.PageTitle
                or FrStudioTypeStyle.SectionHeading or FrStudioTypeStyle.Button;

#if FASHIONRISE_TMP
            var tmpFont = ResolveTmpFont();
            if (tmpFont != null)
            {
                var go = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI));
                go.transform.SetParent(parent, false);
                var tmp = go.GetComponent<TextMeshProUGUI>();
                tmp.font = tmpFont;
                tmp.text = text;
                tmp.fontSize = size;
                tmp.fontStyle = bold ? FontStyles.Bold : FontStyles.Normal;
                tmp.color = color;
                tmp.alignment = ToTmpAlignment(anchor);
                tmp.enableWordWrapping = style != FrStudioTypeStyle.Button;
                tmp.overflowMode = TextOverflowModes.Overflow;
                tmp.raycastTarget = false;
                tmp.richText = false;
                Stretch(go.GetComponent<RectTransform>());
                return tmp;
            }
#endif

            var legacyGo = new GameObject(name, typeof(RectTransform), typeof(Text));
            legacyGo.transform.SetParent(parent, false);
            var label = legacyGo.GetComponent<Text>();
            label.font = LegacyFont;
            label.text = text;
            label.fontSize = Mathf.RoundToInt(size);
            label.fontStyle = bold ? FontStyle.Bold : FontStyle.Normal;
            label.color = color;
            label.alignment = anchor;
            label.horizontalOverflow = HorizontalWrapMode.Wrap;
            label.verticalOverflow = VerticalWrapMode.Overflow;
            label.raycastTarget = false;
            Stretch(legacyGo.GetComponent<RectTransform>());
            return label;
        }

        public static void SetText(Graphic graphic, string text)
        {
#if FASHIONRISE_TMP
            if (graphic is TextMeshProUGUI tmp)
            {
                tmp.text = text;
                return;
            }
#endif
            if (graphic is Text ui)
                ui.text = text;
        }

        public static string GetText(Graphic graphic)
        {
#if FASHIONRISE_TMP
            if (graphic is TextMeshProUGUI tmp)
                return tmp.text;
#endif
            return graphic is Text ui ? ui.text : "";
        }

        public static void SetColor(Graphic graphic, Color color)
        {
#if FASHIONRISE_TMP
            if (graphic is TextMeshProUGUI tmp)
            {
                tmp.color = color;
                return;
            }
#endif
            if (graphic is Text ui)
                ui.color = color;
        }

        public static float ResolveSize(FashionRiseTheme theme, FrStudioTypeStyle style)
        {
            var tablet = DeviceLayoutPolicy.IsTabletLike();
            return style switch
            {
                FrStudioTypeStyle.Display => tablet ? theme.DisplaySize : theme.DisplaySize - 4f,
                FrStudioTypeStyle.PageTitle => tablet ? theme.PageTitleSize : theme.PageTitleSize - 2f,
                FrStudioTypeStyle.SectionHeading => tablet ? theme.SectionHeadingSize : 15f,
                FrStudioTypeStyle.Body => tablet ? theme.BodySize : 16f,
                FrStudioTypeStyle.Button => tablet ? theme.ButtonLabelSize : 15f,
                FrStudioTypeStyle.Caption => Mathf.Max(14f, theme.CaptionSize),
                FrStudioTypeStyle.Metadata => Mathf.Max(13f, theme.MetadataSize),
                _ => theme.BodySize
            };
        }

        static Color ResolveColor(FashionRiseTheme theme, FrStudioTypeStyle style, bool muted, FrStudioTypeTone tone)
        {
            if (tone == FrStudioTypeTone.OnLight)
            {
                if (muted || style is FrStudioTypeStyle.Caption or FrStudioTypeStyle.Metadata)
                    return theme.SecondaryText;
                return theme.PrimaryText;
            }

            if (muted || style is FrStudioTypeStyle.Caption or FrStudioTypeStyle.Metadata)
                return theme.ShellMutedText;
            return theme.ShellText;
        }

        static void Stretch(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }

#if FASHIONRISE_TMP
        static TMP_FontAsset? ResolveTmpFont()
        {
            if (ConfiguredFont is TMP_FontAsset assigned && assigned != null)
                return assigned;

            // Resources.Load returns null when the asset is absent. It does not touch TMP Settings.
            return Resources.Load<TMP_FontAsset>("Fonts & Materials/LiberationSans SDF")
                   ?? Resources.Load<TMP_FontAsset>("LiberationSans SDF")
                   ?? Resources.Load<TMP_FontAsset>("Fonts/StudioSans");
        }

        static TextAlignmentOptions ToTmpAlignment(TextAnchor anchor) =>
            anchor switch
            {
                TextAnchor.UpperLeft => TextAlignmentOptions.TopLeft,
                TextAnchor.UpperCenter => TextAlignmentOptions.Top,
                TextAnchor.UpperRight => TextAlignmentOptions.TopRight,
                TextAnchor.MiddleLeft => TextAlignmentOptions.Left,
                TextAnchor.MiddleCenter => TextAlignmentOptions.Center,
                TextAnchor.MiddleRight => TextAlignmentOptions.Right,
                TextAnchor.LowerLeft => TextAlignmentOptions.BottomLeft,
                TextAnchor.LowerCenter => TextAlignmentOptions.Bottom,
                TextAnchor.LowerRight => TextAlignmentOptions.BottomRight,
                _ => TextAlignmentOptions.Left
            };
#endif
    }
}
