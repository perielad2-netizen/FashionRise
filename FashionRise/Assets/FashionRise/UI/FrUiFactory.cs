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

        static Sprite? s_whiteSprite;
        static Texture2D? s_vGradTex;
        static Sprite? s_vGradSprite;
        static Color s_vGradTop;
        static Color s_vGradBottom;
        static Texture2D? s_softBlobTex;
        static Sprite? s_softBlobSprite;

        static Font DefaultUiFont => FrUiFonts.Ui;

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

        /// <summary>Full-bleed ivory atelier atmosphere — soft parchment wash, champagne light.</summary>
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

            AddAtmosphereBlob(rt, theme.Champagne, new Vector2(0.14f, 0.82f), 0.5f, 0.14f);
            AddAtmosphereBlob(rt, theme.AccentMuted, new Vector2(0.9f, 0.22f), 0.42f, 0.1f);
            AddAtmosphereBlob(rt, theme.Background, new Vector2(0.5f, 0.05f), 0.95f, 0.2f);
            FrScreenReveal.Attach(go);
            return rt;
        }

        /// <summary>Editorial display title (Cormorant) or UI label (DM Sans).</summary>
        public static Text AddEditorialLabel(Transform parent, string name, string text, FashionRiseTheme theme,
            int fontSize, bool editorial, TextAnchor anchor = TextAnchor.UpperLeft,
            bool useSecondaryTextColor = false)
        {
            var go = new GameObject(name, typeof(Text));
            go.transform.SetParent(parent, false);
            var t = go.GetComponent<Text>();
            t.font = editorial ? FrUiFonts.DisplayBold : FrUiFonts.Ui;
            t.text = text;
            t.fontSize = fontSize;
            t.fontStyle = FontStyle.Normal;
            t.color = useSecondaryTextColor ? theme.SecondaryText : theme.PrimaryText;
            t.alignment = anchor;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = fontSize + (editorial ? 22f : 14f);
            le.preferredHeight = fontSize + (editorial ? 32f : 22f);
            le.flexibleWidth = 1f;
            return t;
        }

        public static Text AddOverline(Transform parent, string name, string text, FashionRiseTheme theme)
        {
            var t = AddEditorialLabel(parent, name, text.ToUpperInvariant(), theme,
                Mathf.RoundToInt(theme.OverlineSize), false, TextAnchor.MiddleCenter, true);
            t.font = FrUiFonts.UiMedium;
            var le = t.GetComponent<LayoutElement>();
            le.minHeight = 18f;
            le.preferredHeight = 20f;
            return t;
        }

        /// <summary>Floating ivory panel with hairline edge — for toolbars / sheets.</summary>
        public static RectTransform AddFloatingPanel(Transform parent, string name, FashionRiseTheme theme,
            float minHeight = 0f)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.sprite = FrUiSprites.RoundSoft;
            img.type = Image.Type.Sliced;
            img.color = theme.Panel;
            AddSoftShadow(go, -6f, 0.1f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = theme.Hairline;
            outline.effectDistance = new Vector2(1f, -1f);
            var le = go.GetComponent<LayoutElement>();
            if (minHeight > 0f)
            {
                le.minHeight = minHeight;
                le.preferredHeight = minHeight;
            }

            le.flexibleWidth = 1f;
            return go.GetComponent<RectTransform>();
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
            var editorial = fontSize >= theme.TitleSize - 1f;
            t.font = FrUiFonts.ForStyle(editorial, style);
            t.text = text;
            t.fontSize = fontSize;
            // Weight lives in the font file; keep Normal to avoid faux-bold on custom faces.
            t.fontStyle = FontStyle.Normal;
            t.color = useSecondaryTextColor ? theme.SecondaryText : theme.PrimaryText;
            t.alignment = anchor;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = fontSize + (editorial ? 20f : 14f);
            le.preferredHeight = fontSize + (editorial ? 28f : 22f);
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

        /// <summary>Visual-first Women/Men choice — croquis stage, label under image (never overlaid).</summary>
        public static Button AddModelChoiceTile(Transform parent, string name, string label, string resourcePath,
            FashionRiseTheme theme, UnityAction onClick, bool tall = false)
        {
            var go = new GameObject(name + "_Tile", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.RoundSoft;
            face.type = Image.Type.Sliced;
            face.color = theme.Card;
            AddSoftShadow(go, -8f, 0.12f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = theme.Hairline;
            outline.effectDistance = new Vector2(1f, -1f);

            var le = go.GetComponent<LayoutElement>();
            le.minHeight = tall ? 420f : 210f;
            le.preferredHeight = tall ? 560f : 240f;
            le.flexibleWidth = 1f;
            le.flexibleHeight = tall ? 1f : 0f;

            var v = go.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(14, 14, 16, 16);
            v.spacing = 10f;
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
            previewLe.minHeight = tall ? 340f : 150f;
            previewLe.preferredHeight = tall ? 460f : 170f;
            previewLe.flexibleHeight = 1f;
            var fitter = previewGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
            if (sprite != null && sprite.rect.height > 0)
                fitter.aspectRatio = sprite.rect.width / sprite.rect.height;
            else if (tex != null && tex.height > 0)
                fitter.aspectRatio = tex.width / (float)tex.height;
            else
                fitter.aspectRatio = 0.7f;

            var caption = AddEditorialLabel(go.transform, "Cap", label, theme,
                Mathf.RoundToInt(theme.SubtitleSize + 2f), true, TextAnchor.MiddleCenter);
            caption.font = FrUiFonts.DisplayMedium;
            caption.color = theme.Charcoal;
            var capLe = caption.GetComponent<LayoutElement>();
            capLe.minHeight = 28f;
            capLe.preferredHeight = 32f;
            capLe.flexibleHeight = 0f;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 0.99f, 0.97f, 1f);
            colors.pressedColor = new Color(0.94f, 0.92f, 0.9f, 1f);
            colors.selectedColor = Color.white;
            colors.fadeDuration = 0.12f;
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
            var isAi = emphasis == FrButtonEmphasis.AiAction;
            var isPrimary = emphasis == FrButtonEmphasis.Primary || isAi;
            switch (emphasis)
            {
                case FrButtonEmphasis.Primary:
                    face = theme.Accent;
                    txtColor = theme.ButtonPrimaryText;
                    break;
                case FrButtonEmphasis.AiAction:
                    face = theme.ButtonAiFace;
                    txtColor = theme.Champagne;
                    break;
                case FrButtonEmphasis.Destructive:
                    face = theme.ButtonFace;
                    txtColor = theme.Danger;
                    break;
                case FrButtonEmphasis.Ghost:
                    face = new Color(1f, 1f, 1f, 0.01f);
                    txtColor = theme.SecondaryText;
                    break;
                default:
                    face = theme.ButtonFace;
                    txtColor = theme.ButtonText;
                    break;
            }

            img.sprite = FrUiSprites.RoundSoft;
            img.type = Image.Type.Sliced;
            img.color = face;
            if (emphasis != FrButtonEmphasis.Ghost)
                AddSoftShadow(go, isPrimary ? -5f : -3f, isPrimary ? 0.14f : 0.08f);

            if (emphasis == FrButtonEmphasis.Secondary)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = theme.Hairline;
                outline.effectDistance = new Vector2(1f, -1f);
            }
            else if (emphasis == FrButtonEmphasis.Destructive)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = new Color(theme.Danger.r, theme.Danger.g, theme.Danger.b, 0.35f);
                outline.effectDistance = new Vector2(1f, -1f);
            }
            else if (isAi)
            {
                var outline = go.AddComponent<Outline>();
                outline.effectColor = new Color(theme.Champagne.r, theme.Champagne.g, theme.Champagne.b, 0.45f);
                outline.effectDistance = new Vector2(1.5f, -1.5f);
            }

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.colorMultiplier = 1f;
            colors.fadeDuration = 0.12f;
            colors.normalColor = Color.white;
            colors.selectedColor = Color.white;
            colors.disabledColor = new Color(0.75f, 0.75f, 0.75f, 0.45f);
            colors.highlightedColor = new Color(1f, 0.99f, 0.97f, 1f);
            colors.pressedColor = new Color(0.92f, 0.9f, 0.88f, 1f);
            if (isAi)
            {
                colors.highlightedColor = new Color(1.08f, 1.05f, 1f, 1f);
                colors.pressedColor = new Color(0.85f, 0.85f, 0.85f, 1f);
            }

            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            var le = go.AddComponent<LayoutElement>();
            var h = isPrimary
                ? (DeviceLayoutPolicy.IsTabletLike() ? 64f : 56f)
                : (DeviceLayoutPolicy.IsTabletLike() ? 52f : 46f);
            if (emphasis == FrButtonEmphasis.Ghost)
                h = DeviceLayoutPolicy.IsTabletLike() ? 40f : 36f;
            le.minHeight = h;
            le.preferredHeight = h;
            le.flexibleWidth = 1f;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0, h);

            // Soft highlight sweep for AI / primary
            if (isPrimary)
            {
                var sweep = new GameObject("Sweep", typeof(RectTransform), typeof(Image));
                sweep.transform.SetParent(go.transform, false);
                var srt = sweep.GetComponent<RectTransform>();
                srt.anchorMin = new Vector2(0f, 0f);
                srt.anchorMax = new Vector2(0.35f, 1f);
                srt.offsetMin = Vector2.zero;
                srt.offsetMax = Vector2.zero;
                var simg = sweep.GetComponent<Image>();
                simg.sprite = WhiteSprite;
                simg.color = new Color(1f, 1f, 1f, isAi ? 0.08f : 0.12f);
                simg.raycastTarget = false;
                var sweepMotion = sweep.AddComponent<FrUiMotion>();
                sweepMotion.EnableFloat(true, 0f);
            }

            var txtGo = new GameObject("Text", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = isPrimary ? FrUiFonts.UiMedium : FrUiFonts.Ui;
            txt.text = label;
            txt.fontSize = Mathf.RoundToInt(isPrimary ? theme.SubtitleSize : theme.BodySize);
            txt.fontStyle = FontStyle.Normal;
            txt.color = txtColor;
            txt.alignment = TextAnchor.MiddleCenter;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(18f, 0f);
            trt.offsetMax = new Vector2(-18f, 0f);

            var motion = go.AddComponent<FrUiMotion>();
            if (isAi)
                motion.EnablePulse(true);
            WirePressMotion(btn, motion);

            return btn;
        }

        /// <summary>Compact circular tool button with icon sprite.</summary>
        public static Button AddIconButton(Transform parent, string name, Sprite icon, FashionRiseTheme theme,
            UnityAction onClick, float size = 48f)
        {
            var go = new GameObject(name + "_IconBtn", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.Circle;
            face.color = theme.Card;
            AddSoftShadow(go, -3f, 0.1f);
            var le = go.GetComponent<LayoutElement>();
            le.minWidth = size;
            le.preferredWidth = size;
            le.minHeight = size;
            le.preferredHeight = size;
            le.flexibleWidth = 0f;

            var iconGo = new GameObject("Icon", typeof(Image));
            iconGo.transform.SetParent(go.transform, false);
            var iconImg = iconGo.GetComponent<Image>();
            iconImg.sprite = icon;
            iconImg.preserveAspect = true;
            iconImg.raycastTarget = false;
            iconImg.color = theme.PrimaryText;
            var irt = iconGo.GetComponent<RectTransform>();
            irt.anchorMin = new Vector2(0.22f, 0.22f);
            irt.anchorMax = new Vector2(0.78f, 0.78f);
            irt.offsetMin = Vector2.zero;
            irt.offsetMax = Vector2.zero;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            var motion = go.AddComponent<FrUiMotion>();
            WirePressMotion(btn, motion);
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
            Add(EventTriggerType.PointerEnter, _ => motion.SetHovered(true));
            Add(EventTriggerType.PointerExit, _ =>
            {
                motion.SetPressed(false);
                motion.SetHovered(false);
            });
        }

        static void AddSoftShadow(GameObject go, float offsetY, float alpha)
        {
            var s = go.AddComponent<Shadow>();
            s.effectColor = new Color(0.08f, 0.07f, 0.06f, alpha);
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
            text.font = FrUiFonts.Ui;
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
            ph.font = FrUiFonts.Ui;
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
            txt.font = FrUiFonts.Ui;
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
