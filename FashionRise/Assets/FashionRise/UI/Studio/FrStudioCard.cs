using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioCard : MonoBehaviour
    {
        Image _face = null!;
        Image _ring = null!;
        Graphic? _title;
        bool _selected;
        FashionRiseTheme _theme = null!;
        Color _idleFace;

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

        public static FrStudioCard Build(Transform parent, FashionRiseTheme theme, string title, UnityAction onClick,
            Texture2D? portrait = null, FrStudioIconKind? placeholderIcon = null)
        {
            var go = new GameObject(title + "_Card", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioCard));
            go.transform.SetParent(parent, false);
            var card = go.GetComponent<FrStudioCard>();
            card._theme = theme;
            card._idleFace = theme.ShellElevated;
            card._face = go.GetComponent<Image>();
            card._face.sprite = FrStudioSprites.Rounded(72, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            card._face.type = Image.Type.Sliced;
            card._face.color = card._idleFace;

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.95f);
            colors.pressedColor = new Color(0.86f, 0.86f, 0.88f, 1f);
            colors.selectedColor = Color.white;
            colors.disabledColor = theme.Disabled;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            card.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            le.minHeight = DeviceLayoutPolicy.IsWideLayout() ? 148f : 118f;
            le.preferredHeight = le.minHeight;
            le.flexibleWidth = 1f;
            le.flexibleHeight = DeviceLayoutPolicy.IsWideLayout() ? 1f : 0f;

            var ringGo = new GameObject("Ring", typeof(RectTransform), typeof(Image));
            ringGo.transform.SetParent(go.transform, false);
            var ringRt = ringGo.GetComponent<RectTransform>();
            ringRt.anchorMin = Vector2.zero;
            ringRt.anchorMax = Vector2.one;
            ringRt.offsetMin = Vector2.zero;
            ringRt.offsetMax = Vector2.zero;
            card._ring = ringGo.GetComponent<Image>();
            card._ring.sprite = FrStudioSprites.Rounded(72, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            card._ring.type = Image.Type.Sliced;
            card._ring.raycastTarget = false;

            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, 0.28f);
            shadow.effectDistance = new Vector2(0f, -4f);

            var col = new GameObject("Col", typeof(RectTransform), typeof(VerticalLayoutGroup));
            col.transform.SetParent(go.transform, false);
            var colRt = col.GetComponent<RectTransform>();
            colRt.anchorMin = Vector2.zero;
            colRt.anchorMax = Vector2.one;
            colRt.offsetMin = new Vector2(10f, 10f);
            colRt.offsetMax = new Vector2(-10f, -10f);
            var v = col.GetComponent<VerticalLayoutGroup>();
            v.spacing = 8f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var preview = new GameObject("Preview", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            preview.transform.SetParent(col.transform, false);
            var previewFace = preview.GetComponent<Image>();
            previewFace.sprite = FrStudioSprites.Rounded(64, 12, Color.white);
            previewFace.type = Image.Type.Sliced;
            previewFace.color = new Color(theme.ShellBackground.r, theme.ShellBackground.g, theme.ShellBackground.b, 0.85f);
            previewFace.raycastTarget = false;
            var previewLe = preview.GetComponent<LayoutElement>();
            previewLe.minHeight = DeviceLayoutPolicy.IsWideLayout() ? 96f : 72f;
            previewLe.preferredHeight = previewLe.minHeight;
            previewLe.flexibleWidth = 1f;

            if (portrait != null)
            {
                var thumb = new GameObject("Portrait", typeof(RawImage));
                thumb.transform.SetParent(preview.transform, false);
                var raw = thumb.GetComponent<RawImage>();
                raw.texture = portrait;
                raw.raycastTarget = false;
                var trt = thumb.GetComponent<RectTransform>();
                trt.anchorMin = Vector2.zero;
                trt.anchorMax = Vector2.one;
                trt.offsetMin = new Vector2(8f, 6f);
                trt.offsetMax = new Vector2(-8f, -6f);
            }
            else
            {
                var iconKind = placeholderIcon ?? FrStudioIconKind.Import;
                var mark = new GameObject("Mark", typeof(Image));
                mark.transform.SetParent(preview.transform, false);
                var img = mark.GetComponent<Image>();
                img.sprite = FrStudioSprites.Icon(iconKind, theme.AccentMuted);
                img.preserveAspect = true;
                img.raycastTarget = false;
                var mrt = mark.GetComponent<RectTransform>();
                mrt.anchorMin = new Vector2(0.5f, 0.5f);
                mrt.anchorMax = new Vector2(0.5f, 0.5f);
                mrt.sizeDelta = new Vector2(36f, 36f);
            }

            var titleHost = new GameObject("TitleHost", typeof(RectTransform), typeof(LayoutElement));
            titleHost.transform.SetParent(col.transform, false);
            titleHost.GetComponent<LayoutElement>().minHeight = 22f;
            card._title = FrStudioTypography.AddLabel(titleHost.transform, "Title", title, theme,
                FrStudioTypeStyle.SectionHeading, muted: false, TextAnchor.MiddleCenter, FrStudioTypeTone.OnDark);

            card.Refresh();
            return card;
        }

        void Refresh()
        {
            if (_face == null || _theme == null)
                return;
            _face.color = _selected
                ? Color.Lerp(_idleFace, _theme.Selected, 0.12f)
                : _idleFace;
            // Rose border only — never flood the whole card with solid pink.
            _ring.color = _selected ? _theme.Selected : new Color(_theme.SubtleBorder.r, _theme.SubtleBorder.g,
                _theme.SubtleBorder.b, 0.35f);
            if (_title != null)
                FrStudioTypography.SetColor(_title, _selected ? _theme.ShellText : _theme.ShellMutedText);
        }
    }
}
