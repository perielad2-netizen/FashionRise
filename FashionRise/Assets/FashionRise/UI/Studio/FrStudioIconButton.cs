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
        Image? _ring;
        Image _icon = null!;
        Graphic? _caption;
        LayoutElement? _captionHost;
        FashionRiseTheme _theme = null!;
        bool _selected;
        bool _light;
        bool _swatch;
        bool _modeTool;
        bool _captionsVisible = true;
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
            string caption, UnityAction onClick, bool light = false, bool modeTool = false)
        {
            var go = new GameObject((string.IsNullOrEmpty(caption) ? kind.ToString() : caption) + "_IconBtn",
                typeof(RectTransform), typeof(Image), typeof(Button), typeof(FrStudioIconButton));
            go.transform.SetParent(parent, false);
            var widget = go.GetComponent<FrStudioIconButton>();
            widget._theme = theme;
            widget._light = light;
            widget._modeTool = modeTool;
            widget._face = go.GetComponent<Image>();
            widget._face.sprite = FrStudioSprites.Rounded(64, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            widget._face.type = Image.Type.Sliced;

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.94f);
            colors.pressedColor = new Color(0.84f, 0.84f, 0.86f, 1f);
            colors.selectedColor = Color.white;
            colors.disabledColor = theme.Disabled;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            widget.Button = btn;

            var touch = Mathf.Max(theme.MinTouchTarget, DeviceLayoutPolicy.StudioMinTouch);
            var le = go.AddComponent<LayoutElement>();
            le.minWidth = touch;
            le.minHeight = touch;
            le.preferredWidth = touch + 4f;
            le.preferredHeight = touch + 4f;
            le.flexibleWidth = 0f;

            var ringGo = new GameObject("Ring", typeof(RectTransform), typeof(Image));
            ringGo.transform.SetParent(go.transform, false);
            var ringRt = ringGo.GetComponent<RectTransform>();
            ringRt.anchorMin = Vector2.zero;
            ringRt.anchorMax = Vector2.one;
            ringRt.offsetMin = Vector2.zero;
            ringRt.offsetMax = Vector2.zero;
            widget._ring = ringGo.GetComponent<Image>();
            widget._ring.sprite = FrStudioSprites.Rounded(64, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            widget._ring.type = Image.Type.Sliced;
            widget._ring.raycastTarget = false;

            var col = new GameObject("Stack", typeof(RectTransform), typeof(VerticalLayoutGroup));
            col.transform.SetParent(go.transform, false);
            var colRt = col.GetComponent<RectTransform>();
            colRt.anchorMin = Vector2.zero;
            colRt.anchorMax = Vector2.one;
            colRt.offsetMin = new Vector2(6f, 6f);
            colRt.offsetMax = new Vector2(-6f, -6f);
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
            widget._icon.sprite = FrStudioSprites.Icon(kind, Color.white);
            widget._icon.color = widget._iconIdle;
            widget._icon.preserveAspect = true;
            widget._icon.raycastTarget = false;
            var ile = iconGo.GetComponent<LayoutElement>();
            ile.preferredWidth = theme.IconSize + 4f;
            ile.preferredHeight = theme.IconSize + 4f;

            if (!string.IsNullOrEmpty(caption))
            {
                var capHost = new GameObject("CapHost", typeof(RectTransform), typeof(LayoutElement));
                capHost.transform.SetParent(col.transform, false);
                widget._captionHost = capHost.GetComponent<LayoutElement>();
                widget._captionHost.minHeight = 14f;
                widget._captionHost.preferredHeight = 14f;
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
            widget._face.sprite = FrStudioSprites.Rounded(64, 18, Color.white);
            widget._face.type = Image.Type.Sliced;

            var outline = go.AddComponent<Outline>();
            outline.effectColor = theme.LightBorder;
            outline.effectDistance = new Vector2(1f, -1f);

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
            le.minHeight = Mathf.Max(theme.MinTouchTarget, 46f);
            le.minWidth = 64f;
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
            widget._face.sprite = FrStudioSprites.Circle(64, Color.white);
            widget._face.color = ink;

            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, 0.18f);
            shadow.effectDistance = new Vector2(0f, -2f);

            var btn = go.GetComponent<Button>();
            btn.onClick.AddListener(onClick);
            widget.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            le.minWidth = 52f;
            le.minHeight = 52f;
            le.preferredWidth = 56f;
            le.preferredHeight = 56f;

            var ring = new GameObject("Sel", typeof(Image));
            ring.transform.SetParent(go.transform, false);
            var ringRt = ring.GetComponent<RectTransform>();
            ringRt.anchorMin = Vector2.zero;
            ringRt.anchorMax = Vector2.one;
            ringRt.offsetMin = new Vector2(-5f, -5f);
            ringRt.offsetMax = new Vector2(5f, 5f);
            widget._icon = ring.GetComponent<Image>();
            widget._icon.sprite = FrStudioSprites.Circle(72, Color.white);
            widget._icon.raycastTarget = false;
            widget.Refresh();
            return widget;
        }

        public void SetCaptionsVisible(bool visible)
        {
            _captionsVisible = visible;
            if (_captionHost != null)
                _captionHost.gameObject.SetActive(visible);
            else
                FrStudioTypography.SetVisible(_caption, visible);

            var le = GetComponent<LayoutElement>();
            if (le != null)
            {
                var touch = Mathf.Max(_theme.MinTouchTarget, DeviceLayoutPolicy.StudioMinTouch);
                le.minHeight = visible && _caption != null ? touch + 16f : touch;
                le.preferredHeight = le.minHeight;
            }
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
                _face.color = _selected ? Color.Lerp(_theme.CanvasCard, _theme.Selected, 0.16f) : _theme.CanvasCard;
                if (_caption != null)
                    FrStudioTypography.SetColor(_caption, _selected ? _theme.MidnightNavy : _theme.ButtonText);
                if (_icon != null && !_swatch)
                    _icon.color = _selected ? _theme.Selected : _iconIdle;
                if (_ring != null)
                    _ring.color = _selected ? _theme.Selected : new Color(0f, 0f, 0f, 0f);
                return;
            }

            if (_modeTool && _selected)
            {
                _face.color = Color.Lerp(_theme.ShellElevated, _theme.Selected, 0.22f);
                if (_ring != null)
                    _ring.color = _theme.Selected;
                if (_icon != null)
                    _icon.color = _theme.ShellText;
                if (_caption != null)
                    FrStudioTypography.SetColor(_caption, _theme.ShellText);
            }
            else
            {
                _face.color = _theme.ShellElevated;
                if (_ring != null)
                    _ring.color = new Color(0f, 0f, 0f, 0f);
                if (_icon != null)
                    _icon.color = _iconIdle;
                if (_caption != null)
                    FrStudioTypography.SetColor(_caption,
                        _captionsVisible ? _theme.ShellMutedText : _theme.ShellMutedText);
            }
        }
    }
}
