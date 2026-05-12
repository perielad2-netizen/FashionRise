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
            return t;
        }
    }
}
