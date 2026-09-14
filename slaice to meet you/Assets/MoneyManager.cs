using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class MoneyManager : MonoBehaviour
{
    public static MoneyManager Instance
    {
        get;
        private set;
    }

    [Header("Money UI")]
    [SerializeField] private TMP_Text moneyText;

    [Header("Tomato Upgrade UI")]
    [SerializeField] private Button upgradeButton;
    [SerializeField] private TMP_Text upgradePriceText;
    [SerializeField] private TMP_Text tomatoProfitText;
    [SerializeField] private TMP_Text upgradeLevelText;

    [Header("Money Popup")]
    [SerializeField] private MoneyPopupSpawner moneyPopupSpawner;

    [Header("Starting Settings")]
    [SerializeField] private int startingMoney = 0;
    [SerializeField] private int startingTomatoProfit = 1;

    [Header("Tomato Upgrade Settings")]
    [SerializeField] private int startingUpgradePrice = 10;
    [SerializeField] private float upgradePriceMultiplier = 2f;
    [SerializeField] private float tomatoProfitMultiplier = 2f;

    [Header("Saving")]
    [SerializeField] private bool saveData = true;
    [SerializeField] private bool allowResetWithR = true;

    private const string MoneySaveKey =
        "PlayerMoney";

    private const string TomatoProfitSaveKey =
        "TomatoProfit";

    private const string UpgradePriceSaveKey =
        "TomatoUpgradePrice";

    private const string UpgradeLevelSaveKey =
        "TomatoUpgradeLevel";

    private int currentMoney;
    private int currentTomatoProfit;
    private int currentUpgradePrice;
    private int upgradeLevel;

    public int CurrentMoney
    {
        get
        {
            return currentMoney;
        }
    }

    public int CurrentTomatoProfit
    {
        get
        {
            return currentTomatoProfit;
        }
    }

    public int MoneyPerTomato
    {
        get
        {
            return currentTomatoProfit;
        }
    }

    public int CurrentUpgradePrice
    {
        get
        {
            return currentUpgradePrice;
        }
    }

    public int UpgradeLevel
    {
        get
        {
            return upgradeLevel;
        }
    }

    private void Awake()
    {
        /*
         * יוצר גישה דרך MoneyManager.Instance.
         */
        if (Instance != null && Instance != this)
        {
            Debug.LogWarning(
                "קיים יותר מ-MoneyManager אחד בסצנה."
            );

            Destroy(gameObject);
            return;
        }

        Instance = this;

        ValidateSettings();
        LoadData();
        UpdateAllUI();
    }

    private void Start()
    {
        ConnectUpgradeButton();
    }

    private void Update()
    {
        if (
            allowResetWithR &&
            Input.GetKeyDown(KeyCode.R)
        )
        {
            ResetEverything();
        }
    }

    private void ConnectUpgradeButton()
    {
        if (upgradeButton == null)
        {
            Debug.LogWarning(
                "MoneyManager: כפתור השדרוג לא מחובר."
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

    public void AddTomatoMoney()
    {
        AddMoney(
            currentTomatoProfit,
            true
        );
    }

    public void AddMoney(int amount)
    {
        AddMoney(
            amount,
            false
        );
    }

    public void AddMoney(
        int amount,
        bool showPopup
    )
    {
        if (amount <= 0)
        {
            return;
        }

        currentMoney += amount;

        if (showPopup)
        {
            ShowMoneyPopup(amount);
        }

        SaveData();
        UpdateAllUI();

        Debug.Log(
            "נוסף $" + amount +
            " | סך הכסף: $" +
            currentMoney
        );
    }

    public void BuyTomatoUpgrade()
    {
        if (currentMoney < currentUpgradePrice)
        {
            Debug.Log(
                "אין מספיק כסף לשדרוג. צריך $" +
                currentUpgradePrice
            );

            return;
        }

        currentMoney -= currentUpgradePrice;
        upgradeLevel++;

        currentTomatoProfit = Mathf.CeilToInt(
            currentTomatoProfit *
            tomatoProfitMultiplier
        );

        currentUpgradePrice = Mathf.CeilToInt(
            currentUpgradePrice *
            upgradePriceMultiplier
        );

        SaveData();
        UpdateAllUI();

        Debug.Log(
            "שדרוג העגבנייה נקנה" +
            " | רמה: " +
            upgradeLevel +
            " | רווח מעגבנייה: $" +
            currentTomatoProfit +
            " | מחיר השדרוג הבא: $" +
            currentUpgradePrice
        );
    }

    /*
     * השם הזה נשאר כדי שקוד ישן
     * שקורא ל-BuyUpgrade ימשיך לעבוד.
     */
    public void BuyUpgrade()
    {
        BuyTomatoUpgrade();
    }

    public bool TrySpendMoney(int amount)
    {
        if (amount <= 0)
        {
            return false;
        }

        if (currentMoney < amount)
        {
            Debug.Log(
                "אין מספיק כסף."
            );

            return false;
        }

        currentMoney -= amount;

        SaveData();
        UpdateAllUI();

        return true;
    }

    private void ShowMoneyPopup(int amount)
    {
        if (moneyPopupSpawner == null)
        {
            Debug.LogWarning(
                "MoneyPopupSpawner לא מחובר."
            );

            return;
        }

        moneyPopupSpawner.ShowMoneyPopup(
            amount
        );
    }

    public void ResetEverything()
    {
        currentMoney =
            startingMoney;

        currentTomatoProfit =
            startingTomatoProfit;

        currentUpgradePrice =
            startingUpgradePrice;

        upgradeLevel = 0;

        DeleteSavedData();
        SaveData();
        UpdateAllUI();

        Debug.Log(
            "הכסף והשדרוגים אופסו."
        );
    }

    private void UpdateAllUI()
    {
        UpdateMoneyText();
        UpdateUpgradePriceText();
        UpdateTomatoProfitText();
        UpdateUpgradeLevelText();
        UpdateUpgradeButton();
    }

    private void UpdateMoneyText()
    {
        if (moneyText == null)
        {
            return;
        }

        moneyText.text =
            FormatNumber(currentMoney);
    }

    private void UpdateUpgradePriceText()
    {
        if (upgradePriceText == null)
        {
            return;
        }

        upgradePriceText.text =
            "$" +
            FormatNumber(
                currentUpgradePrice
            );
    }

    private void UpdateTomatoProfitText()
    {
        if (tomatoProfitText == null)
        {
            return;
        }

        tomatoProfitText.text =
            "$" +
            FormatNumber(
                currentTomatoProfit
            );
    }

    private void UpdateUpgradeLevelText()
    {
        if (upgradeLevelText == null)
        {
            return;
        }

        upgradeLevelText.text =
            "LVL " +
            upgradeLevel;
    }

    private void UpdateUpgradeButton()
    {
        if (upgradeButton == null)
        {
            return;
        }

        upgradeButton.interactable =
            currentMoney >=
            currentUpgradePrice;
    }

    private string FormatNumber(int value)
    {
        if (value >= 1000000000)
        {
            return (
                value / 1000000000f
            ).ToString("0.#") + "B";
        }

        if (value >= 1000000)
        {
            return (
                value / 1000000f
            ).ToString("0.#") + "M";
        }

        if (value >= 1000)
        {
            return (
                value / 1000f
            ).ToString("0.#") + "K";
        }

        return value.ToString();
    }

    private void ValidateSettings()
    {
        startingMoney =
            Mathf.Max(
                0,
                startingMoney
            );

        startingTomatoProfit =
            Mathf.Max(
                1,
                startingTomatoProfit
            );

        startingUpgradePrice =
            Mathf.Max(
                1,
                startingUpgradePrice
            );

        upgradePriceMultiplier =
            Mathf.Max(
                1f,
                upgradePriceMultiplier
            );

        tomatoProfitMultiplier =
            Mathf.Max(
                1f,
                tomatoProfitMultiplier
            );
    }

    private void LoadData()
    {
        if (!saveData)
        {
            currentMoney =
                startingMoney;

            currentTomatoProfit =
                startingTomatoProfit;

            currentUpgradePrice =
                startingUpgradePrice;

            upgradeLevel = 0;

            return;
        }

        currentMoney =
            PlayerPrefs.GetInt(
                MoneySaveKey,
                startingMoney
            );

        currentTomatoProfit =
            PlayerPrefs.GetInt(
                TomatoProfitSaveKey,
                startingTomatoProfit
            );

        currentUpgradePrice =
            PlayerPrefs.GetInt(
                UpgradePriceSaveKey,
                startingUpgradePrice
            );

        upgradeLevel =
            PlayerPrefs.GetInt(
                UpgradeLevelSaveKey,
                0
            );
    }

    private void SaveData()
    {
        if (!saveData)
        {
            return;
        }

        PlayerPrefs.SetInt(
            MoneySaveKey,
            currentMoney
        );

        PlayerPrefs.SetInt(
            TomatoProfitSaveKey,
            currentTomatoProfit
        );

        PlayerPrefs.SetInt(
            UpgradePriceSaveKey,
            currentUpgradePrice
        );

        PlayerPrefs.SetInt(
            UpgradeLevelSaveKey,
            upgradeLevel
        );

        PlayerPrefs.Save();
    }

    private void DeleteSavedData()
    {
        if (!saveData)
        {
            return;
        }

        PlayerPrefs.DeleteKey(
            MoneySaveKey
        );

        PlayerPrefs.DeleteKey(
            TomatoProfitSaveKey
        );

        PlayerPrefs.DeleteKey(
            UpgradePriceSaveKey
        );

        PlayerPrefs.DeleteKey(
            UpgradeLevelSaveKey
        );

        PlayerPrefs.Save();
    }

    private void OnDestroy()
    {
        if (upgradeButton != null)
        {
            upgradeButton.onClick.RemoveListener(
                BuyTomatoUpgrade
            );
        }

        if (Instance == this)
        {
            Instance = null;
        }
    }
}