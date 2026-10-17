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
            Texture2D? portrait = null, bool light = false)
        {
            var go = new GameObject(title + "_Card", typeof(RectTransform), typeof(Image), typeof(Button),
                typeof(FrStudioCard));
            go.transform.SetParent(parent, false);
            var card = go.GetComponent<FrStudioCard>();
            card._theme = theme;
            card._idleFace = light ? theme.CanvasCard : theme.ShellElevated;
            card._face = go.GetComponent<Image>();
            card._face.sprite = FrStudioSprites.Rounded(64, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            card._face.type = Image.Type.Sliced;
            card._face.color = card._idleFace;

            var btn = go.GetComponent<Button>();
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 1f, 1f, 0.94f);
            colors.pressedColor = new Color(0.86f, 0.86f, 0.88f, 1f);
            colors.selectedColor = Color.white;
            colors.disabledColor = theme.Disabled;
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            card.Button = btn;

            var le = go.AddComponent<LayoutElement>();
            le.minHeight = Mathf.Max(DeviceLayoutPolicy.StudioMinTouch + 36f, 88f);
            le.flexibleWidth = 1f;

            var ringGo = new GameObject("Ring", typeof(RectTransform), typeof(Image));
            ringGo.transform.SetParent(go.transform, false);
            var ringRt = ringGo.GetComponent<RectTransform>();
            ringRt.anchorMin = Vector2.zero;
            ringRt.anchorMax = Vector2.one;
            ringRt.offsetMin = Vector2.zero;
            ringRt.offsetMax = Vector2.zero;
            card._ring = ringGo.GetComponent<Image>();
            card._ring.sprite = FrStudioSprites.Rounded(64, Mathf.RoundToInt(theme.CornerRadiusMedium), Color.white);
            card._ring.type = Image.Type.Sliced;
            card._ring.raycastTarget = false;

            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = theme.Shadow;
            shadow.effectDistance = new Vector2(0f, -3f);

            var row = new GameObject("Row", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            row.transform.SetParent(go.transform, false);
            var rowRt = row.GetComponent<RectTransform>();
            rowRt.anchorMin = Vector2.zero;
            rowRt.anchorMax = Vector2.one;
            rowRt.offsetMin = new Vector2(theme.SpaceSm, theme.SpaceSm);
            rowRt.offsetMax = new Vector2(-theme.SpaceSm, -theme.SpaceSm);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = theme.SpaceSm;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            h.childForceExpandHeight = false;
            h.padding = new RectOffset(4, 8, 4, 4);

            if (portrait != null)
            {
                var thumb = new GameObject("Portrait", typeof(RawImage), typeof(LayoutElement));
                thumb.transform.SetParent(row.transform, false);
                var raw = thumb.GetComponent<RawImage>();
                raw.texture = portrait;
                raw.raycastTarget = false;
                var tle = thumb.GetComponent<LayoutElement>();
                tle.preferredWidth = 56f;
                tle.preferredHeight = 72f;
                tle.minWidth = 48f;
                tle.minHeight = 64f;
            }
            else
            {
                var mark = new GameObject("Mark", typeof(Image), typeof(LayoutElement));
                mark.transform.SetParent(row.transform, false);
                var img = mark.GetComponent<Image>();
                img.sprite = FrStudioSprites.Rounded(48, 10, Color.white);
                img.type = Image.Type.Sliced;
                img.color = light ? theme.CanvasWell : new Color(theme.AccentMuted.r, theme.AccentMuted.g,
                    theme.AccentMuted.b, 0.35f);
                img.raycastTarget = false;
                var mle = mark.GetComponent<LayoutElement>();
                mle.preferredWidth = 44f;
                mle.preferredHeight = 56f;
            }

            var titleHost = new GameObject("TitleHost", typeof(RectTransform), typeof(LayoutElement));
            titleHost.transform.SetParent(row.transform, false);
            var titleLe = titleHost.GetComponent<LayoutElement>();
            titleLe.flexibleWidth = 1f;
            titleLe.minHeight = 28f;
            card._title = FrStudioTypography.AddLabel(titleHost.transform, "Title", title, theme,
                FrStudioTypeStyle.SectionHeading, muted: false, TextAnchor.MiddleLeft,
                light ? FrStudioTypeTone.OnLight : FrStudioTypeTone.OnDark);

            card.Refresh();
            return card;
        }

        void Refresh()
        {
            if (_face == null || _theme == null)
                return;
            _face.color = _selected
                ? Color.Lerp(_idleFace, _theme.Selected, 0.18f)
                : _idleFace;
            _ring.color = _selected ? _theme.Selected : new Color(0f, 0f, 0f, 0f);
        }
    }
}
