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
        readonly FrStudioOrientationStack _stack;
        readonly FrStudioIconButton[] _tools;

        FrStudioToolRail(RectTransform root, FrStudioOrientationStack stack, FrStudioIconButton draw,
            FrStudioIconButton erase, FrStudioIconButton undo, FrStudioIconButton clear)
        {
            Root = root;
            _stack = stack;
            Draw = draw;
            Erase = erase;
            Undo = undo;
            Clear = clear;
            _tools = new[] { draw, erase, undo, clear };
        }

        public static FrStudioToolRail Build(Transform parent, FashionRiseTheme theme, UnityAction onDraw,
            UnityAction onErase, UnityAction onUndo, UnityAction onClear)
        {
            var go = new GameObject("StudioToolRail", typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            Stretch(rt);
            var img = go.GetComponent<Image>();
            img.sprite = FrStudioSprites.Rounded(64, 18, Color.white);
            img.type = Image.Type.Sliced;
            img.color = theme.ShellPanel;
            img.raycastTarget = true;

            var stack = FrStudioOrientationStack.Create(rt, "Tools", theme.SpaceSm, 10f, TextAnchor.UpperCenter,
                TextAnchor.MiddleCenter, new RectOffset(8, 8, 8, 8));
            stack.Root.offsetMin = new Vector2(8f, 14f);
            stack.Root.offsetMax = new Vector2(-8f, -14f);

            // Wide rail is icon-first; captions stay off until portrait horizontal mode.
            var draw = FrStudioIconButton.Build(stack.Content, theme, FrStudioIconKind.Draw, "Draw", onDraw,
                modeTool: true);
            var erase = FrStudioIconButton.Build(stack.Content, theme, FrStudioIconKind.Erase, "Erase", onErase,
                modeTool: true);
            var divider = FrStudioDivider.Horizontal(stack.Content, theme);
            var undo = FrStudioIconButton.Build(stack.Content, theme, FrStudioIconKind.Undo, "Undo", onUndo);
            var clear = FrStudioIconButton.Build(stack.Content, theme, FrStudioIconKind.Clear, "Clear", onClear);
            stack.Add(draw.transform);
            stack.Add(erase.transform);
            stack.Add(divider);
            stack.Add(undo.transform);
            stack.Add(clear.transform);

            draw.Selected = true;
            var rail = new FrStudioToolRail(rt, stack, draw, erase, undo, clear);
            rail.SetCaptionsVisible(false);
            return rail;
        }

        public void SetDrawSelected(bool drawSelected)
        {
            Draw.Selected = drawSelected;
            Erase.Selected = !drawSelected;
        }

        public void SetHorizontal(bool horizontal)
        {
            _stack.SetHorizontal(horizontal);
            // Portrait strip can show short labels; wide vertical rail stays icon-only.
            SetCaptionsVisible(horizontal);
        }

        void SetCaptionsVisible(bool visible)
        {
            for (var i = 0; i < _tools.Length; i++)
                _tools[i].SetCaptionsVisible(visible);
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
