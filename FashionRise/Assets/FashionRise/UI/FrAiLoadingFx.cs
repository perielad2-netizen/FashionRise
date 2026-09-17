using FashionRise.Content;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.UI
{
    /// <summary>
    /// Magical AI progress overlay — scanning line + soft particles + status copy.
    /// Lightweight uGUI; no particle system dependency.
    /// </summary>
    public sealed class FrAiLoadingFx : MonoBehaviour
    {
        RectTransform _root = null!;
        RectTransform _scan = null!;
        Text _status = null!;
        Image[] _dots = null!;
        float _t;
        bool _active;

        public static FrAiLoadingFx Create(Transform parent, FashionRiseTheme theme)
        {
            var go = new GameObject("AiLoadingFx", typeof(RectTransform), typeof(Image), typeof(FrAiLoadingFx));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var veil = go.GetComponent<Image>();
            veil.color = new Color(theme.Background.r, theme.Background.g, theme.Background.b, 0.82f);
            veil.raycastTarget = true;

            var fx = go.GetComponent<FrAiLoadingFx>();
            fx._root = rt;

            var title = FrUiFactory.AddEditorialLabel(go.transform, "AiTitle", "FashionRise AI", theme,
                Mathf.RoundToInt(theme.TitleSize), true, TextAnchor.MiddleCenter);
            var titleRt = title.GetComponent<RectTransform>();
            titleRt.anchorMin = new Vector2(0.1f, 0.58f);
            titleRt.anchorMax = new Vector2(0.9f, 0.68f);
            titleRt.offsetMin = Vector2.zero;
            titleRt.offsetMax = Vector2.zero;
            Object.Destroy(title.GetComponent<LayoutElement>());

            var statusGo = new GameObject("Status", typeof(Text));
            statusGo.transform.SetParent(go.transform, false);
            fx._status = statusGo.GetComponent<Text>();
            fx._status.font = FrUiFonts.UiMedium;
            fx._status.fontSize = Mathf.RoundToInt(theme.BodySize);
            fx._status.color = theme.SecondaryText;
            fx._status.alignment = TextAnchor.MiddleCenter;
            fx._status.text = "Analyzing your sketch…";
            var statusRt = statusGo.GetComponent<RectTransform>();
            statusRt.anchorMin = new Vector2(0.1f, 0.48f);
            statusRt.anchorMax = new Vector2(0.9f, 0.56f);
            statusRt.offsetMin = Vector2.zero;
            statusRt.offsetMax = Vector2.zero;

            // Stage frame for scan
            var stage = new GameObject("Stage", typeof(RectTransform), typeof(Image));
            var stageRt = stage.GetComponent<RectTransform>();
            stageRt.SetParent(go.transform, false);
            stageRt.anchorMin = new Vector2(0.18f, 0.18f);
            stageRt.anchorMax = new Vector2(0.82f, 0.46f);
            stageRt.offsetMin = Vector2.zero;
            stageRt.offsetMax = Vector2.zero;
            var stageImg = stage.GetComponent<Image>();
            stageImg.color = new Color(1f, 1f, 1f, 0.35f);
            stageImg.raycastTarget = false;

            var scanGo = new GameObject("Scan", typeof(RectTransform), typeof(Image));
            fx._scan = scanGo.GetComponent<RectTransform>();
            fx._scan.SetParent(stageRt, false);
            fx._scan.anchorMin = new Vector2(0f, 0.92f);
            fx._scan.anchorMax = new Vector2(1f, 1f);
            fx._scan.offsetMin = Vector2.zero;
            fx._scan.offsetMax = Vector2.zero;
            var scanImg = scanGo.GetComponent<Image>();
            scanImg.color = new Color(theme.Champagne.r, theme.Champagne.g, theme.Champagne.b, 0.55f);
            scanImg.raycastTarget = false;

            fx._dots = new Image[12];
            for (var i = 0; i < fx._dots.Length; i++)
            {
                var d = new GameObject("Dot" + i, typeof(RectTransform), typeof(Image));
                var drt = d.GetComponent<RectTransform>();
                drt.SetParent(stageRt, false);
                drt.sizeDelta = new Vector2(6f, 6f);
                var img = d.GetComponent<Image>();
                img.sprite = FrUiSprites.Circle;
                img.color = new Color(theme.Accent.r, theme.Accent.g, theme.Accent.b, 0.35f);
                img.raycastTarget = false;
                fx._dots[i] = img;
            }

            go.SetActive(false);
            return fx;
        }

        public void Show(string status)
        {
            _active = true;
            if (_status != null)
                _status.text = status;
            gameObject.SetActive(true);
        }

        public void SetStatus(string status)
        {
            if (_status != null)
                _status.text = status;
        }

        public void Hide()
        {
            _active = false;
            gameObject.SetActive(false);
        }

        void Update()
        {
            if (!_active || _scan == null)
                return;

            _t += Time.unscaledDeltaTime;
            var y = Mathf.PingPong(_t * 0.22f, 1f);
            _scan.anchorMin = new Vector2(0f, 1f - y - 0.04f);
            _scan.anchorMax = new Vector2(1f, 1f - y);
            _scan.offsetMin = Vector2.zero;
            _scan.offsetMax = Vector2.zero;

            if (_dots == null)
                return;
            for (var i = 0; i < _dots.Length; i++)
            {
                var img = _dots[i];
                if (img == null)
                    continue;
                var rt = img.rectTransform;
                var a = (i / (float)_dots.Length) * Mathf.PI * 2f + _t * 0.7f;
                var r = 0.28f + 0.08f * Mathf.Sin(_t + i);
                rt.anchorMin = rt.anchorMax = new Vector2(0.5f + Mathf.Cos(a) * r, 0.5f + Mathf.Sin(a) * r);
                rt.anchoredPosition = Vector2.zero;
                var c = img.color;
                c.a = 0.2f + 0.35f * (0.5f + 0.5f * Mathf.Sin(_t * 2f + i));
                img.color = c;
            }
        }
    }
}
