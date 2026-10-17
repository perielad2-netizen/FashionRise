using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    /// <summary>
    /// Two sibling containers, each with exactly one layout group. Orientation changes
    /// reparent the same children. Unity UGUI rejects a second LayoutGroup on one GameObject.
    /// </summary>
    public sealed class FrStudioOrientationStack
    {
        readonly RectTransform _vertical;
        readonly RectTransform _horizontal;
        readonly List<Transform> _items = new();
        bool _horizontalActive;

        public RectTransform Root { get; }
        public Transform Content => _horizontalActive ? _horizontal : _vertical;

        FrStudioOrientationStack(RectTransform root, RectTransform vertical, RectTransform horizontal)
        {
            Root = root;
            _vertical = vertical;
            _horizontal = horizontal;
        }

        public static FrStudioOrientationStack Create(Transform parent, string name, float verticalSpacing,
            float horizontalSpacing, TextAnchor verticalAlign, TextAnchor horizontalAlign,
            RectOffset? horizontalPadding = null)
        {
            var rootGo = new GameObject(name, typeof(RectTransform));
            var root = rootGo.GetComponent<RectTransform>();
            root.SetParent(parent, false);
            Stretch(root);

            var verticalGo = new GameObject(name + "Vertical", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var vertical = verticalGo.GetComponent<RectTransform>();
            vertical.SetParent(root, false);
            Stretch(vertical);
            var v = verticalGo.GetComponent<VerticalLayoutGroup>();
            v.spacing = verticalSpacing;
            v.childAlignment = verticalAlign;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;

            var horizontalGo = new GameObject(name + "Horizontal", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            var horizontal = horizontalGo.GetComponent<RectTransform>();
            horizontal.SetParent(root, false);
            Stretch(horizontal);
            var h = horizontalGo.GetComponent<HorizontalLayoutGroup>();
            h.spacing = horizontalSpacing;
            h.childAlignment = horizontalAlign;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = true;
            h.childForceExpandHeight = false;
            if (horizontalPadding != null)
                h.padding = horizontalPadding;
            horizontalGo.SetActive(false);

            return new FrStudioOrientationStack(root, vertical, horizontal);
        }

        public void Add(Transform child)
        {
            child.SetParent(Content, false);
            _items.Add(child);
        }

        public void SetHorizontal(bool horizontal)
        {
            if (horizontal == _horizontalActive)
                return;

            _horizontalActive = horizontal;
            var target = horizontal ? _horizontal : _vertical;
            var idle = horizontal ? _vertical : _horizontal;
            for (var i = 0; i < _items.Count; i++)
            {
                var item = _items[i];
                if (item == null)
                    continue;
                item.SetParent(target, false);
            }

            idle.gameObject.SetActive(false);
            target.gameObject.SetActive(true);
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
