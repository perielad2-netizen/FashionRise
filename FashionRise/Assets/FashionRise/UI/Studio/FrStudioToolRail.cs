using FashionRise.Content;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioToolRail
    {
        public RectTransform Root { get; }
        public FrStudioIconButton Draw { get; }
        public FrStudioIconButton Erase { get; }
        public FrStudioIconButton Undo { get; }
        public FrStudioIconButton Clear { get; }

        FrStudioToolRail(RectTransform root, FrStudioIconButton draw, FrStudioIconButton erase,
            FrStudioIconButton undo, FrStudioIconButton clear)
        {
            Root = root;
            Draw = draw;
            Erase = erase;
            Undo = undo;
            Clear = clear;
        }

        public static FrStudioToolRail Build(Transform parent, FashionRiseTheme theme, UnityAction onDraw,
            UnityAction onErase, UnityAction onUndo, UnityAction onClear)
        {
            var go = new GameObject("StudioToolRail", typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            Stretch(rt);
            var img = go.GetComponent<Image>();
            img.color = theme.ShellPanel;
            img.raycastTarget = true;

            var col = new GameObject("Col", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var colRt = col.GetComponent<RectTransform>();
            colRt.SetParent(rt, false);
            colRt.anchorMin = Vector2.zero;
            colRt.anchorMax = Vector2.one;
            colRt.offsetMin = new Vector2(8f, 12f);
            colRt.offsetMax = new Vector2(-8f, -12f);
            var v = col.GetComponent<VerticalLayoutGroup>();
            v.spacing = theme.SpaceSm;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var draw = FrStudioIconButton.Build(col.transform, theme, FrStudioIconKind.Draw, "Draw", onDraw);
            var erase = FrStudioIconButton.Build(col.transform, theme, FrStudioIconKind.Erase, "Erase", onErase);
            FrStudioDivider.Horizontal(col.transform, theme);
            var undo = FrStudioIconButton.Build(col.transform, theme, FrStudioIconKind.Undo, "Undo", onUndo);
            var clear = FrStudioIconButton.Build(col.transform, theme, FrStudioIconKind.Clear, "Clear", onClear);

            draw.Selected = true;
            return new FrStudioToolRail(rt, draw, erase, undo, clear);
        }

        public void SetDrawSelected(bool drawSelected)
        {
            Draw.Selected = drawSelected;
            Erase.Selected = !drawSelected;
        }

        public void SetHorizontal(bool horizontal)
        {
            var col = Root.Find("Col");
            if (col == null)
                return;

            var v = col.GetComponent<VerticalLayoutGroup>();
            var h = col.GetComponent<HorizontalLayoutGroup>();
            if (horizontal)
            {
                if (v != null)
                    v.enabled = false;
                if (h == null)
                {
                    h = col.gameObject.AddComponent<HorizontalLayoutGroup>();
                    h.spacing = 8f;
                    h.childAlignment = TextAnchor.MiddleCenter;
                    h.childControlWidth = true;
                    h.childControlHeight = true;
                    h.childForceExpandWidth = true;
                    h.childForceExpandHeight = false;
                    h.padding = new RectOffset(8, 8, 6, 6);
                }

                h.enabled = true;
            }
            else
            {
                if (h != null)
                    h.enabled = false;
                if (v == null)
                {
                    v = col.gameObject.AddComponent<VerticalLayoutGroup>();
                    v.spacing = 10f;
                    v.childAlignment = TextAnchor.UpperCenter;
                    v.childControlWidth = true;
                    v.childControlHeight = true;
                    v.childForceExpandWidth = true;
                    v.childForceExpandHeight = false;
                }

                v.enabled = true;
            }
        }

        static void Stretch(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }
    }
}
