using FashionRise.Content;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioInspector
    {
        public RectTransform Root { get; }
        public RectTransform ScrollBody { get; }
        public RectTransform Footer { get; }
        public Graphic Status { get; }

        FrStudioInspector(RectTransform root, RectTransform scrollBody, RectTransform footer, Graphic status)
        {
            Root = root;
            ScrollBody = scrollBody;
            Footer = footer;
            Status = status;
        }

        public static FrStudioInspector Build(Transform parent, FashionRiseTheme theme)
        {
            var go = new GameObject("StudioInspector", typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var img = go.GetComponent<Image>();
            img.sprite = FrStudioSprites.Rounded(72, 20, Color.white);
            img.type = Image.Type.Sliced;
            img.color = theme.CanvasSurface;
            img.raycastTarget = true;
            var panelShade = go.AddComponent<Shadow>();
            panelShade.effectColor = new Color(0f, 0f, 0f, 0.16f);
            panelShade.effectDistance = new Vector2(0f, -4f);
            var panelRim = go.AddComponent<Outline>();
            panelRim.effectColor = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.35f);
            panelRim.effectDistance = new Vector2(1f, -1f);

            var vGo = new GameObject("Stack", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var vRt = vGo.GetComponent<RectTransform>();
            vRt.SetParent(rt, false);
            vRt.anchorMin = Vector2.zero;
            vRt.anchorMax = Vector2.one;
            vRt.offsetMin = new Vector2(theme.SpaceMd, theme.SpaceMd);
            vRt.offsetMax = new Vector2(-theme.SpaceMd, -theme.SpaceMd);
            var v = vGo.GetComponent<VerticalLayoutGroup>();
            v.spacing = theme.SpaceMd;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var titleHost = new GameObject("InspTitle", typeof(RectTransform), typeof(LayoutElement));
            titleHost.transform.SetParent(vGo.transform, false);
            titleHost.GetComponent<LayoutElement>().minHeight = 32f;
            FrStudioTypography.AddLabel(titleHost.transform, "T", "Studio", theme,
                FrStudioTypeStyle.PageTitle, muted: false, TextAnchor.MiddleLeft, FrStudioTypeTone.OnLight);

            var hairline = new GameObject("TitleRule", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            hairline.transform.SetParent(vGo.transform, false);
            hairline.GetComponent<LayoutElement>().minHeight = 2f;
            hairline.GetComponent<LayoutElement>().preferredHeight = 2f;
            hairline.GetComponent<Image>().color = new Color(theme.AccentMuted.r, theme.AccentMuted.g,
                theme.AccentMuted.b, 0.45f);
            hairline.GetComponent<Image>().raycastTarget = false;

            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(Image),
                typeof(RectMask2D), typeof(LayoutElement));
            scrollGo.transform.SetParent(vGo.transform, false);
            scrollGo.GetComponent<Image>().color = new Color(0f, 0f, 0f, 0f);
            scrollGo.GetComponent<Image>().raycastTarget = true;
            var scrollLe = scrollGo.GetComponent<LayoutElement>();
            scrollLe.flexibleHeight = 1f;
            scrollLe.minHeight = 100f;
            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.horizontal = false;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 24f;

            var content = new GameObject("Content", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            content.transform.SetParent(scrollGo.transform, false);
            var contentRt = content.GetComponent<RectTransform>();
            contentRt.anchorMin = new Vector2(0f, 1f);
            contentRt.anchorMax = new Vector2(1f, 1f);
            contentRt.pivot = new Vector2(0.5f, 1f);
            contentRt.sizeDelta = new Vector2(0f, 0f);
            var cv = content.GetComponent<VerticalLayoutGroup>();
            cv.spacing = theme.SpaceMd;
            cv.childAlignment = TextAnchor.UpperCenter;
            cv.childControlWidth = true;
            cv.childControlHeight = true;
            cv.childForceExpandWidth = true;
            cv.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            scroll.content = contentRt;
            scroll.viewport = scrollGo.GetComponent<RectTransform>();

            var statusHost = new GameObject("StatusHost", typeof(RectTransform), typeof(LayoutElement));
            statusHost.transform.SetParent(vGo.transform, false);
            statusHost.GetComponent<LayoutElement>().minHeight = 40f;
            var status = FrStudioTypography.AddLabel(statusHost.transform, "Status", " ", theme,
                FrStudioTypeStyle.Caption, muted: true, TextAnchor.UpperLeft, FrStudioTypeTone.OnLight);

            var footer = new GameObject("Footer", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(LayoutElement));
            footer.transform.SetParent(vGo.transform, false);
            footer.GetComponent<LayoutElement>().minHeight = 78f;
            var fv = footer.GetComponent<VerticalLayoutGroup>();
            fv.spacing = 0f;
            fv.childAlignment = TextAnchor.LowerCenter;
            fv.childControlWidth = true;
            fv.childControlHeight = true;
            fv.childForceExpandWidth = true;
            fv.childForceExpandHeight = false;

            return new FrStudioInspector(rt, contentRt, footer.GetComponent<RectTransform>(), status);
        }

        public void SetStatus(string text) => FrStudioTypography.SetText(Status, text);
    }
}
