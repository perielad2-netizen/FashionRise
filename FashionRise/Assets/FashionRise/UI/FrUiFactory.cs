using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.UI
{
    public static class FrUiFactory
    {
        const string BrandLogoResourcePath = "Branding/fashion_rise_logo";

        static Font? s_defaultUiFont;
        static Sprite? s_whiteSprite;
        static Texture2D? s_vGradTex;
        static Sprite? s_vGradSprite;
        static Color s_vGradTop;
        static Color s_vGradBottom;
        static Texture2D? s_softBlobTex;
        static Sprite? s_softBlobSprite;

        static Font DefaultUiFont =>
            s_defaultUiFont != null
                ? s_defaultUiFont
                : (s_defaultUiFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf")!);

        static Sprite WhiteSprite
        {
            get
            {
                if (s_whiteSprite != null)
                    return s_whiteSprite;
                var tex = Texture2D.whiteTexture;
                s_whiteSprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f), 100f);
                return s_whiteSprite;
            }
        }

        /// <summary>Full-bleed soft runway atmosphere (blush → sky), not a flat fill.</summary>
        public static RectTransform CreateStretchPanel(Transform parent, string name, FashionRiseTheme theme)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var baseImg = go.GetComponent<Image>();
            baseImg.sprite = VerticalGradientSprite(theme.BackgroundDeep, theme.BackgroundSky);
            baseImg.type = Image.Type.Simple;
            baseImg.color = Color.white;
            baseImg.raycastTarget = true;

            // Soft light blobs for studio bokeh (no hard cards).
            AddAtmosphereBlob(rt, theme.Champagne, new Vector2(0.12f, 0.78f), 0.55f, 0.22f);
            AddAtmosphereBlob(rt, theme.AccentHot, new Vector2(0.88f, 0.72f), 0.48f, 0.14f);
            AddAtmosphereBlob(rt, theme.BackgroundSky, new Vector2(0.5f, 0.08f), 0.9f, 0.18f);
            return rt;
        }

        static void AddAtmosphereBlob(RectTransform parent, Color color, Vector2 anchor, float size, float alpha)
        {
            var go = new GameObject("AtmosBlob", typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = anchor;
            rt.anchorMax = anchor;
            rt.pivot = new Vector2(0.5f, 0.5f);
            var px = Mathf.Max(180f, parent.rect.width * size);
            if (px < 220f)
                px = 320f;
            rt.sizeDelta = new Vector2(px, px);
            var img = go.GetComponent<Image>();
            img.sprite = SoftBlobSprite();
            img.color = new Color(color.r, color.g, color.b, alpha);
            img.raycastTarget = false;
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
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = fontSize + 18f;
            le.preferredHeight = fontSize + 28f;
            le.flexibleWidth = 1f;
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
            rowLe.minHeight = maxHeight + 12f;
            rowLe.preferredHeight = maxHeight + 12f;
            rowLe.flexibleWidth = 1f;

            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.childAlignment = TextAnchor.MiddleCenter;
            h.spacing = 0f;
            h.padding = new RectOffset(0, 0, 4, 4);
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

            var motion = imgGo.AddComponent<FrUiMotion>();
            motion.EnablePulse(true);
        }

        /// <summary>
        /// Visual-first Girl/Boy choice tile (inspired by dress-up pickers — FashionRise uses croquis, not shop items).
        /// </summary>
        public static Button AddModelChoiceTile(Transform parent, string name, string label, string resourcePath,
            FashionRiseTheme theme, UnityAction onClick)
        {
            var go = new GameObject(name + "_Tile", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = WhiteSprite;
            face.color = theme.Card;
            AddSoftShadow(go, -6f, 0.14f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(theme.Accent.r, theme.Accent.g, theme.Accent.b, 0.35f);
            outline.effectDistance = new Vector2(2f, -2f);

            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 210f;
            le.preferredHeight = 240f;
            le.flexibleWidth = 1f;

            var v = go.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(10, 10, 12, 12);
            v.spacing = 8f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            var previewGo = new GameObject("Preview", typeof(Image), typeof(LayoutElement), typeof(AspectRatioFitter));
            previewGo.transform.SetParent(go.transform, false);
            var preview = previewGo.GetComponent<Image>();
            preview.preserveAspect = true;
            preview.raycastTarget = false;
            var sprite = Resources.Load<Sprite>(resourcePath);
            Texture2D? tex = null;
            if (sprite != null)
            {
                preview.sprite = sprite;
                preview.color = Color.white;
            }
            else
            {
                tex = Resources.Load<Texture2D>(resourcePath);
                if (tex != null)
                {
                    preview.sprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f),
                        100f);
                    preview.color = Color.white;
                }
                else
                {
                    preview.sprite = WhiteSprite;
                    preview.color = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.35f);
                }
            }

            var previewLe = previewGo.GetComponent<LayoutElement>();
            previewLe.minHeight = 150f;
            previewLe.preferredHeight = 170f;
            previewLe.flexibleHeight = 1f;
            var fitter = previewGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
            if (sprite != null && sprite.rect.height > 0)
                fitter.aspectRatio = sprite.rect.width / sprite.rect.height;
            else if (tex != null && tex.height > 0)
                fitter.aspectRatio = tex.width / (float)tex.height;
            else
                fitter.aspectRatio = 0.7f;

            var caption = AddLabel(go.transform, "Cap", label, theme, Mathf.RoundToInt(theme.SubtitleSize),
                FontStyle.Bold, TextAnchor.MiddleCenter);
            caption.color = theme.MidnightNavy;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 0.97f, 0.98f, 1f);
            colors.pressedColor = new Color(0.94f, 0.9f, 0.92f, 1f);
            colors.selectedColor = Color.white;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);

            var motion = go.AddComponent<FrUiMotion>();
            WirePressMotion(btn, motion);
            return btn;
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

            img.sprite = WhiteSprite;
            img.color = face;
            AddSoftShadow(go, emphasis == FrButtonEmphasis.Primary ? -5f : -3f,
                emphasis == FrButtonEmphasis.Primary ? 0.16f : 0.1f);

            if (emphasis == FrButtonEmphasis.Secondary)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.5f);
                outline.effectDistance = new Vector2(1.5f, -1.5f);
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
            colors.fadeDuration = 0.08f;
            colors.normalColor = Color.white;
            colors.selectedColor = Color.white;
            colors.disabledColor = new Color(0.75f, 0.75f, 0.75f, 0.5f);
            if (emphasis == FrButtonEmphasis.Primary)
            {
                colors.highlightedColor = new Color(1f, 0.96f, 0.98f, 1f);
                colors.pressedColor = new Color(0.88f, 0.82f, 0.86f, 1f);
            }
            else if (emphasis == FrButtonEmphasis.Destructive)
            {
                colors.highlightedColor = new Color(0.98f, 0.94f, 0.94f, 1f);
                colors.pressedColor = new Color(0.92f, 0.86f, 0.86f, 1f);
            }
            else
            {
                colors.highlightedColor = new Color(0.99f, 0.99f, 0.99f, 1f);
                colors.pressedColor = new Color(0.92f, 0.9f, 0.9f, 1f);
            }

            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            var le = go.AddComponent<LayoutElement>();
            var h = emphasis == FrButtonEmphasis.Primary
                ? (DeviceLayoutPolicy.IsTabletLike() ? 72f : 64f)
                : (DeviceLayoutPolicy.IsTabletLike() ? 58f : 52f);
            le.minHeight = h;
            le.preferredHeight = h;
            le.flexibleWidth = 1f;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, h);

            var txtGo = new GameObject("Text", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = DefaultUiFont;
            txt.text = label;
            txt.fontSize = Mathf.RoundToInt(emphasis == FrButtonEmphasis.Primary
                ? theme.SubtitleSize
                : theme.BodySize);
            txt.fontStyle = emphasis == FrButtonEmphasis.Primary ? FontStyle.Bold : FontStyle.Normal;
            txt.color = txtColor;
            txt.alignment = TextAnchor.MiddleCenter;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(16f, 0f);
            trt.offsetMax = new Vector2(-16f, 0f);

            if (emphasis == FrButtonEmphasis.Primary)
            {
                var motion = go.AddComponent<FrUiMotion>();
                motion.EnablePulse(true);
                WirePressMotion(btn, motion);
            }

            return btn;
        }

        /// <summary>Soft frosted stage behind a look / sketch preview.</summary>
        public static RectTransform AddStageFrame(Transform parent, string name, FashionRiseTheme theme,
            float minHeight, float preferredHeight)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.sprite = WhiteSprite;
            img.color = theme.Stage;
            AddSoftShadow(go, -8f, 0.12f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(theme.Champagne.r, theme.Champagne.g, theme.Champagne.b, 0.55f);
            outline.effectDistance = new Vector2(2f, -2f);
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = minHeight;
            le.preferredHeight = preferredHeight;
            le.flexibleWidth = 1f;
            le.flexibleHeight = 0f;
            return go.GetComponent<RectTransform>();
        }

        public static RectTransform AddHorizontalRow(Transform parent, string name, float spacing)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(HorizontalLayoutGroup), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 220f;
            le.preferredHeight = 250f;
            le.flexibleWidth = 1f;
            var h = go.GetComponent<HorizontalLayoutGroup>();
            h.spacing = spacing;
            h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true;
            h.childForceExpandWidth = true;
            h.childControlHeight = true;
            h.childForceExpandHeight = true;
            return go.GetComponent<RectTransform>();
        }

        static void WirePressMotion(Button btn, FrUiMotion motion)
        {
            var trigger = btn.gameObject.GetComponent<EventTrigger>() ?? btn.gameObject.AddComponent<EventTrigger>();
            void Add(EventTriggerType type, UnityAction<BaseEventData> cb)
            {
                var entry = new EventTrigger.Entry { eventID = type };
                entry.callback.AddListener(cb);
                trigger.triggers.Add(entry);
            }

            Add(EventTriggerType.PointerDown, _ => motion.SetPressed(true));
            Add(EventTriggerType.PointerUp, _ => motion.SetPressed(false));
            Add(EventTriggerType.PointerExit, _ => motion.SetPressed(false));
        }

        static void AddSoftShadow(GameObject go, float offsetY, float alpha)
        {
            var s = go.AddComponent<Shadow>();
            s.effectColor = new Color(0.25f, 0.12f, 0.18f, alpha);
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
            var pad = Mathf.Max(DeviceLayoutPolicy.ContentPadding, 22f);
            rt.offsetMin = new Vector2(pad, pad);
            rt.offsetMax = new Vector2(-pad, -pad);
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
            img.sprite = WhiteSprite;
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
            if (string.Equals(placeholder, "password", System.StringComparison.OrdinalIgnoreCase))
                input.contentType = InputField.ContentType.Password;

            return input;
        }

        public static Toggle AddCheckbox(Transform parent, string name, string label, FashionRiseTheme theme,
            bool isOn)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(HorizontalLayoutGroup), typeof(Toggle));
            go.transform.SetParent(parent, false);
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = DeviceLayoutPolicy.IsTabletLike() ? 44f : 40f;
            le.flexibleWidth = 1f;
            var h = go.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 12f;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlHeight = true;
            h.childForceExpandHeight = false;
            h.childControlWidth = true;
            h.childForceExpandWidth = false;
            h.padding = new RectOffset(4, 4, 0, 0);

            var boxGo = new GameObject("Box", typeof(Image));
            boxGo.transform.SetParent(go.transform, false);
            var boxImg = boxGo.GetComponent<Image>();
            boxImg.sprite = WhiteSprite;
            boxImg.color = theme.Card;
            var boxOutline = boxGo.AddComponent<Outline>();
            boxOutline.effectColor = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b, 0.45f);
            boxOutline.effectDistance = new Vector2(1f, -1f);
            var boxLe = boxGo.AddComponent<LayoutElement>();
            boxLe.minWidth = 28f;
            boxLe.preferredWidth = 28f;
            boxLe.minHeight = 28f;
            boxLe.preferredHeight = 28f;

            var checkGo = new GameObject("Checkmark", typeof(Image));
            checkGo.transform.SetParent(boxGo.transform, false);
            var checkImg = checkGo.GetComponent<Image>();
            checkImg.sprite = WhiteSprite;
            checkImg.color = theme.Accent;
            checkImg.raycastTarget = false;
            var checkRt = checkGo.GetComponent<RectTransform>();
            checkRt.anchorMin = new Vector2(0.2f, 0.2f);
            checkRt.anchorMax = new Vector2(0.8f, 0.8f);
            checkRt.offsetMin = Vector2.zero;
            checkRt.offsetMax = Vector2.zero;

            var labelGo = new GameObject("Label", typeof(Text));
            labelGo.transform.SetParent(go.transform, false);
            var txt = labelGo.GetComponent<Text>();
            txt.font = DefaultUiFont;
            txt.text = label;
            txt.fontSize = Mathf.RoundToInt(theme.BodySize);
            txt.color = theme.PrimaryText;
            txt.alignment = TextAnchor.MiddleLeft;
            var labelLe = labelGo.AddComponent<LayoutElement>();
            labelLe.flexibleWidth = 1f;
            labelLe.minHeight = 28f;

            var toggle = go.GetComponent<Toggle>();
            toggle.targetGraphic = boxImg;
            toggle.graphic = checkImg;
            toggle.isOn = isOn;
            return toggle;
        }

        static Sprite VerticalGradientSprite(Color top, Color bottom)
        {
            if (s_vGradTex == null)
            {
                s_vGradTex = new Texture2D(2, 64, TextureFormat.RGBA32, false)
                {
                    wrapMode = TextureWrapMode.Clamp,
                    filterMode = FilterMode.Bilinear
                };
            }

            if (s_vGradSprite != null && s_vGradTop == top && s_vGradBottom == bottom)
                return s_vGradSprite;

            for (var y = 0; y < s_vGradTex.height; y++)
            {
                var t = y / (float)(s_vGradTex.height - 1);
                var c = Color.Lerp(bottom, top, t);
                s_vGradTex.SetPixel(0, y, c);
                s_vGradTex.SetPixel(1, y, c);
            }

            s_vGradTex.Apply(false, false);
            s_vGradTop = top;
            s_vGradBottom = bottom;
            s_vGradSprite = Sprite.Create(s_vGradTex, new Rect(0, 0, s_vGradTex.width, s_vGradTex.height),
                new Vector2(0.5f, 0.5f), 100f);
            return s_vGradSprite;
        }

        static Sprite SoftBlobSprite()
        {
            if (s_softBlobSprite != null)
                return s_softBlobSprite;

            if (s_softBlobTex == null)
            {
                const int n = 64;
                s_softBlobTex = new Texture2D(n, n, TextureFormat.RGBA32, false)
                {
                    wrapMode = TextureWrapMode.Clamp,
                    filterMode = FilterMode.Bilinear
                };
                var mid = (n - 1) * 0.5f;
                for (var y = 0; y < n; y++)
                for (var x = 0; x < n; x++)
                {
                    var dx = (x - mid) / mid;
                    var dy = (y - mid) / mid;
                    var d = Mathf.Sqrt(dx * dx + dy * dy);
                    var a = Mathf.Clamp01(1f - d);
                    a = a * a * (3f - 2f * a);
                    s_softBlobTex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }

                s_softBlobTex.Apply(false, false);
            }

            s_softBlobSprite = Sprite.Create(s_softBlobTex, new Rect(0, 0, s_softBlobTex.width, s_softBlobTex.height),
                new Vector2(0.5f, 0.5f), 100f);
            return s_softBlobSprite;
        }
    }
}
