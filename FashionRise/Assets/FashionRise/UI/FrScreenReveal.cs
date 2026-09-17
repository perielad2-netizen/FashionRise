using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.UI
{
    /// <summary>Short fade + lift transition when a screen becomes visible.</summary>
    public sealed class FrScreenReveal : MonoBehaviour
    {
        CanvasGroup? _group;
        RectTransform? _rt;
        bool _played;

        public static void Attach(GameObject screenRoot)
        {
            if (screenRoot.GetComponent<FrScreenReveal>() != null)
                return;
            screenRoot.AddComponent<FrScreenReveal>();
        }

        void OnEnable()
        {
            if (_played)
            {
                Play();
                return;
            }

            _played = true;
            Play();
        }

        void Play()
        {
            _group = GetComponent<CanvasGroup>();
            if (_group == null)
                _group = gameObject.AddComponent<CanvasGroup>();
            _rt = GetComponent<RectTransform>();
            StopAllCoroutines();
            StartCoroutine(Reveal());
        }

        IEnumerator Reveal()
        {
            _group!.alpha = 0f;
            if (_rt != null)
                _rt.anchoredPosition = new Vector2(0f, -18f);
            var t = 0f;
            const float dur = 0.32f;
            while (t < dur)
            {
                t += Time.unscaledDeltaTime;
                var u = Mathf.Clamp01(t / dur);
                var e = 1f - Mathf.Pow(1f - u, 3f);
                _group.alpha = e;
                if (_rt != null)
                    _rt.anchoredPosition = new Vector2(0f, Mathf.Lerp(-18f, 0f, e));
                yield return null;
            }

            _group.alpha = 1f;
            if (_rt != null)
                _rt.anchoredPosition = Vector2.zero;
        }
    }
}
