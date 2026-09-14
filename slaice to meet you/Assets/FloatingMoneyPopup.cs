using TMPro;
using UnityEngine;

[RequireComponent(typeof(RectTransform))]
[RequireComponent(typeof(CanvasGroup))]
public class FloatingMoneyPopup : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private TMP_Text popupText;
    [SerializeField] private CanvasGroup canvasGroup;

    [Header("Animation")]
    [Tooltip("כמה זמן הפופאפ יוצג")]
    [SerializeField] private float lifetime = 1f;

    [Tooltip("כמה הפופאפ יעלה למעלה")]
    [SerializeField] private float moveUpDistance = 90f;

    [Tooltip("הגודל בתחילת האנימציה")]
    [SerializeField] private float startScale = 0.7f;

    [Tooltip("הגודל המרבי")]
    [SerializeField] private float maximumScale = 1.2f;

    private RectTransform rectTransform;

    private Vector2 startPosition;
    private Vector2 endPosition;

    private float timer;
    private bool isPlaying;

    private void Awake()
    {
        rectTransform = GetComponent<RectTransform>();

        if (popupText == null)
        {
            popupText = GetComponent<TMP_Text>();
        }

        if (canvasGroup == null)
        {
            canvasGroup = GetComponent<CanvasGroup>();
        }
    }

    public void Setup(
        int amount,
        Color popupColor,
        Vector2 spawnPosition
    )
    {
        if (popupText != null)
        {
            popupText.text = "+$" + amount;
            popupText.color = popupColor;
        }

        startPosition = spawnPosition;
        endPosition = startPosition + Vector2.up * moveUpDistance;

        rectTransform.anchoredPosition = startPosition;
        rectTransform.localScale = Vector3.one * startScale;

        canvasGroup.alpha = 1f;

        timer = 0f;
        isPlaying = true;
    }

    private void Update()
    {
        if (!isPlaying)
        {
            return;
        }

        timer += Time.deltaTime;

        float progress = Mathf.Clamp01(
            timer / lifetime
        );

        AnimatePosition(progress);
        AnimateScale(progress);
        AnimateFade(progress);

        if (progress >= 1f)
        {
            Destroy(gameObject);
        }
    }

    private void AnimatePosition(float progress)
    {
        float smoothProgress = Mathf.SmoothStep(
            0f,
            1f,
            progress
        );

        rectTransform.anchoredPosition = Vector2.Lerp(
            startPosition,
            endPosition,
            smoothProgress
        );
    }

    private void AnimateScale(float progress)
    {
        float scale;

        if (progress < 0.25f)
        {
            float popProgress = progress / 0.25f;

            scale = Mathf.Lerp(
                startScale,
                maximumScale,
                popProgress
            );
        }
        else
        {
            float shrinkProgress =
                (progress - 0.25f) / 0.75f;

            scale = Mathf.Lerp(
                maximumScale,
                1f,
                shrinkProgress
            );
        }

        rectTransform.localScale =
            Vector3.one * scale;
    }

    private void AnimateFade(float progress)
    {
        if (progress < 0.5f)
        {
            canvasGroup.alpha = 1f;
            return;
        }

        float fadeProgress =
            (progress - 0.5f) / 0.5f;

        canvasGroup.alpha = Mathf.Lerp(
            1f,
            0f,
            fadeProgress
        );
    }
}