using UnityEngine;
using UnityEngine.UI;

public class TomatoUpgradeButton : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private MoneyManager moneyManager;
    [SerializeField] private Button upgradeButton;

    private void Awake()
    {
        if (upgradeButton == null)
        {
            upgradeButton = GetComponent<Button>();
        }
    }

    private void Start()
    {
        if (upgradeButton == null)
        {
            Debug.LogError(
                "TomatoUpgradeButton: לא נמצא Button."
            );

            return;
        }

        if (moneyManager == null)
        {
            Debug.LogError(
                "TomatoUpgradeButton: MoneyManager לא מחובר."
            );

            return;
        }

        upgradeButton.onClick.RemoveListener(
            BuyTomatoUpgrade
        );

        upgradeButton.onClick.AddListener(
            BuyTomatoUpgrade
        );
    }

    public void BuyTomatoUpgrade()
    {
        if (moneyManager == null)
        {
            Debug.LogWarning(
                "MoneyManager לא מחובר."
            );

            return;
        }

        moneyManager.BuyTomatoUpgrade();
    }

    private void OnDestroy()
    {
        if (upgradeButton != null)
        {
            upgradeButton.onClick.RemoveListener(
                BuyTomatoUpgrade
            );
        }
    }
}