using FashionRise.Content;
using FashionRise.Config;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI.Studio
{
    public sealed class FrStudioShell
    {
        public RectTransform Root { get; }
        public RectTransform TopSlot { get; }
        public RectTransform BodySlot { get; }

        FrStudioShell(RectTransform root, RectTransform top, RectTransform body)
        {
            Root = root;
            TopSlot = top;
            BodySlot = body;
        }

        public static FrStudioShell Build(Transform parent, FashionRiseTheme theme)
        {
            var rootGo = new GameObject("StudioShell", typeof(RectTransform), typeof(Image));
            var root = rootGo.GetComponent<RectTransform>();
            root.SetParent(parent, false);
            root.anchorMin = Vector2.zero;
            root.anchorMax = Vector2.one;
            root.offsetMin = Vector2.zero;
            root.offsetMax = Vector2.zero;
            var bg = rootGo.GetComponent<Image>();
            bg.color = theme.ShellBackground;
            bg.raycastTarget = true;

            var gold = new GameObject("BrandHairline", typeof(RectTransform), typeof(Image));
            var goldRt = gold.GetComponent<RectTransform>();
            goldRt.SetParent(root, false);
            goldRt.anchorMin = new Vector2(0f, 1f);
            goldRt.anchorMax = new Vector2(1f, 1f);
            goldRt.pivot = new Vector2(0.5f, 1f);
            goldRt.sizeDelta = new Vector2(0f, 3f);
            goldRt.anchoredPosition = Vector2.zero;
            gold.GetComponent<Image>().color = theme.AccentMuted;
            gold.GetComponent<Image>().raycastTarget = false;

            var topH = DeviceLayoutPolicy.StudioTopBarHeight;
            var topGo = new GameObject("TopSlot", typeof(RectTransform));
            var top = topGo.GetComponent<RectTransform>();
            top.SetParent(root, false);
            top.anchorMin = new Vector2(0f, 1f);
            top.anchorMax = Vector2.one;
            top.pivot = new Vector2(0.5f, 1f);
            top.sizeDelta = new Vector2(0f, topH);
            top.anchoredPosition = new Vector2(0f, -3f);

            var bodyGo = new GameObject("BodySlot", typeof(RectTransform));
            var body = bodyGo.GetComponent<RectTransform>();
            body.SetParent(root, false);
            body.anchorMin = Vector2.zero;
            body.anchorMax = Vector2.one;
            body.offsetMin = new Vector2(0f, 0f);
            body.offsetMax = new Vector2(0f, -(topH + 3f));

            return new FrStudioShell(root, top, body);
        }
    }
}
