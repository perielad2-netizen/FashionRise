using FashionRise.Content;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioSection
    {
        public RectTransform Root { get; }
        public RectTransform Body { get; }

        FrStudioSection(RectTransform root, RectTransform body)
        {
            Root = root;
            Body = body;
        }

        public static FrStudioSection Build(Transform parent, FashionRiseTheme theme, string heading,
            bool light = true)
        {
            var go = new GameObject(heading + "_Section", typeof(RectTransform), typeof(Image),
                typeof(VerticalLayoutGroup), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.sprite = FrStudioSprites.Rounded(72, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            img.type = Image.Type.Sliced;
            img.color = light ? theme.CanvasCard : theme.ShellElevated;
            img.raycastTarget = false;

            var outline = go.AddComponent<Outline>();
            outline.effectColor = light ? theme.LightBorder : theme.SubtleBorder;
            outline.effectDistance = new Vector2(1f, -1f);

            var le = go.GetComponent<LayoutElement>();
            le.flexibleWidth = 1f;
            le.minHeight = 84f;

            var v = go.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(16, 16, 14, 16);
            v.spacing = theme.SpaceSm;
            v.childAlignment = TextAnchor.UpperLeft;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var headHost = new GameObject("Heading", typeof(RectTransform), typeof(LayoutElement));
            headHost.transform.SetParent(go.transform, false);
            headHost.GetComponent<LayoutElement>().minHeight = 18f;
            var headingLabel = FrStudioTypography.AddLabel(headHost.transform, "H", heading.ToUpperInvariant(), theme,
                FrStudioTypeStyle.Metadata, muted: true, TextAnchor.MiddleLeft,
                light ? FrStudioTypeTone.OnLight : FrStudioTypeTone.OnDark);
            if (light)
                FrStudioTypography.SetColor(headingLabel,
                    new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.95f));

            var body = new GameObject("Body", typeof(RectTransform), typeof(VerticalLayoutGroup));
            body.transform.SetParent(go.transform, false);
            var bv = body.GetComponent<VerticalLayoutGroup>();
            bv.spacing = theme.SpaceXs;
            bv.childAlignment = TextAnchor.UpperLeft;
            bv.childControlWidth = true;
            bv.childControlHeight = true;
            bv.childForceExpandWidth = true;
            bv.childForceExpandHeight = false;
            var bodyLe = body.AddComponent<LayoutElement>();
            bodyLe.flexibleWidth = 1f;

            return new FrStudioSection(go.GetComponent<RectTransform>(), body.GetComponent<RectTransform>());
        }
    }
}
