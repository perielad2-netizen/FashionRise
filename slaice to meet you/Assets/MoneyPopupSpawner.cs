using UnityEngine;

public class MoneyPopupSpawner : MonoBehaviour
{
    [Header("UI References")]
    [Tooltip("ה-Canvas שבו יוצג הפופאפ")]
    [SerializeField] private Canvas targetCanvas;

    [Tooltip("ה-Prefab של הטקסט הצף")]
    [SerializeField] private FloatingMoneyPopup popupPrefab;

    [Tooltip("נקודת ההופעה בתוך ה-Canvas")]
    [SerializeField] private RectTransform popupSpawnPoint;

    [Header("Popup Appearance")]
    [Tooltip("צבע הטקסט של הכסף")]
    [SerializeField]
    private Color popupColor =
        new Color(0.2f, 0.85f, 0.25f, 1f);

    [Tooltip("פיזור קטן כדי שפופאפים לא יופיעו בדיוק אחד על השני")]
    [SerializeField] private float horizontalRandomOffset = 30f;

    [SerializeField] private float verticalRandomOffset = 10f;

    public void ShowMoneyPopup(int amount)
    {
        if (!ValidateReferences())
        {
            return;
        }

        FloatingMoneyPopup popupInstance = Instantiate(
            popupPrefab,
            targetCanvas.transform
        );

        RectTransform popupRect =
            popupInstance.GetComponent<RectTransform>();

        popupRect.anchorMin =
            popupSpawnPoint.anchorMin;

        popupRect.anchorMax =
            popupSpawnPoint.anchorMax;

        popupRect.pivot =
            popupSpawnPoint.pivot;

        Vector2 randomOffset = new Vector2(
            Random.Range(
                -horizontalRandomOffset,
                horizontalRandomOffset
            ),
            Random.Range(
                -verticalRandomOffset,
                verticalRandomOffset
            )
        );

        Vector2 spawnPosition =
            popupSpawnPoint.anchoredPosition +
            randomOffset;

        popupInstance.Setup(
            amount,
            popupColor,
            spawnPosition
        );
    }

    private bool ValidateReferences()
    {
        if (targetCanvas == null)
        {
            Debug.LogError(
                "MoneyPopupSpawner: Target Canvas לא מחובר."
            );

            return false;
        }

        if (popupPrefab == null)
        {
            Debug.LogError(
                "MoneyPopupSpawner: Popup Prefab לא מחובר."
            );

            return false;
        }

        if (popupSpawnPoint == null)
        {
            Debug.LogError(
                "MoneyPopupSpawner: Popup Spawn Point לא מחובר."
            );

            return false;
        }

        return true;
    }
}