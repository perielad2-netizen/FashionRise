using UnityEngine;

namespace FashionRise.Content
{
    [CreateAssetMenu(menuName = "FashionRise/UI Theme", fileName = "FashionRiseTheme")]
    public sealed class FashionRiseTheme : ScriptableObject
    {
        [Header("Surfaces — soft runway studio")]
        public Color Background = new(1f, 246f / 255f, 248f / 255f, 1f);
        public Color BackgroundDeep = new(255f / 255f, 228f / 255f, 236f / 255f, 1f);
        public Color BackgroundSky = new(232f / 255f, 244f / 255f, 255f / 255f, 1f);
        public Color Panel = new(1f, 1f, 1f, 0.78f);
        public Color Card = new(1f, 1f, 1f, 0.94f);
        public Color Stage = new(1f, 1f, 1f, 0.55f);

        [Header("Text")]
        public Color PrimaryText = new(34f / 255f, 24f / 255f, 36f / 255f, 1f);
        public Color SecondaryText = new(110f / 255f, 90f / 255f, 108f / 255f, 1f);

        [Header("Brand")]
        public Color MidnightNavy = new(42f / 255f, 28f / 255f, 48f / 255f, 1f);

        [Header("Accents — rose runway (not purple)")]
        public Color Accent = new(236f / 255f, 72f / 255f, 153f / 255f, 1f);
        public Color AccentHot = new(255f / 255f, 90f / 255f, 140f / 255f, 1f);
        public Color AccentMuted = new(232f / 255f, 180f / 255f, 170f / 255f, 1f);
        public Color Champagne = new(255f / 255f, 214f / 255f, 170f / 255f, 1f);
        public Color Danger = new(0.55f, 0.18f, 0.26f, 1f);

        [Header("Controls")]
        public Color ButtonFace = new(1f, 1f, 1f, 0.92f);
        public Color ButtonText = new(42f / 255f, 28f / 255f, 48f / 255f, 1f);
        public Color ButtonPrimaryText = Color.white;

        [Header("Typography (UI units)")]
        public float TitleSize = 40f;
        public float SubtitleSize = 22f;
        public float BodySize = 18f;
        public float CaptionSize = 14f;

        [Header("Spacing")]
        public float ScreenPadding = 28f;
        public float SectionGap = 22f;
        public float ControlGap = 12f;

        public static FashionRiseTheme CreateRuntimeFallback()
        {
            var t = CreateInstance<FashionRiseTheme>();
            t.name = "RuntimeFallbackTheme";
            t.Background = new Color(1f, 246f / 255f, 248f / 255f, 1f);
            t.BackgroundDeep = new Color(255f / 255f, 228f / 255f, 236f / 255f, 1f);
            t.BackgroundSky = new Color(232f / 255f, 244f / 255f, 255f / 255f, 1f);
            t.Panel = new Color(1f, 1f, 1f, 0.78f);
            t.Card = new Color(1f, 1f, 1f, 0.94f);
            t.Stage = new Color(1f, 1f, 1f, 0.55f);
            t.PrimaryText = new Color(34f / 255f, 24f / 255f, 36f / 255f, 1f);
            t.SecondaryText = new Color(110f / 255f, 90f / 255f, 108f / 255f, 1f);
            t.MidnightNavy = new Color(42f / 255f, 28f / 255f, 48f / 255f, 1f);
            t.Accent = new Color(236f / 255f, 72f / 255f, 153f / 255f, 1f);
            t.AccentHot = new Color(255f / 255f, 90f / 255f, 140f / 255f, 1f);
            t.AccentMuted = new Color(232f / 255f, 180f / 255f, 170f / 255f, 1f);
            t.Champagne = new Color(255f / 255f, 214f / 255f, 170f / 255f, 1f);
            t.Danger = new Color(0.55f, 0.18f, 0.26f, 1f);
            t.ButtonFace = new Color(1f, 1f, 1f, 0.92f);
            t.ButtonText = new Color(42f / 255f, 28f / 255f, 48f / 255f, 1f);
            t.ButtonPrimaryText = Color.white;
            t.TitleSize = 40f;
            t.SubtitleSize = 22f;
            t.BodySize = 18f;
            t.CaptionSize = 14f;
            t.ScreenPadding = 28f;
            t.SectionGap = 22f;
            t.ControlGap = 12f;
            return t;
        }
    }
}
