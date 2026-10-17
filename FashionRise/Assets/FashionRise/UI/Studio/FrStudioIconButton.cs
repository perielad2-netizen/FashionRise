using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioIconButton : MonoBehaviour
    {
        Image _face = null!;
        Image _icon = null!;
        Graphic? _caption;
        FashionRiseTheme _theme = null!;
        bool _selected;
        bool _light;
        bool _swatch;
        Color _iconIdle;

        public Button Button { get; private set; } = null!;

        public bool Selected
        {
            get => _selected;
            set
            {
                _selected = value;
                Refresh();
            }
        }

        public static FrStudioIconButton Build(Transform parent, FashionRiseTheme theme, FrStudioIconKind kind,
            string caption, UnityAction onClick, bool light = false)
        {
            var go = new GameObject(caption + "_IconBtn", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioIconButton));
            go.transform.SetParent(parent, false);
            var widget = go.GetComponent<FrStudioIconButton>();
            widget._theme = theme;
            widget._light = light;
            widget._face = go.GetComponent<Image>();
            widget._face.sprite = FrStudioSprites.Rounded(48, Mathf.RoundToInt(theme.CornerRadiusSmall), Color.white);
            widget._face.type = Image.Type.Sliced;

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.92f);
            colors.pressedColor = new Color(0.82f, 0.82f, 0.84f, 1f);
            colors.selectedColor = Color.white;
            colors.disabledColor = theme.Disabled;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            widget.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            var touch = Mathf.Max(theme.MinTouchTarget, DeviceLayoutPolicy.StudioMinTouch);
            le.minWidth = touch;
            le.minHeight = string.IsNullOrEmpty(caption) ? touch : touch + 18f;
            le.preferredWidth = touch + 8f;
            le.flexibleWidth = 0f;

            var col = new GameObject("Stack", typeof(RectTransform), typeof(VerticalLayoutGroup));
            col.transform.SetParent(go.transform, false);
            var colRt = col.GetComponent<RectTransform>();
            colRt.anchorMin = Vector2.zero;
            colRt.anchorMax = Vector2.one;
            colRt.offsetMin = new Vector2(4f, 4f);
            colRt.offsetMax = new Vector2(-4f, -4f);
            var v = col.GetComponent<VerticalLayoutGroup>();
            v.spacing = 2f;
            v.childAlignment = TextAnchor.MiddleCenter;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = false;
            v.childForceExpandHeight = false;

            var iconGo = new GameObject("Icon", typeof(Image), typeof(LayoutElement));
            iconGo.transform.SetParent(col.transform, false);
            widget._icon = iconGo.GetComponent<Image>();
            widget._iconIdle = light ? theme.MidnightNavy : theme.ShellText;
            widget._icon.sprite = FrStudioSprites.Icon(kind, widget._iconIdle);
            widget._icon.preserveAspect = true;
            widget._icon.raycastTarget = false;
            var ile = iconGo.GetComponent<LayoutElement>();
            ile.preferredWidth = theme.IconSize + 6f;
            ile.preferredHeight = theme.IconSize + 6f;

            if (!string.IsNullOrEmpty(caption))
            {
                var capHost = new GameObject("CapHost", typeof(RectTransform), typeof(LayoutElement));
                capHost.transform.SetParent(col.transform, false);
                capHost.GetComponent<LayoutElement>().minHeight = 16f;
                widget._caption = FrStudioTypography.AddLabel(capHost.transform, "Cap", caption, theme,
                    FrStudioTypeStyle.Caption, muted: true, TextAnchor.MiddleCenter,
                    light ? FrStudioTypeTone.OnLight : FrStudioTypeTone.OnDark);
            }

            widget.Refresh();
            return widget;
        }

        public static FrStudioIconButton Chip(Transform parent, FashionRiseTheme theme, string label,
            UnityAction onClick, bool light = true)
        {
            var go = new GameObject(label + "_Chip", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioIconButton));
            go.transform.SetParent(parent, false);
            var widget = go.GetComponent<FrStudioIconButton>();
            widget._theme = theme;
            widget._light = light;
            widget._face = go.GetComponent<Image>();
            widget._face.sprite = FrStudioSprites.Rounded(48, 18, Color.white);
            widget._face.type = Image.Type.Sliced;

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.94f);
            colors.pressedColor = new Color(0.86f, 0.84f, 0.82f, 1f);
            colors.selectedColor = Color.white;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            widget.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            le.minHeight = Mathf.Max(theme.MinTouchTarget, 44f);
            le.minWidth = 72f;
            le.preferredWidth = 0f;
            le.flexibleWidth = 1f;

            var host = new GameObject("LabelHost", typeof(RectTransform));
            host.transform.SetParent(go.transform, false);
            var hrt = host.GetComponent<RectTransform>();
            hrt.anchorMin = Vector2.zero;
            hrt.anchorMax = Vector2.one;
            hrt.offsetMin = new Vector2(8f, 0f);
            hrt.offsetMax = new Vector2(-8f, 0f);
            widget._caption = FrStudioTypography.AddLabel(host.transform, "L", label, theme, FrStudioTypeStyle.Button,
                muted: false, TextAnchor.MiddleCenter,
                light ? FrStudioTypeTone.OnLight : FrStudioTypeTone.OnDark);
            widget.Refresh();
            return widget;
        }

        public static FrStudioIconButton Swatch(Transform parent, FashionRiseTheme theme, Color ink, UnityAction onClick)
        {
            var go = new GameObject("Swatch", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioIconButton));
            go.transform.SetParent(parent, false);
            var widget = go.GetComponent<FrStudioIconButton>();
            widget._theme = theme;
            widget._light = true;
            widget._swatch = true;
            widget._face = go.GetComponent<Image>();
            widget._face.sprite = FrStudioSprites.Circle(48, Color.white);
            widget._face.color = ink;

            var btn = go.GetComponent<Button>();
            btn.onClick.AddListener(onClick);
            widget.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            le.minWidth = 44f;
            le.minHeight = 44f;
            le.preferredWidth = 48f;
            le.preferredHeight = 48f;

            var ring = new GameObject("Sel", typeof(Image));
            ring.transform.SetParent(go.transform, false);
            var ringRt = ring.GetComponent<RectTransform>();
            ringRt.anchorMin = Vector2.zero;
            ringRt.anchorMax = Vector2.one;
            ringRt.offsetMin = new Vector2(-4f, -4f);
            ringRt.offsetMax = new Vector2(4f, 4f);
            widget._icon = ring.GetComponent<Image>();
            widget._icon.sprite = FrStudioSprites.Circle(56, Color.white);
            widget._icon.raycastTarget = false;
            widget.Refresh();
            return widget;
        }

        void Refresh()
        {
            if (_face == null || _theme == null)
                return;

            if (_swatch)
            {
                if (_icon != null)
                    _icon.color = _selected ? _theme.Selected : new Color(0f, 0f, 0f, 0f);
                return;
            }

            if (_light)
            {
                _face.color = _selected ? Color.Lerp(_theme.CanvasCard, _theme.Accent, 0.22f) : _theme.ButtonFace;
                if (_caption != null)
                    FrStudioTypography.SetColor(_caption, _selected ? _theme.MidnightNavy : _theme.ButtonText);
                if (_icon != null)
                    _icon.color = _selected ? _theme.Selected : _iconIdle;
            }
            else
            {
                _face.color = _selected ? Color.Lerp(_theme.ShellElevated, _theme.Accent, 0.28f) : _theme.ShellElevated;
                if (_caption != null)
                    FrStudioTypography.SetColor(_caption, _selected ? _theme.ShellText : _theme.ShellMutedText);
                if (_icon != null)
                    _icon.color = _selected ? _theme.ShellText : _iconIdle;
            }
        }
    }
}
