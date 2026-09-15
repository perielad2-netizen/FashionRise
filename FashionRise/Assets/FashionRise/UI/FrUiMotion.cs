using UnityEngine;

namespace FashionRise.UI
{
    /// <summary>Soft press squash + idle pulse for kid CTAs.</summary>
    public sealed class FrUiMotion : MonoBehaviour
    {
        [SerializeField] float pulseScale = 1.035f;
        [SerializeField] float pulseSeconds = 1.15f;
        [SerializeField] float pressScale = 0.94f;
        RectTransform _rt = null!;
        Vector3 _base;
        bool _pulse;
        bool _pressed;

        void Awake()
        {
            _rt = GetComponent<RectTransform>();
            _base = _rt.localScale;
        }

        public void EnablePulse(bool on) => _pulse = on;

        public void SetPressed(bool pressed) => _pressed = pressed;

        void Update()
        {
            if (_rt == null)
                return;
            var s = _base;
            if (_pressed)
                s *= pressScale;
            else if (_pulse)
            {
                var w = (Mathf.Sin(Time.unscaledTime * (Mathf.PI * 2f / Mathf.Max(0.2f, pulseSeconds))) + 1f) * 0.5f;
                s *= Mathf.Lerp(1f, pulseScale, w);
            }

            _rt.localScale = Vector3.Lerp(_rt.localScale, s, 1f - Mathf.Exp(-14f * Time.unscaledDeltaTime));
        }
    }
}
