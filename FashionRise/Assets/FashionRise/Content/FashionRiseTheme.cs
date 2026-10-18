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
        // Style board: Midnight Navy #0F172A
        public Color MidnightNavy = new(15f / 255f, 23f / 255f, 42f / 255f, 1f);

        [Header("Accents")]
        // Style board: Hot Pink #FF2D8A
        public Color Accent = new(1f, 45f / 255f, 138f / 255f, 1f);
        // Style board: Rose Gold #D4A796
        public Color AccentMuted = new(212f / 255f, 167f / 255f, 150f / 255f, 1f);
        // Style board: Blush #F7C8D0
        public Color Blush = new(247f / 255f, 200f / 255f, 208f / 255f, 1f);
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
        public Color ShellBackground = new(15f / 255f, 23f / 255f, 42f / 255f, 1f);
        public Color ShellElevated = new(30f / 255f, 41f / 255f, 59f / 255f, 1f);
        public Color ShellPanel = new(15f / 255f, 23f / 255f, 42f / 255f, 1f);
        public Color ShellText = new(253f / 255f, 248f / 255f, 243f / 255f, 1f);
        public Color ShellMutedText = new(168f / 255f, 174f / 255f, 186f / 255f, 1f);

        [Header("Studio canvas")]
        // Style board: Cream #FDF8F3 / Soft Gray #E5E7EB
        public Color CanvasSurface = new(253f / 255f, 248f / 255f, 243f / 255f, 1f);
        public Color CanvasCard = new(1f, 1f, 1f, 1f);
        public Color CanvasWell = new(253f / 255f, 248f / 255f, 243f / 255f, 1f);

        [Header("Studio states")]
        public Color SubtleBorder = new(55f / 255f, 65f / 255f, 81f / 255f, 0.7f);
        public Color LightBorder = new(212f / 255f, 175f / 255f, 155f / 255f, 0.55f);
        public Color Divider = new(55f / 255f, 65f / 255f, 81f / 255f, 0.4f);
        public Color Hover = new(255f / 255f, 255f / 255f, 255f / 255f, 0.08f);
        public Color Pressed = new(0f, 0f, 0f, 0.18f);
        public Color Selected = new(1f, 45f / 255f, 138f / 255f, 1f);
        public Color SelectedSoft = new(1f, 45f / 255f, 138f / 255f, 0.14f);
        public Color Disabled = new(107f / 255f, 114f / 255f, 128f / 255f, 0.45f);
        public Color Shadow = new(0f, 0f, 0f, 0.32f);
        public Color AiAccent = new(1f, 45f / 255f, 138f / 255f, 1f);
        public Color AiAccentPressed = new(210f / 255f, 30f / 255f, 110f / 255f, 1f);

        [Header("Studio metrics")]
        public float CornerRadiusSmall = 10f;
        public float CornerRadiusMedium = 16f;
        public float CornerRadiusLarge = 26f;
        public float ShadowAlpha = 0.32f;
        public float IconSize = 24f;
        public float MinTouchTarget = 48f;
        public float SpaceXs = 6f;
        public float SpaceSm = 12f;
        public float SpaceMd = 18f;
        public float SpaceLg = 26f;
        public float SpaceXl = 40f;
        public float DisplaySize = 36f;
        public float PageTitleSize = 26f;
        public float SectionHeadingSize = 15f;
        public float ButtonLabelSize = 15f;
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
            t.MidnightNavy = new Color(15f / 255f, 23f / 255f, 42f / 255f, 1f);
            t.Accent = new Color(1f, 45f / 255f, 138f / 255f, 1f);
            t.AccentMuted = new Color(212f / 255f, 167f / 255f, 150f / 255f, 1f);
            t.Blush = new Color(247f / 255f, 200f / 255f, 208f / 255f, 1f);
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
            t.ShellBackground = new Color(15f / 255f, 23f / 255f, 42f / 255f, 1f);
            t.ShellElevated = new Color(30f / 255f, 41f / 255f, 59f / 255f, 1f);
            t.ShellPanel = new Color(15f / 255f, 23f / 255f, 42f / 255f, 1f);
            t.ShellText = new Color(253f / 255f, 248f / 255f, 243f / 255f, 1f);
            t.ShellMutedText = new Color(168f / 255f, 174f / 255f, 186f / 255f, 1f);
            t.CanvasSurface = new Color(253f / 255f, 248f / 255f, 243f / 255f, 1f);
            t.CanvasCard = Color.white;
            t.CanvasWell = new Color(253f / 255f, 248f / 255f, 243f / 255f, 1f);
            t.SubtleBorder = new Color(55f / 255f, 65f / 255f, 81f / 255f, 0.7f);
            t.LightBorder = new Color(212f / 255f, 175f / 255f, 155f / 255f, 0.55f);
            t.Divider = new Color(55f / 255f, 65f / 255f, 81f / 255f, 0.4f);
            t.Hover = new Color(255f / 255f, 255f / 255f, 255f / 255f, 0.08f);
            t.Pressed = new Color(0f, 0f, 0f, 0.18f);
            t.Selected = new Color(1f, 45f / 255f, 138f / 255f, 1f);
            t.SelectedSoft = new Color(1f, 45f / 255f, 138f / 255f, 0.14f);
            t.Disabled = new Color(107f / 255f, 114f / 255f, 128f / 255f, 0.45f);
            t.Shadow = new Color(0f, 0f, 0f, 0.32f);
            t.AiAccent = new Color(1f, 45f / 255f, 138f / 255f, 1f);
            t.AiAccentPressed = new Color(210f / 255f, 30f / 255f, 110f / 255f, 1f);
            t.CornerRadiusSmall = 10f;
            t.CornerRadiusMedium = 16f;
            t.CornerRadiusLarge = 26f;
            t.ShadowAlpha = 0.32f;
            t.IconSize = 24f;
            t.MinTouchTarget = 48f;
            t.SpaceXs = 6f;
            t.SpaceSm = 12f;
            t.SpaceMd = 18f;
            t.SpaceLg = 26f;
            t.SpaceXl = 40f;
            t.DisplaySize = 36f;
            t.PageTitleSize = 26f;
            t.SectionHeadingSize = 15f;
            t.ButtonLabelSize = 15f;
            t.MetadataSize = 13f;
            return t;
        }
    }
}
