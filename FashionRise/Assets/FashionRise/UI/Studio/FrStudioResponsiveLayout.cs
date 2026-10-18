using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioResponsiveLayout : MonoBehaviour
    {
        FashionRiseTheme _theme = null!;
        RectTransform _left = null!;
        RectTransform _rail = null!;
        RectTransform _canvas = null!;
        RectTransform _inspector = null!;
        bool _wide = true;
        int _lastW;
        int _lastH;

        public RectTransform LeftPanel => _left;
        public RectTransform ToolRail => _rail;
        public RectTransform CanvasHost => _canvas;
        public RectTransform Inspector => _inspector;
        public bool IsWide => _wide;

        public static FrStudioResponsiveLayout Build(Transform parent, FashionRiseTheme theme)
        {
            var go = new GameObject("StudioLayout", typeof(RectTransform), typeof(FrStudioResponsiveLayout));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            var layout = go.GetComponent<FrStudioResponsiveLayout>();
            layout._theme = theme;
            layout._left = CreateSlot(rt, "LeftPanel", theme.ShellPanel, soft: true);
            layout._rail = CreateSlot(rt, "ToolRailSlot", theme.ShellBackground, soft: true);
            layout._canvas = CreateSlot(rt, "CanvasHost", theme.CanvasSurface, soft: false, deepShadow: true);
            layout._inspector = CreateSlot(rt, "InspectorSlot", theme.CanvasSurface, soft: false);
            layout.Apply(force: true);
            return layout;
        }

        public void RefreshIfNeeded()
        {
            if (Screen.width == _lastW && Screen.height == _lastH)
                return;
            Apply(force: false);
        }

        public void Apply(bool force)
        {
            var wide = DeviceLayoutPolicy.IsWideLayout();
            if (!force && wide == _wide && Screen.width == _lastW && Screen.height == _lastH)
                return;

            _wide = wide;
            _lastW = Screen.width;
            _lastH = Screen.height;
            var pad = DeviceLayoutPolicy.StudioBodyPad;

            if (wide)
                ApplyWide(pad);
            else
                ApplyNarrow(pad);
        }

        void ApplyWide(float pad)
        {
            var leftW = DeviceLayoutPolicy.StudioLeftRailWidth;
            var railW = DeviceLayoutPolicy.StudioToolRailWidth;
            var inspW = DeviceLayoutPolicy.StudioInspectorWidth;
            var gap = 14f;

            // Dark chrome frames the canvas; gaps give the hero surface breathing room.
            Anchor(_left, new Vector2(0f, 0f), new Vector2(0f, 1f), new Vector2(pad, pad),
                new Vector2(pad + leftW, -pad));
            Anchor(_rail, new Vector2(0f, 0f), new Vector2(0f, 1f), new Vector2(pad + leftW + gap, pad),
                new Vector2(pad + leftW + gap + railW, -pad));
            Anchor(_inspector, new Vector2(1f, 0f), new Vector2(1f, 1f),
                new Vector2(-(pad + inspW), pad), new Vector2(-pad, -pad));
            Anchor(_canvas, new Vector2(0f, 0f), new Vector2(1f, 1f),
                new Vector2(pad + leftW + railW + gap * 2f, pad),
                new Vector2(-(pad + inspW + gap), -pad));

            SetSlotColor(_left, _theme.ShellPanel);
            SetSlotColor(_rail, _theme.ShellPanel);
            SetSlotColor(_canvas, _theme.CanvasSurface);
            SetSlotColor(_inspector, _theme.CanvasSurface);
        }

        void ApplyNarrow(float pad)
        {
            var strip = DeviceLayoutPolicy.StudioNarrowStripHeight;
            var dock = DeviceLayoutPolicy.StudioNarrowDockHeight;
            var railH = 80f;

            Anchor(_left, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(pad, -(pad + strip)), new Vector2(-pad, -pad));
            Anchor(_rail, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(pad, pad + dock), new Vector2(-pad, pad + dock + railH));
            Anchor(_inspector, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(pad, pad), new Vector2(-pad, pad + dock));
            Anchor(_canvas, new Vector2(0f, 0f), new Vector2(1f, 1f),
                new Vector2(pad, pad + dock + railH + 8f),
                new Vector2(-pad, -(pad + strip + 8f)));

            SetSlotColor(_left, _theme.ShellPanel);
            SetSlotColor(_rail, _theme.ShellPanel);
            SetSlotColor(_canvas, _theme.CanvasSurface);
            SetSlotColor(_inspector, _theme.CanvasSurface);
        }

        static RectTransform CreateSlot(Transform parent, string name, Color color, bool soft, bool deepShadow = false)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.sprite = FrStudioSprites.Rounded(72, soft ? 18 : 22, Color.white);
            img.type = Image.Type.Sliced;
            img.color = color;
            img.raycastTarget = true;
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, deepShadow ? 0.34f : 0.2f);
            shadow.effectDistance = new Vector2(0f, deepShadow ? -8f : -3f);
            return go.GetComponent<RectTransform>();
        }

        static void Anchor(RectTransform rt, Vector2 min, Vector2 max, Vector2 offMin, Vector2 offMax)
        {
            rt.anchorMin = min;
            rt.anchorMax = max;
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.offsetMin = offMin;
            rt.offsetMax = offMax;
        }

        static void SetSlotColor(RectTransform rt, Color color)
        {
            var img = rt.GetComponent<Image>();
            if (img != null)
                img.color = color;
        }
    }
}
