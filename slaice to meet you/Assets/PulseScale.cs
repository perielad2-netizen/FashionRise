using UnityEngine;

public class PulseScale : MonoBehaviour
{
    [Header("Pulse Settings")]
    [SerializeField] private float scaleAmount = 0.08f;
    [SerializeField] private float pulseSpeed = 2f;

    private Vector3 originalScale;

    private void Awake()
    {
        originalScale = transform.localScale;
    }

    private void Update()
    {
        float pulse =
            1f + Mathf.Sin(Time.time * pulseSpeed) * scaleAmount;

        transform.localScale =
            originalScale * pulse;
    }

    private void OnDisable()
    {
        transform.localScale = originalScale;
    }
}