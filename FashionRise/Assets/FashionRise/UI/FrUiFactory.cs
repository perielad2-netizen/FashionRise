using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI
{
    public static class FrUiFactory
    {
        const string BrandLogoResourcePath = "Branding/fashion_rise_logo";

        static Font? s_defaultUiFont;

        static Font DefaultUiFont =>
            s_defaultUiFont != null
                ? s_defaultUiFont
                : (s_defaultUiFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf")!);

        public static RectTransform CreateStretchPanel(Transform parent, string name, FashionRiseTheme theme)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            go.GetComponent<Image>().color = theme.Background;
            return rt;
        }

        public static Text AddLabel(Transform parent, string name, string text, FashionRiseTheme theme,
            int fontSize, FontStyle style = FontStyle.Normal, TextAnchor anchor = TextAnchor.UpperLeft,
            bool useSecondaryTextColor = false)
        {
            var go = new GameObject(name, typeof(Text));
            go.transform.SetParent(parent, false);
            var t = go.GetComponent<Text>();
            t.font = DefaultUiFont;
            t.text = text;
            t.fontSize = fontSize;
            t.fontStyle = style;
            t.color = useSecondaryTextColor ? theme.SecondaryText : theme.PrimaryText;
            t.alignment = anchor;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, 48);
            return t;
        }

        /// <summary>Centers the FashionRise logo when present under Resources/<see cref="BrandLogoResourcePath"/>.</summary>
        public static void AddBrandLogoRow(Transform parent, FashionRiseTheme theme, float maxWidth, float maxHeight)
        {
            var sprite = Resources.Load<Sprite>(BrandLogoResourcePath);
            var row = new GameObject("BrandLogoRow", typeof(HorizontalLayoutGroup));
            var rowRt = row.GetComponent<RectTransform>();
            rowRt.SetParent(parent, false);
            var rowLe = row.AddComponent<LayoutElement>();
            rowLe.minHeight = maxHeight + 20f;
            rowLe.preferredHeight = maxHeight + 20f;
            rowLe.flexibleWidth = 1f;

            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.childAlignment = TextAnchor.MiddleCenter;
            h.spacing = 0f;
            h.padding = new RectOffset(0, 0, 8, 8);
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            h.childForceExpandHeight = false;

            var imgGo = new GameObject("Logo", typeof(Image));
            imgGo.transform.SetParent(row.transform, false);
            var img = imgGo.GetComponent<Image>();
            img.sprite = sprite;
            img.preserveAspect = true;
            img.color = sprite != null ? Color.white : new Color(theme.SecondaryText.r, theme.SecondaryText.g,
                theme.SecondaryText.b, 0.2f);
            var ile = imgGo.AddComponent<LayoutElement>();
            ile.preferredWidth = maxWidth;
            ile.preferredHeight = maxHeight;
            ile.flexibleWidth = 0f;
            ile.flexibleHeight = 0f;
        }

        public static Button AddButton(Transform parent, string label, FashionRiseTheme theme,
            UnityAction onClick, FrButtonEmphasis emphasis = FrButtonEmphasis.Secondary)
        {
            var go = new GameObject(label + "_Btn", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            var txtColor = theme.ButtonText;
            Color face;
            switch (emphasis)
            {
                case FrButtonEmphasis.Primary:
                    face = theme.Accent;
                    txtColor = theme.ButtonPrimaryText;
                    break;
                case FrButtonEmphasis.Destructive:
                    face = theme.ButtonFace;
                    txtColor = theme.Danger;
                    break;
                default:
                    face = theme.ButtonFace;
                    txtColor = theme.ButtonText;
                    break;
            }

            img.color = face;
            AddSoftShadow(go, -4f, 0.12f);

            if (emphasis == FrButtonEmphasis.Secondary)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.45f);
                outline.effectDistance = new Vector2(1f, -1f);
            }
            else if (emphasis == FrButtonEmphasis.Destructive)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = new Color(theme.Danger.r, theme.Danger.g, theme.Danger.b, 0.35f);
                outline.effectDistance = new Vector2(1f, -1f);
            }

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.colorMultiplier = 1f;
            colors.fadeDuration = 0.1f;
            colors.normalColor = Color.white;
            colors.selectedColor = Color.white;
            colors.disabledColor = new Color(0.75f, 0.75f, 0.75f, 0.5f);
            if (emphasis == FrButtonEmphasis.Primary)
            {
                colors.highlightedColor = new Color(0.97f, 0.97f, 0.98f, 1f);
                colors.pressedColor = new Color(0.82f, 0.82f, 0.84f, 1f);
            }
            else if (emphasis == FrButtonEmphasis.Destructive)
            {
                colors.highlightedColor = new Color(0.98f, 0.94f, 0.94f, 1f);
                colors.pressedColor = new Color(0.92f, 0.86f, 0.86f, 1f);
            }
            else
            {
                colors.highlightedColor = new Color(0.99f, 0.99f, 0.99f, 1f);
                colors.pressedColor = new Color(0.9f, 0.89f, 0.88f, 1f);
            }

            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            var le = go.AddComponent<LayoutElement>();
            var h = DeviceLayoutPolicy.IsTabletLike() ? 58f : 52f;
            le.minHeight = h;
            le.flexibleWidth = 1f;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, h);

            var txtGo = new GameObject("Text", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = DefaultUiFont;
            txt.text = label;
            txt.fontSize = Mathf.RoundToInt(theme.BodySize);
            txt.color = txtColor;
            txt.alignment = TextAnchor.MiddleCenter;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(16f, 0f);
            trt.offsetMax = new Vector2(-16f, 0f);

            return btn;
        }

        static void AddSoftShadow(GameObject go, float offsetY, float alpha)
        {
            var s = go.AddComponent<Shadow>();
            s.effectColor = new Color(0f, 0f, 0f, alpha);
            s.effectDistance = new Vector2(0f, offsetY);
            s.useGraphicAlpha = true;
        }

        public static RectTransform AddVerticalLayout(Transform parent, string name, float spacing,
            TextAnchor childAlignment)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(VerticalLayoutGroup));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = new Vector2(0, 0);
            rt.anchorMax = new Vector2(1, 1);
            rt.offsetMin = new Vector2(DeviceLayoutPolicy.ContentPadding, DeviceLayoutPolicy.ContentPadding);
            rt.offsetMax = new Vector2(-DeviceLayoutPolicy.ContentPadding, -DeviceLayoutPolicy.ContentPadding);
            var v = go.GetComponent<VerticalLayoutGroup>();
            v.spacing = spacing;
            v.childAlignment = childAlignment;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            return rt;
        }

        public static UnityEngine.UI.InputField AddInputField(Transform parent, string name, string placeholder,
            FashionRiseTheme theme, int fontSize)
        {
            var go = new GameObject(name, typeof(Image), typeof(InputField));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = theme.Card;
            AddSoftShadow(go, -3f, 0.08f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.35f);
            outline.effectDistance = new Vector2(1f, -1f);
            var input = go.GetComponent<InputField>();
            input.lineType = InputField.LineType.SingleLine;
            var le = go.AddComponent<LayoutElement>();
            var h = DeviceLayoutPolicy.IsTabletLike() ? 56f : 52f;
            le.minHeight = h;
            le.flexibleWidth = 1f;

            var textGo = new GameObject("Text", typeof(Text));
            textGo.transform.SetParent(go.transform, false);
            var text = textGo.GetComponent<Text>();
            text.font = DefaultUiFont;
            text.text = "";
            text.fontSize = fontSize;
            text.color = theme.PrimaryText;
            text.supportRichText = false;
            var trt = textGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(16f, 8f);
            trt.offsetMax = new Vector2(-16f, -8f);

            var phGo = new GameObject("Placeholder", typeof(Text));
            phGo.transform.SetParent(go.transform, false);
            var ph = phGo.GetComponent<Text>();
            ph.font = DefaultUiFont;
            ph.text = placeholder;
            ph.fontSize = fontSize;
            ph.color = new Color(theme.SecondaryText.r, theme.SecondaryText.g, theme.SecondaryText.b, 0.55f);
            ph.fontStyle = FontStyle.Italic;
            var prt = phGo.GetComponent<RectTransform>();
            prt.anchorMin = Vector2.zero;
            prt.anchorMax = Vector2.one;
            prt.offsetMin = new Vector2(16f, 8f);
            prt.offsetMax = new Vector2(-16f, -8f);

            input.textComponent = text;
            input.placeholder = ph;

            return input;
        }
    }
}
