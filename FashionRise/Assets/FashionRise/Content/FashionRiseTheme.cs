using UnityEngine;

namespace FashionRise.Content
{
    [CreateAssetMenu(menuName = "FashionRise/UI Theme", fileName = "FashionRiseTheme")]
    public sealed class FashionRiseTheme : ScriptableObject
    {
        [Header("Surfaces")]
        public Color Background = new(0.98f, 0.97f, 0.95f, 1f);
        public Color Panel = new(1f, 1f, 1f, 0.92f);
        public Color Card = new(0.99f, 0.98f, 0.96f, 1f);

        [Header("Text")]
        public Color PrimaryText = new(0.16f, 0.14f, 0.13f, 1f);
        public Color SecondaryText = new(0.42f, 0.38f, 0.35f, 1f);

        [Header("Accents")]
        public Color Accent = new(0.55f, 0.42f, 0.38f, 1f);
        public Color AccentMuted = new(0.78f, 0.72f, 0.68f, 1f);
        public Color Danger = new(0.65f, 0.3f, 0.28f, 1f);

        [Header("Controls")]
        public Color ButtonFace = new(0.93f, 0.9f, 0.86f, 1f);
        public Color ButtonText = new(0.2f, 0.18f, 0.16f, 1f);

        [Header("Typography (UI units)")]
        public float TitleSize = 32f;
        public float SubtitleSize = 22f;
        public float BodySize = 18f;
        public float CaptionSize = 14f;

        [Header("Spacing")]
        public float ScreenPadding = 40f;
        public float SectionGap = 24f;
        public float ControlGap = 12f;

        public static FashionRiseTheme CreateRuntimeFallback()
        {
            var t = CreateInstance<FashionRiseTheme>();
            t.name = "RuntimeFallbackTheme";
            return t;
        }
    }
}
