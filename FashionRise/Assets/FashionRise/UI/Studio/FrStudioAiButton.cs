using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioAiButton : MonoBehaviour
    {
        Button _button = null!;
        Image _face = null!;
        Graphic? _label;
        FashionRiseTheme _theme = null!;
        bool _busy;

        public Button Button => _button;

        public bool Busy
        {
            get => _busy;
            set
            {
                _busy = value;
                if (_button != null)
                    _button.interactable = !value;
                if (_label != null)
                    FrStudioTypography.SetText(_label, value ? "Working…" : "Magic");
                if (_face != null && _theme != null)
                    _face.color = value ? _theme.AiAccentPressed : _theme.AiAccent;
            }
        }

        public static FrStudioAiButton Build(Transform parent, FashionRiseTheme theme, UnityAction onClick,
            string label = "Magic")
        {
            var go = new GameObject("MagicCta", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioAiButton));
            go.transform.SetParent(parent, false);
            var widget = go.GetComponent<FrStudioAiButton>();
            widget._theme = theme;
            widget._face = go.GetComponent<Image>();
            widget._face.sprite = FrStudioSprites.Rounded(72, 24, Color.white);
            widget._face.type = Image.Type.Sliced;
            widget._face.color = theme.AiAccent;

            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(theme.AiAccent.r, theme.AiAccent.g, theme.AiAccent.b, 0.48f);
            shadow.effectDistance = new Vector2(0f, -6f);

            var glow = go.AddComponent<Outline>();
            glow.effectColor = new Color(theme.AiAccent.r, theme.AiAccent.g, theme.AiAccent.b, 0.35f);
            glow.effectDistance = new Vector2(2f, -2f);

            widget._button = go.GetComponent<Button>();
            widget._button.transition = Selectable.Transition.ColorTint;
            var colors = widget._button.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.96f);
            colors.pressedColor = new Color(0.78f, 0.78f, 0.8f, 1f);
            colors.disabledColor = theme.Disabled;
            colors.fadeDuration = 0.08f;
            widget._button.colors = colors;
            widget._button.onClick.AddListener(onClick);

            var le = go.AddComponent<LayoutElement>();
            le.minHeight = Mathf.Max(theme.MinTouchTarget + 24f, DeviceLayoutPolicy.IsTabletLike() ? 78f : 68f);
            le.preferredHeight = le.minHeight;
            le.flexibleWidth = 1f;

            var row = new GameObject("Row", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            row.transform.SetParent(go.transform, false);
            var rowRt = row.GetComponent<RectTransform>();
            rowRt.anchorMin = Vector2.zero;
            rowRt.anchorMax = Vector2.one;
            rowRt.offsetMin = new Vector2(18f, 0f);
            rowRt.offsetMax = new Vector2(-18f, 0f);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 12f;
            h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            h.childForceExpandHeight = false;

            var icon = new GameObject("Icon", typeof(Image), typeof(LayoutElement));
            icon.transform.SetParent(row.transform, false);
            var img = icon.GetComponent<Image>();
            // Style-board Magic CTA is hot-pink with a light sparkle — prefer white glyph over
            // the navy icon-sheet tile so the pink surface stays the hero.
            img.sprite = FrStudioSprites.Icon(FrStudioIconKind.Magic, Color.white);
            img.color = Color.white;
            img.preserveAspect = true;
            img.raycastTarget = false;
            var ile = icon.GetComponent<LayoutElement>();
            ile.preferredWidth = 28f;
            ile.preferredHeight = 28f;

            var labelHost = new GameObject("LabelHost", typeof(RectTransform), typeof(LayoutElement));
            labelHost.transform.SetParent(row.transform, false);
            labelHost.GetComponent<LayoutElement>().preferredWidth = 110f;
            widget._label = FrStudioTypography.AddLabel(labelHost.transform, "L", label, theme,
                FrStudioTypeStyle.Button, muted: false, TextAnchor.MiddleCenter);
            FrStudioTypography.SetColor(widget._label, theme.ButtonPrimaryText);
            return widget;
        }
    }
}
