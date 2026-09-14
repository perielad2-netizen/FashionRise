using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class CucumberBuyButton : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private ClickTomatoSlicer tomatoSlicer;
    [SerializeField] private Button cucumberButton;
    [SerializeField] private TMP_Text buttonText;

    [Header("Button Text")]
    [SerializeField] private string switchToTomatoText = "TOMATO";
    [SerializeField] private string switchToCucumberText = "CUCUMBER";

    [Header("Settings")]
    [SerializeField] private bool disableWhenNotEnoughMoney = false;

    private void Awake()
    {
        if (cucumberButton == null)
        {
            cucumberButton = GetComponent<Button>();
        }
    }

    private void Start()
    {
        if (!ValidateReferences())
        {
            enabled = false;
            return;
        }

        cucumberButton.onClick.RemoveListener(
            HandleButtonClick
        );

        cucumberButton.onClick.AddListener(
            HandleButtonClick
        );

        UpdateButtonUI();
        UpdateButtonInteractable();
    }

    private void Update()
    {
        UpdateButtonUI();
        UpdateButtonInteractable();
    }

    public void HandleButtonClick()
    {
        if (tomatoSlicer == null)
        {
            return;
        }

        /*
         * לפני הקנייה:
         * חובה לשלם 50 דולר.
         */
        if (!tomatoSlicer.IsCucumberUnlocked())
        {
            bool purchaseSucceeded =
                tomatoSlicer.BuyCucumber();

            if (!purchaseSucceeded)
            {
                Debug.Log(
                    "אין מספיק כסף לקניית המלפפון."
                );

                return;
            }

            /*
             * אחרי הקנייה עוברים מיד למלפפון.
             */
            tomatoSlicer.SelectCucumber();

            UpdateButtonUI();
            return;
        }

        /*
         * אחרי הקנייה:
         * מחליפים בין עגבנייה למלפפון.
         */
        if (
            tomatoSlicer.CurrentProduct ==
            ClickTomatoSlicer.ProductType.Cucumber
        )
        {
            tomatoSlicer.SelectTomato();
        }
        else
        {
            tomatoSlicer.SelectCucumber();
        }

        UpdateButtonUI();
    }

    private void UpdateButtonUI()
    {
        if (
            buttonText == null ||
            tomatoSlicer == null
        )
        {
            return;
        }

        /*
         * כל עוד המלפפון לא נקנה,
         * תמיד מציגים את המחיר.
         */
        if (!tomatoSlicer.IsCucumberUnlocked())
        {
            buttonText.text =
                "$" +
                tomatoSlicer.GetCucumberUnlockPrice();

            return;
        }

        /*
         * המלפפון מוצג:
         * הכפתור יעביר לעגבנייה.
         */
        if (
            tomatoSlicer.CurrentProduct ==
            ClickTomatoSlicer.ProductType.Cucumber
        )
        {
            buttonText.text =
                switchToTomatoText;
        }
        else
        {
            /*
             * העגבנייה מוצגת:
             * הכפתור יעביר למלפפון.
             */
            buttonText.text =
                switchToCucumberText;
        }
    }

    private void UpdateButtonInteractable()
    {
        if (
            cucumberButton == null ||
            tomatoSlicer == null
        )
        {
            return;
        }

        /*
         * אחרי הקנייה הכפתור תמיד פעיל.
         */
        if (tomatoSlicer.IsCucumberUnlocked())
        {
            cucumberButton.interactable = true;
            return;
        }

        /*
         * הכפתור נשאר פעיל גם בלי מספיק כסף.
         * בלחיצה פשוט לא תתבצע קנייה.
         */
        if (!disableWhenNotEnoughMoney)
        {
            cucumberButton.interactable = true;
            return;
        }

        if (MoneyManager.Instance == null)
        {
            cucumberButton.interactable = false;
            return;
        }

        cucumberButton.interactable =
            MoneyManager.Instance.CurrentMoney >=
            tomatoSlicer.GetCucumberUnlockPrice();
    }

    private bool ValidateReferences()
    {
        bool valid = true;

        if (tomatoSlicer == null)
        {
            Debug.LogError(
                "CucumberBuyButton: Tomato Slicer לא מחובר."
            );

            valid = false;
        }

        if (cucumberButton == null)
        {
            Debug.LogError(
                "CucumberBuyButton: Cucumber Button לא מחובר."
            );

            valid = false;
        }

        if (buttonText == null)
        {
            Debug.LogError(
                "CucumberBuyButton: Button Text לא מחובר."
            );

            valid = false;
        }

        return valid;
    }

    private void OnDestroy()
    {
        if (cucumberButton != null)
        {
            cucumberButton.onClick.RemoveListener(
                HandleButtonClick
            );
        }
    }
}