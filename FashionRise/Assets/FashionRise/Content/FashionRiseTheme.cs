using UnityEngine;

namespace FashionRise.Content
{
    /// <summary>
    /// Premium fashion-AI design tokens — ivory atelier, charcoal type, champagne AI accent.
    /// </summary>
    [CreateAssetMenu(menuName = "FashionRise/UI Theme", fileName = "FashionRiseTheme")]
    public sealed class FashionRiseTheme : ScriptableObject
    {
        [Header("Surfaces — ivory atelier")]
        public Color Background = new(247f / 255f, 244f / 255f, 239f / 255f, 1f);
        public Color BackgroundDeep = new(236f / 255f, 230f / 255f, 220f / 255f, 1f);
        public Color BackgroundSky = new(250f / 255f, 248f / 255f, 244f / 255f, 1f);
        public Color Panel = new(255f / 255f, 253f / 255f, 249f / 255f, 0.92f);
        public Color Card = new(255f / 255f, 255f / 255f, 255f / 255f, 0.96f);
        public Color Stage = new(255f / 255f, 255f / 255f, 255f / 255f, 0.62f);
        public Color Hairline = new(26f / 255f, 26f / 255f, 26f / 255f, 0.12f);

        [Header("Text")]
        public Color PrimaryText = new(20f / 255f, 20f / 255f, 20f / 255f, 1f);
        public Color SecondaryText = new(107f / 255f, 101f / 255f, 96f / 255f, 1f);

        [Header("Brand")]
        public Color MidnightNavy = new(20f / 255f, 20f / 255f, 20f / 255f, 1f);
        public Color Charcoal = new(20f / 255f, 20f / 255f, 20f / 255f, 1f);

        [Header("Accents — champagne + AI rose-gold")]
        public Color Accent = new(168f / 255f, 135f / 255f, 90f / 255f, 1f);
        public Color AccentHot = new(183f / 255f, 110f / 255f, 121f / 255f, 1f);
        public Color AccentMuted = new(212f / 255f, 196f / 255f, 168f / 255f, 1f);
        public Color Champagne = new(212f / 255f, 184f / 255f, 140f / 255f, 1f);
        public Color AiGlow = new(196f / 255f, 165f / 255f, 116f / 255f, 0.55f);
        public Color Danger = new(0.45f, 0.16f, 0.18f, 1f);

        [Header("Controls")]
        public Color ButtonFace = new(255f / 255f, 255f / 255f, 255f / 255f, 0.94f);
        public Color ButtonText = new(20f / 255f, 20f / 255f, 20f / 255f, 1f);
        public Color ButtonPrimaryText = Color.white;
        public Color ButtonAiFace = new(20f / 255f, 20f / 255f, 20f / 255f, 1f);

        [Header("Typography (UI units)")]
        public float DisplaySize = 52f;
        public float TitleSize = 36f;
        public float SubtitleSize = 18f;
        public float BodySize = 16f;
        public float CaptionSize = 13f;
        public float OverlineSize = 11f;

        [Header("Spacing")]
        public float ScreenPadding = 32f;
        public float SectionGap = 20f;
        public float ControlGap = 12f;
        public float HairlineThickness = 1f;

        public static FashionRiseTheme CreateRuntimeFallback()
        {
            var t = CreateInstance<FashionRiseTheme>();
            t.name = "RuntimeFallbackTheme";
            return t;
        }
    }
}
