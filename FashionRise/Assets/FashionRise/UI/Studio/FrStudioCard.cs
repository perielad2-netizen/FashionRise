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
            le.minHeight = DeviceLayoutPolicy.IsWideLayout() ? 196f : 136f;
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
            shadow.effectColor = new Color(0f, 0f, 0f, 0.3f);
            shadow.effectDistance = new Vector2(0f, -4f);

            var col = new GameObject("Col", typeof(RectTransform), typeof(VerticalLayoutGroup));
            col.transform.SetParent(go.transform, false);
            var colRt = col.GetComponent<RectTransform>();
            colRt.anchorMin = Vector2.zero;
            colRt.anchorMax = Vector2.one;
            colRt.offsetMin = new Vector2(12f, 12f);
            colRt.offsetMax = new Vector2(-12f, -12f);
            var v = col.GetComponent<VerticalLayoutGroup>();
            v.spacing = 10f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var preview = new GameObject("Preview", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            preview.transform.SetParent(col.transform, false);
            var previewFace = preview.GetComponent<Image>();
            previewFace.sprite = FrStudioSprites.Rounded(64, 14, Color.white);
            previewFace.type = Image.Type.Sliced;
            previewFace.color = new Color(theme.ShellBackground.r, theme.ShellBackground.g, theme.ShellBackground.b, 0.92f);
            previewFace.raycastTarget = false;
            var previewLe = preview.GetComponent<LayoutElement>();
            previewLe.minHeight = DeviceLayoutPolicy.IsWideLayout() ? 140f : 86f;
            previewLe.preferredHeight = previewLe.minHeight;
            previewLe.flexibleWidth = 1f;
            previewLe.flexibleHeight = 1f;

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
                // Tall croquis get vertical breathing room; keep artwork dominant.
                trt.offsetMin = new Vector2(6f, 4f);
                trt.offsetMax = new Vector2(-6f, -4f);
            }
            else
            {
                var iconKind = placeholderIcon ?? FrStudioIconKind.Import;
                var mark = new GameObject("Mark", typeof(Image));
                mark.transform.SetParent(preview.transform, false);
                var img = mark.GetComponent<Image>();
                var tile = FrStudioAssets.Icon(iconKind) ?? FrStudioAssets.IconNamed(
                    iconKind == FrStudioIconKind.Import ? "fr_icon_import" : "fr_icon_clear");
                if (tile != null)
                {
                    img.sprite = tile;
                    img.color = Color.white;
                }
                else
                {
                    img.sprite = FrStudioSprites.Icon(iconKind, theme.AccentMuted);
                }

                img.preserveAspect = true;
                img.raycastTarget = false;
                var mrt = mark.GetComponent<RectTransform>();
                mrt.anchorMin = new Vector2(0.5f, 0.5f);
                mrt.anchorMax = new Vector2(0.5f, 0.5f);
                mrt.sizeDelta = new Vector2(72f, 72f);
            }

            var rule = new GameObject("Rule", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            rule.transform.SetParent(col.transform, false);
            rule.GetComponent<LayoutElement>().minHeight = 2f;
            rule.GetComponent<LayoutElement>().preferredHeight = 2f;
            rule.GetComponent<Image>().color = new Color(theme.AccentMuted.r, theme.AccentMuted.g, theme.AccentMuted.b,
                0.55f);
            rule.GetComponent<Image>().raycastTarget = false;

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
                ? Color.Lerp(_idleFace, _theme.Selected, 0.1f)
                : _idleFace;
            // Rose/pink outline — never a solid hot-pink flood.
            _ring.color = _selected
                ? _theme.Selected
                : new Color(_theme.AccentMuted.r, _theme.AccentMuted.g, _theme.AccentMuted.b, 0.55f);
            if (_title != null)
                FrStudioTypography.SetColor(_title, _selected ? _theme.ShellText : _theme.AccentMuted);
        }
    }
}
