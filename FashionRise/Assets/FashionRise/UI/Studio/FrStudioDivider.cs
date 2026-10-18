using FashionRise.Content;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public static class FrStudioDivider
    {
        public static RectTransform Horizontal(Transform parent, FashionRiseTheme theme, float height = 1f)
        {
            var go = new GameObject("Divider", typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = theme.Divider;
            img.raycastTarget = false;
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = height;
            le.preferredHeight = height;
            le.flexibleWidth = 1f;
            return go.GetComponent<RectTransform>();
        }

        public static RectTransform Vertical(Transform parent, FashionRiseTheme theme, float width = 1f)
        {
            var go = new GameObject("VDivider", typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = theme.Divider;
            img.raycastTarget = false;
            var le = go.AddComponent<LayoutElement>();
            le.minWidth = width;
            le.preferredWidth = width;
            le.flexibleHeight = 1f;
            return go.GetComponent<RectTransform>();
        }
    }
}
