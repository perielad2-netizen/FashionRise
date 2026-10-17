using UnityEngine;

namespace FashionRise.Content
{
    [CreateAssetMenu(menuName = "FashionRise/UI Theme", fileName = "FashionRiseTheme")]
    public sealed class FashionRiseTheme : ScriptableObject
    {
        [Header("Surfaces")]
        public Color Background = new(1f, 250f / 255f, 245f / 255f, 1f);
        public Color Panel = new(248f / 255f, 244f / 255f, 240f / 255f, 0.94f);
        public Color Card = new(248f / 255f, 244f / 255f, 240f / 255f, 1f);

        [Header("Text")]
        public Color PrimaryText = new(28f / 255f, 28f / 255f, 30f / 255f, 1f);
        public Color SecondaryText = new(107f / 255f, 114f / 255f, 128f / 255f, 1f);

        [Header("Brand")]
        public Color MidnightNavy = new(17f / 255f, 24f / 255f, 39f / 255f, 1f);

        [Header("Accents")]
        public Color Accent = new(236f / 255f, 72f / 255f, 153f / 255f, 1f);
        public Color AccentMuted = new(212f / 255f, 175f / 255f, 155f / 255f, 1f);
        public Color Danger = new(0.52f, 0.2f, 0.24f, 1f);

        [Header("Controls")]
        public Color ButtonFace = new(1f, 0.995f, 0.99f, 1f);
        public Color ButtonText = new(17f / 255f, 24f / 255f, 39f / 255f, 1f);
        public Color ButtonPrimaryText = Color.white;

        [Header("Typography (UI units)")]
        public float TitleSize = 34f;
        public float SubtitleSize = 20f;
        public float BodySize = 17f;
        public float CaptionSize = 14f;

        [Header("Spacing")]
        public float ScreenPadding = 40f;
        public float SectionGap = 28f;
        public float ControlGap = 14f;

        [Header("Studio shell")]
        public Color ShellBackground = new(17f / 255f, 24f / 255f, 39f / 255f, 1f);
        public Color ShellElevated = new(31f / 255f, 41f / 255f, 55f / 255f, 1f);
        public Color ShellPanel = new(22f / 255f, 30f / 255f, 46f / 255f, 1f);
        public Color ShellText = new(255f / 255f, 250f / 255f, 245f / 255f, 1f);
        public Color ShellMutedText = new(156f / 255f, 163f / 255f, 175f / 255f, 1f);

        [Header("Studio canvas")]
        public Color CanvasSurface = new(1f, 250f / 255f, 245f / 255f, 1f);
        public Color CanvasCard = new(248f / 255f, 244f / 255f, 240f / 255f, 1f);
        public Color CanvasWell = new(255f / 255f, 253f / 255f, 249f / 255f, 1f);

        [Header("Studio states")]
        public Color SubtleBorder = new(55f / 255f, 65f / 255f, 81f / 255f, 0.85f);
        public Color LightBorder = new(212f / 255f, 175f / 255f, 155f / 255f, 0.45f);
        public Color Divider = new(55f / 255f, 65f / 255f, 81f / 255f, 0.55f);
        public Color Hover = new(255f / 255f, 255f / 255f, 255f / 255f, 0.08f);
        public Color Pressed = new(0f, 0f, 0f, 0.18f);
        public Color Selected = new(236f / 255f, 72f / 255f, 153f / 255f, 1f);
        public Color Disabled = new(107f / 255f, 114f / 255f, 128f / 255f, 0.45f);
        public Color Shadow = new(0f, 0f, 0f, 0.28f);
        public Color AiAccent = new(236f / 255f, 72f / 255f, 153f / 255f, 1f);
        public Color AiAccentPressed = new(190f / 255f, 50f / 255f, 122f / 255f, 1f);

        [Header("Studio metrics")]
        public float CornerRadiusSmall = 8f;
        public float CornerRadiusMedium = 14f;
        public float CornerRadiusLarge = 22f;
        public float ShadowAlpha = 0.28f;
        public float IconSize = 22f;
        public float MinTouchTarget = 48f;
        public float SpaceXs = 6f;
        public float SpaceSm = 10f;
        public float SpaceMd = 16f;
        public float SpaceLg = 24f;
        public float SpaceXl = 36f;
        public float DisplaySize = 30f;
        public float PageTitleSize = 22f;
        public float SectionHeadingSize = 16f;
        public float ButtonLabelSize = 16f;
        public float MetadataSize = 13f;

