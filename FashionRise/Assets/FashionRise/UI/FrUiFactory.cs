using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI
{
    public static class FrUiFactory
    {
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
            int fontSize, FontStyle style = FontStyle.Normal, TextAnchor anchor = TextAnchor.UpperLeft)
        {
            var go = new GameObject(name, typeof(Text));
            go.transform.SetParent(parent, false);
            var t = go.GetComponent<Text>();
            t.font = DefaultUiFont;
            t.text = text;
            t.fontSize = fontSize;
            t.fontStyle = style;
            t.color = theme.PrimaryText;
            t.alignment = anchor;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, 48);
            return t;
        }

        public static Button AddButton(Transform parent, string label, FashionRiseTheme theme,
            UnityAction onClick)
        {
            var go = new GameObject(label + "_Btn", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = theme.ButtonFace;
            var btn = go.GetComponent<Button>();
            btn.onClick.AddListener(onClick);
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = DeviceLayoutPolicy.IsTabletLike() ? 56 : 48;
            le.flexibleWidth = 1f;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, DeviceLayoutPolicy.IsTabletLike() ? 56 : 48);

            var txtGo = new GameObject("Text", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = DefaultUiFont;
            txt.text = label;
            txt.fontSize = Mathf.RoundToInt(theme.BodySize);
            txt.color = theme.ButtonText;
            txt.alignment = TextAnchor.MiddleCenter;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = Vector2.zero;
            trt.offsetMax = Vector2.zero;

            return btn;
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
            img.color = theme.ButtonFace;
            var input = go.GetComponent<InputField>();
            input.lineType = InputField.LineType.SingleLine;
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = DeviceLayoutPolicy.IsTabletLike() ? 52 : 44;
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
            trt.offsetMin = new Vector2(12, 6);
            trt.offsetMax = new Vector2(-12, -6);

            var phGo = new GameObject("Placeholder", typeof(Text));
            phGo.transform.SetParent(go.transform, false);
            var ph = phGo.GetComponent<Text>();
            ph.font = DefaultUiFont;
            ph.text = placeholder;
            ph.fontSize = fontSize;
            ph.color = new Color(theme.PrimaryText.r, theme.PrimaryText.g, theme.PrimaryText.b, 0.45f);
            ph.fontStyle = FontStyle.Italic;
            var prt = phGo.GetComponent<RectTransform>();
            prt.anchorMin = Vector2.zero;
            prt.anchorMax = Vector2.one;
            prt.offsetMin = new Vector2(12, 6);
            prt.offsetMax = new Vector2(-12, -6);

            input.textComponent = text;
            input.placeholder = ph;

            return input;
        }
    }
}
