using UnityEngine;

namespace FashionRise.UI
{
    /// <summary>Soft press squash, idle pulse, and gentle float for kid studio chrome.</summary>
    public sealed class FrUiMotion : MonoBehaviour
    {
        [SerializeField] float pulseScale = 1.035f;
        [SerializeField] float pulseSeconds = 1.15f;
        [SerializeField] float pressScale = 0.94f;
        [SerializeField] float floatAmplitude = 0f;
        [SerializeField] float floatSeconds = 2.4f;
        RectTransform _rt = null!;
        Vector3 _baseScale;
        Vector2 _basePos;
        bool _pulse;
        bool _pressed;
        bool _float;
        float _phase;

        void Awake()
        {
            _rt = GetComponent<RectTransform>();
            _baseScale = _rt.localScale;
            _basePos = _rt.anchoredPosition;
            _phase = Random.Range(0f, Mathf.PI * 2f);
        }

        public void EnablePulse(bool on) => _pulse = on;

        public void EnableFloat(bool on, float amplitude = 6f, float seconds = 2.6f)
        {
            _float = on;
            floatAmplitude = amplitude;
            floatSeconds = Mathf.Max(0.4f, seconds);
            _basePos = _rt.anchoredPosition;
        }

        public void SetPressed(bool pressed) => _pressed = pressed;

        void Update()
        {
            if (_rt == null)
                return;

            var s = _baseScale;
            if (_pressed)
                s *= pressScale;
            else if (_pulse)
            {
                var w = (Mathf.Sin(Time.unscaledTime * (Mathf.PI * 2f / Mathf.Max(0.2f, pulseSeconds))) + 1f) * 0.5f;
                s *= Mathf.Lerp(1f, pulseScale, w);
            }

            _rt.localScale = Vector3.Lerp(_rt.localScale, s, 1f - Mathf.Exp(-14f * Time.unscaledDeltaTime));

            if (_float && floatAmplitude > 0.01f)
            {
                var t = Time.unscaledTime * (Mathf.PI * 2f / floatSeconds) + _phase;
                var y = Mathf.Sin(t) * floatAmplitude;
                var target = _basePos + new Vector2(0f, y);
                _rt.anchoredPosition = Vector2.Lerp(_rt.anchoredPosition, target,
                    1f - Mathf.Exp(-10f * Time.unscaledDeltaTime));
            }
        }
    }
}