        public static FashionRiseTheme CreateRuntimeFallback()
        {
            var t = CreateInstance<FashionRiseTheme>();
            t.name = "RuntimeFallbackTheme";
            t.Background = new Color(1f, 250f / 255f, 245f / 255f, 1f);
            t.Panel = new Color(248f / 255f, 244f / 255f, 240f / 255f, 0.94f);
            t.Card = new Color(248f / 255f, 244f / 255f, 240f / 255f, 1f);
            t.PrimaryText = new Color(28f / 255f, 28f / 255f, 30f / 255f, 1f);
            t.SecondaryText = new Color(107f / 255f, 114f / 255f, 128f / 255f, 1f);
            t.MidnightNavy = new Color(17f / 255f, 24f / 255f, 39f / 255f, 1f);
            t.Accent = new Color(236f / 255f, 72f / 255f, 153f / 255f, 1f);
            t.AccentMuted = new Color(212f / 255f, 175f / 255f, 155f / 255f, 1f);
            t.Danger = new Color(0.52f, 0.2f, 0.24f, 1f);
            t.ButtonFace = new Color(1f, 0.995f, 0.99f, 1f);
            t.ButtonText = new Color(17f / 255f, 24f / 255f, 39f / 255f, 1f);
            t.ButtonPrimaryText = Color.white;
            t.TitleSize = 34f;
            t.SubtitleSize = 20f;
            t.BodySize = 17f;
            t.CaptionSize = 14f;
            t.ScreenPadding = 40f;
            t.SectionGap = 28f;
            t.ControlGap = 14f;
            t.ShellBackground = new Color(17f / 255f, 24f / 255f, 39f / 255f, 1f);
            t.ShellElevated = new Color(31f / 255f, 41f / 255f, 55f / 255f, 1f);
            t.ShellPanel = new Color(22f / 255f, 30f / 255f, 46f / 255f, 1f);
            t.ShellText = new Color(255f / 255f, 250f / 255f, 245f / 255f, 1f);
            t.ShellMutedText = new Color(156f / 255f, 163f / 255f, 175f / 255f, 1f);
            t.CanvasSurface = new Color(1f, 250f / 255f, 245f / 255f, 1f);
            t.CanvasCard = new Color(248f / 255f, 244f / 255f, 240f / 255f, 1f);
            t.CanvasWell = new Color(255f / 255f, 253f / 255f, 249f / 255f, 1f);
            t.SubtleBorder = new Color(55f / 255f, 65f / 255f, 81f / 255f, 0.85f);
            t.LightBorder = new Color(212f / 255f, 175f / 255f, 155f / 255f, 0.45f);
            t.Divider = new Color(55f / 255f, 65f / 255f, 81f / 255f, 0.55f);
            t.Hover = new Color(255f / 255f, 255f / 255f, 255f / 255f, 0.08f);
            t.Pressed = new Color(0f, 0f, 0f, 0.18f);
            t.Selected = new Color(236f / 255f, 72f / 255f, 153f / 255f, 1f);
            t.Disabled = new Color(107f / 255f, 114f / 255f, 128f / 255f, 0.45f);
            t.Shadow = new Color(0f, 0f, 0f, 0.28f);
            t.AiAccent = new Color(236f / 255f, 72f / 255f, 153f / 255f, 1f);
            t.AiAccentPressed = new Color(190f / 255f, 50f / 255f, 122f / 255f, 1f);
            t.CornerRadiusSmall = 8f;
            t.CornerRadiusMedium = 14f;
            t.CornerRadiusLarge = 22f;
            t.ShadowAlpha = 0.28f;
            t.IconSize = 22f;
            t.MinTouchTarget = 48f;
            t.SpaceXs = 6f;
            t.SpaceSm = 10f;
            t.SpaceMd = 16f;
            t.SpaceLg = 24f;
            t.SpaceXl = 36f;
            t.DisplaySize = 30f;
            t.PageTitleSize = 22f;
            t.SectionHeadingSize = 16f;
            t.ButtonLabelSize = 16f;
            t.MetadataSize = 13f;
            return t;
        }
    }
}
