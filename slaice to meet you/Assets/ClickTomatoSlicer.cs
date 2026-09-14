using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ClickTomatoSlicer : MonoBehaviour
{
    public enum ProductType
    {
        Tomato,
        Cucumber
    }

    public enum LocalAxis
    {
        X,
        Y,
        Z
    }

    [Header("Current Product")]
    [SerializeField]
    private ProductType currentProduct = ProductType.Tomato;

    // =========================================================
    // TOMATO
    // =========================================================

    [Header("Tomato Models")]
    [SerializeField] private GameObject wholeTomato;
    [SerializeField] private Transform remainingTomato;

    [Header("Tomato Slice")]
    [SerializeField] private GameObject tomatoSlicePrefab;
    [SerializeField] private Transform tomatoSliceSpawnPoint;
    [SerializeField] private int tomatoSlicesRequired = 8;

    [Header("Tomato Shrinking")]
    [SerializeField] private LocalAxis tomatoShrinkAxis = LocalAxis.Z;
    [SerializeField] private float tomatoShrinkAmount = 0.11f;
    [SerializeField] private float tomatoMinimumScale = 0.18f;
    [SerializeField] private float tomatoShrinkMoveDirection = -1f;

    // =========================================================
    // CUCUMBER
    // =========================================================

    [Header("Cucumber Purchase")]
    [Tooltip("המחיר לפתיחת המלפפון")]
    [SerializeField] private int cucumberUnlockPrice = 50;

    [Header("Cucumber Models - Put In Order")]
    [Tooltip("המלפפון השלם")]
    [SerializeField] private GameObject wholeCucumber;

    [Tooltip("המלפפון לאחר החיתוך הראשון")]
    [SerializeField] private GameObject cucumberStage1;

    [Tooltip("המלפפון לאחר החיתוך השני")]
    [SerializeField] private GameObject cucumberStage2;

    [Tooltip("המלפפון לאחר החיתוך השלישי")]
    [SerializeField] private GameObject cucumberStage3;

    [Tooltip("החלק האחרון והקטן ביותר")]
    [SerializeField] private GameObject cucumberStage4;

    [Header("Cucumber Slice")]
    [Tooltip("הפרוסה שנוצרת בכל חיתוך")]
    [SerializeField] private GameObject cucumberSlicePrefab;

    [Tooltip("המקום שממנו נוצרת פרוסת המלפפון")]
    [SerializeField] private Transform cucumberSliceSpawnPoint;

    [Header("Cucumber Reward")]
    [Tooltip("כמה כסף מקבלים לאחר סיום מלפפון")]
    [SerializeField] private int cucumberReward = 5;

    // =========================================================
    // SOUND
    // =========================================================

    [Header("Sounds")]
    [SerializeField] private AudioSource audioSource;
    [SerializeField] private AudioClip tomatoCutSound;
    [SerializeField] private AudioClip cucumberCutSound;

    [Range(0f, 1f)]
    [SerializeField] private float cutSoundVolume = 1f;

    [SerializeField] private bool randomizePitch = false;
    [SerializeField] private float minimumPitch = 0.95f;
    [SerializeField] private float maximumPitch = 1.05f;

    // =========================================================
    // SLICE PHYSICS
    // =========================================================

    [Header("Slice Physics")]
    [SerializeField] private LocalAxis pushAxis = LocalAxis.X;

    [Tooltip("שנה בין 1 לבין מינוס 1 אם הפרוסה עפה לצד הלא נכון")]
    [SerializeField] private float pushDirection = 1f;

    [SerializeField] private float sideForce = 0.12f;
    [SerializeField] private float upwardForce = 0.05f;
    [SerializeField] private float torqueForce = 0.04f;

    [SerializeField] private float sliceMass = 0.25f;
    [SerializeField] private float sliceDrag = 0.5f;
    [SerializeField] private float sliceAngularDrag = 2f;

    // =========================================================
    // PLATE
    // =========================================================

    [Header("Plate")]
    [SerializeField] private Transform plateTarget;
    [SerializeField] private float timeOnPlate = 5f;

    [Header("Plate Movement")]
    [SerializeField] private float moveToPlateDuration = 0.45f;
    [SerializeField] private float moveToPlateArcHeight = 0.3f;
    [SerializeField] private float dropHeightAbovePlate = 0.18f;
    [SerializeField] private float plateSpreadRadius = 0.12f;
    [SerializeField] private float plateDropForce = 0.2f;
    [SerializeField] private float plateRandomForce = 0.08f;

    // =========================================================
    // GAME
    // =========================================================

    [Header("Game")]
    [SerializeField] private float clickCooldown = 0.12f;
    [SerializeField] private float settleTimeBeforePlate = 0.5f;

    /*
     * V2 גורם למשחק להתעלם משמירה ישנה
     * שבה המלפפון אולי כבר היה פתוח.
     */
    private const string CucumberUnlockedKey =
        "CucumberUnlocked_V2";

    private readonly List<GameObject> createdSlices =
        new List<GameObject>();

    private readonly List<GameObject> cucumberStages =
        new List<GameObject>();

    private Vector3 tomatoWholeStartPosition;
    private Quaternion tomatoWholeStartRotation;
    private Vector3 tomatoWholeStartScale;

    private Vector3 tomatoRemainingStartPosition;
    private Quaternion tomatoRemainingStartRotation;
    private Vector3 tomatoRemainingStartScale;

    private bool cucumberUnlocked;
    private bool firstTomatoCut = true;
    private bool isBusy;
    private bool isFinishing;

    private int cutCount;
    private int currentCucumberStage;
    private float nextCutTime;

    public ProductType CurrentProduct
    {
        get
        {
            return currentProduct;
        }
    }

    private void Awake()
    {
        ValidateSettings();
        PrepareAudioSource();
        SaveTomatoStartingTransforms();
        CreateCucumberStagesList();
        LoadCucumberUnlock();

        /*
         * המשחק תמיד מתחיל עם עגבנייה.
         */
        currentProduct = ProductType.Tomato;

        ResetTomato();
        HideCucumber();
    }

    private void Update()
    {
        if (isBusy || isFinishing)
        {
            return;
        }

        if (
            Input.GetMouseButtonDown(0) ||
            Input.GetKeyDown(KeyCode.Space)
        )
        {
            TryCut();
        }
    }

    private void TryCut()
    {
        if (Time.time < nextCutTime)
        {
            return;
        }

        nextCutTime = Time.time + clickCooldown;

        StartCoroutine(CutRoutine());
    }

    private IEnumerator CutRoutine()
    {
        isBusy = true;

        bool cutSucceeded;

        if (currentProduct == ProductType.Tomato)
        {
            cutSucceeded = CutTomato();
        }
        else
        {
            cutSucceeded = CutCucumber();
        }

        if (!cutSucceeded)
        {
            isBusy = false;
            yield break;
        }

        yield return new WaitForSeconds(clickCooldown);

        isBusy = false;

        if (IsCurrentProductFinished())
        {
            StartCoroutine(FinishProductRoutine());
        }
    }

    // =========================================================
    // TOMATO CUTTING
    // =========================================================

    private bool CutTomato()
    {
        if (!ValidateTomatoReferences())
        {
            return false;
        }

        PlayCutSound(tomatoCutSound);

        if (firstTomatoCut)
        {
            wholeTomato.SetActive(false);
            remainingTomato.gameObject.SetActive(true);

            firstTomatoCut = false;
        }
        else
        {
            ShrinkTomato();
        }

        GameObject slice = CreatePhysicalSlice(
            tomatoSlicePrefab,
            tomatoSliceSpawnPoint.position,
            tomatoSliceSpawnPoint.rotation
        );

        if (slice != null)
        {
            slice.name =
                "TomatoSlice_" +
                (cutCount + 1);

            createdSlices.Add(slice);
        }

        cutCount++;

        return true;
    }

    private bool ValidateTomatoReferences()
    {
        if (wholeTomato == null)
        {
            Debug.LogError(
                "Whole Tomato לא מחובר."
            );

            return false;
        }

        if (remainingTomato == null)
        {
            Debug.LogError(
                "Remaining Tomato לא מחובר."
            );

            return false;
        }

        if (tomatoSlicePrefab == null)
        {
            Debug.LogError(
                "Tomato Slice Prefab לא מחובר."
            );

            return false;
        }

        if (tomatoSliceSpawnPoint == null)
        {
            Debug.LogError(
                "Tomato Slice Spawn Point לא מחובר."
            );

            return false;
        }

        return true;
    }

    private void ShrinkTomato()
    {
        Vector3 oldScale =
            remainingTomato.localScale;

        Vector3 newScale =
            oldScale;

        switch (tomatoShrinkAxis)
        {
            case LocalAxis.X:
                newScale.x = Mathf.Max(
                    tomatoMinimumScale,
                    oldScale.x - tomatoShrinkAmount
                );
                break;

            case LocalAxis.Y:
                newScale.y = Mathf.Max(
                    tomatoMinimumScale,
                    oldScale.y - tomatoShrinkAmount
                );
                break;

            case LocalAxis.Z:
                newScale.z = Mathf.Max(
                    tomatoMinimumScale,
                    oldScale.z - tomatoShrinkAmount
                );
                break;
        }

        float removedAmount =
            GetAxisValue(
                oldScale,
                tomatoShrinkAxis
            ) -
            GetAxisValue(
                newScale,
                tomatoShrinkAxis
            );

        remainingTomato.localScale =
            newScale;

        remainingTomato.localPosition +=
            GetLocalAxisVector(
                tomatoShrinkAxis
            ) *
            tomatoShrinkMoveDirection *
            removedAmount *
            0.5f;
    }

    // =========================================================
    // CUCUMBER CUTTING
    // =========================================================

    private bool CutCucumber()
    {
        if (!cucumberUnlocked)
        {
            Debug.Log(
                "צריך לקנות את המלפפון ב-$" +
                cucumberUnlockPrice
            );

            return false;
        }

        if (!ValidateCucumberReferences())
        {
            return false;
        }

        PlayCutSound(cucumberCutSound);

        /*
         * מסתיר את מודל המלפפון הנוכחי.
         */
        if (
            currentCucumberStage >= 0 &&
            currentCucumberStage < cucumberStages.Count
        )
        {
            GameObject currentStage =
                cucumberStages[currentCucumberStage];

            if (currentStage != null)
            {
                currentStage.SetActive(false);
            }
        }

        /*
         * יוצר פרוסת מלפפון חדשה בכל לחיצה.
         */
        GameObject slice = CreatePhysicalSlice(
            cucumberSlicePrefab,
            cucumberSliceSpawnPoint.position,
            cucumberSliceSpawnPoint.rotation
        );

        if (slice != null)
        {
            slice.name =
                "CucumberSlice_" +
                (cutCount + 1);

            createdSlices.Add(slice);
        }

        /*
         * עובר למודל המלפפון הקטן הבא.
         */
        currentCucumberStage++;

        if (currentCucumberStage < cucumberStages.Count)
        {
            GameObject nextStage =
                cucumberStages[currentCucumberStage];

            if (nextStage != null)
            {
                nextStage.SetActive(true);
            }
        }

        cutCount++;

        return true;
    }

    private bool ValidateCucumberReferences()
    {
        if (cucumberStages.Count != 5)
        {
            Debug.LogError(
                "צריכים להיות בדיוק 5 מודלים של מלפפון."
            );

            return false;
        }

        for (int i = 0; i < cucumberStages.Count; i++)
        {
            if (cucumberStages[i] == null)
            {
                Debug.LogError(
                    "מודל מלפפון מספר " +
                    i +
                    " לא מחובר."
                );

                return false;
            }
        }

        if (cucumberSlicePrefab == null)
        {
            Debug.LogError(
                "Cucumber Slice Prefab לא מחובר."
            );

            return false;
        }

        if (cucumberSliceSpawnPoint == null)
        {
            Debug.LogError(
                "Cucumber Slice Spawn Point לא מחובר."
            );

            return false;
        }

        return true;
    }

    private bool IsCurrentProductFinished()
    {
        if (currentProduct == ProductType.Tomato)
        {
            return cutCount >= tomatoSlicesRequired;
        }

        /*
         * 5 לחיצות:
         * מלפפון שלם ועוד 4 מודלים קטנים.
         */
        return cutCount >= cucumberStages.Count;
    }

    // =========================================================
    // PRODUCT FINISH
    // =========================================================

    private IEnumerator FinishProductRoutine()
    {
        isFinishing = true;
        isBusy = true;

        HideCurrentProduct();

        yield return new WaitForSeconds(
            settleTimeBeforePlate
        );

        FreezeAllSlices();

        yield return StartCoroutine(
            MoveAllSlicesAbovePlate()
        );

        ReleaseSlicesIntoPlate();

        GiveProductMoney();

        yield return new WaitForSeconds(
            timeOnPlate
        );

        DeleteAllSlices();
        ResetCurrentProduct();

        isBusy = false;
        isFinishing = false;
    }

    private void GiveProductMoney()
    {
        if (MoneyManager.Instance == null)
        {
            Debug.LogWarning(
                "MoneyManager.Instance לא נמצא בסצנה."
            );

            return;
        }

        if (currentProduct == ProductType.Tomato)
        {
            /*
             * העגבנייה משתמשת ברווח המשודרג
             * מתוך MoneyManager.
             */
            MoneyManager.Instance.AddTomatoMoney();
        }
        else
        {
            /*
             * מלפפון שלם נותן 5 דולר.
             */
            MoneyManager.Instance.AddMoney(
                cucumberReward,
                true
            );
        }
    }

    // =========================================================
    // CUCUMBER PURCHASE
    // =========================================================

    public bool BuyCucumber()
    {
        /*
         * אם הוא כבר נקנה,
         * לא מורידים כסף שוב.
         */
        if (cucumberUnlocked)
        {
            return true;
        }

        if (MoneyManager.Instance == null)
        {
            Debug.LogWarning(
                "MoneyManager.Instance לא נמצא."
            );

            return false;
        }

        bool purchaseSucceeded =
            MoneyManager.Instance.TrySpendMoney(
                cucumberUnlockPrice
            );

        if (!purchaseSucceeded)
        {
            Debug.Log(
                "אין מספיק כסף. המלפפון עולה $" +
                cucumberUnlockPrice
            );

            return false;
        }

        cucumberUnlocked = true;

        PlayerPrefs.SetInt(
            CucumberUnlockedKey,
            1
        );

        PlayerPrefs.Save();

        Debug.Log(
            "המלפפון נקנה ב-$" +
            cucumberUnlockPrice
        );

        return true;
    }

    public void BuyOrSelectCucumber()
    {
        if (isBusy || isFinishing)
        {
            return;
        }

        if (!cucumberUnlocked)
        {
            bool purchaseSucceeded =
                BuyCucumber();

            if (!purchaseSucceeded)
            {
                return;
            }
        }

        SelectCucumber();
    }

    public bool IsCucumberUnlocked()
    {
        return cucumberUnlocked;
    }

    public int GetCucumberUnlockPrice()
    {
        return cucumberUnlockPrice;
    }

    // =========================================================
    // PRODUCT SWITCHING
    // =========================================================

    public void SelectCucumber()
    {
        if (!cucumberUnlocked)
        {
            Debug.Log(
                "צריך לקנות את המלפפון ב-$" +
                cucumberUnlockPrice
            );

            return;
        }

        if (isBusy || isFinishing)
        {
            return;
        }

        DeleteAllSlices();

        currentProduct =
            ProductType.Cucumber;

        HideTomato();
        ResetCucumber();

        Debug.Log(
            "נבחר מלפפון."
        );
    }

    public void SelectTomato()
    {
        if (isBusy || isFinishing)
        {
            return;
        }

        DeleteAllSlices();

        currentProduct =
            ProductType.Tomato;

        HideCucumber();
        ResetTomato();

        Debug.Log(
            "נבחרה עגבנייה."
        );
    }

    public void ToggleProduct()
    {
        if (isBusy || isFinishing)
        {
            return;
        }

        if (!cucumberUnlocked)
        {
            BuyOrSelectCucumber();
            return;
        }

        if (currentProduct == ProductType.Cucumber)
        {
            SelectTomato();
        }
        else
        {
            SelectCucumber();
        }
    }

    // =========================================================
    // CUCUMBER MODELS
    // =========================================================

    private void CreateCucumberStagesList()
    {
        cucumberStages.Clear();

        cucumberStages.Add(wholeCucumber);
        cucumberStages.Add(cucumberStage1);
        cucumberStages.Add(cucumberStage2);
        cucumberStages.Add(cucumberStage3);
        cucumberStages.Add(cucumberStage4);
    }

    private void ResetCucumber()
    {
        cutCount = 0;
        currentCucumberStage = 0;
        nextCutTime = 0f;

        HideCucumber();

        if (
            cucumberStages.Count > 0 &&
            cucumberStages[0] != null
        )
        {
            cucumberStages[0].SetActive(true);
        }
    }

    private void HideCucumber()
    {
        foreach (GameObject cucumberStage in cucumberStages)
        {
            if (cucumberStage != null)
            {
                cucumberStage.SetActive(false);
            }
        }
    }

    // =========================================================
    // TOMATO RESET
    // =========================================================

    private void ResetTomato()
    {
        cutCount = 0;
        firstTomatoCut = true;
        nextCutTime = 0f;

        if (wholeTomato != null)
        {
            wholeTomato.transform.position =
                tomatoWholeStartPosition;

            wholeTomato.transform.rotation =
                tomatoWholeStartRotation;

            wholeTomato.transform.localScale =
                tomatoWholeStartScale;

            wholeTomato.SetActive(true);
        }

        if (remainingTomato != null)
        {
            remainingTomato.position =
                tomatoRemainingStartPosition;

            remainingTomato.rotation =
                tomatoRemainingStartRotation;

            remainingTomato.localScale =
                tomatoRemainingStartScale;

            remainingTomato.gameObject.SetActive(false);
        }
    }

    private void ResetCurrentProduct()
    {
        if (currentProduct == ProductType.Tomato)
        {
            ResetTomato();
        }
        else
        {
            ResetCucumber();
        }
    }

    private void HideCurrentProduct()
    {
        if (currentProduct == ProductType.Tomato)
        {
            HideTomato();
        }
        else
        {
            HideCucumber();
        }
    }

    private void HideTomato()
    {
        if (wholeTomato != null)
        {
            wholeTomato.SetActive(false);
        }

        if (remainingTomato != null)
        {
            remainingTomato.gameObject.SetActive(false);
        }
    }

    // =========================================================
    // SLICE CREATION
    // =========================================================

    private GameObject CreatePhysicalSlice(
        GameObject prefab,
        Vector3 position,
        Quaternion rotation
    )
    {
        if (prefab == null)
        {
            return null;
        }

        GameObject newSlice = Instantiate(
            prefab,
            position,
            rotation
        );

        newSlice.SetActive(true);

        Collider sliceCollider =
            newSlice.GetComponentInChildren<Collider>();

        if (sliceCollider == null)
        {
            sliceCollider =
                newSlice.AddComponent<BoxCollider>();
        }

        if (sliceCollider is MeshCollider meshCollider)
        {
            meshCollider.convex = true;
        }

        sliceCollider.isTrigger = false;

        Rigidbody body =
            newSlice.GetComponent<Rigidbody>();

        if (body == null)
        {
            body =
                newSlice.AddComponent<Rigidbody>();
        }

        body.mass = sliceMass;
        body.drag = sliceDrag;
        body.angularDrag = sliceAngularDrag;

        body.useGravity = true;
        body.isKinematic = false;

        body.interpolation =
            RigidbodyInterpolation.Interpolate;

        body.collisionDetectionMode =
            CollisionDetectionMode.ContinuousDynamic;

        body.velocity = Vector3.zero;
        body.angularVelocity = Vector3.zero;

        Vector3 forceDirection =
            GetWorldAxisDirection(
                newSlice.transform,
                pushAxis
            ) *
            pushDirection;

        Vector3 force =
            forceDirection * sideForce +
            Vector3.up * upwardForce;

        body.AddForce(
            force,
            ForceMode.Impulse
        );

        body.AddTorque(
            new Vector3(
                Random.Range(
                    -torqueForce,
                    torqueForce
                ),
                Random.Range(
                    -torqueForce,
                    torqueForce
                ),
                Random.Range(
                    -torqueForce,
                    torqueForce
                )
            ),
            ForceMode.Impulse
        );

        return newSlice;
    }

    // =========================================================
    // SOUND
    // =========================================================

    private void PlayCutSound(AudioClip clip)
    {
        if (
            audioSource == null ||
            clip == null
        )
        {
            return;
        }

        audioSource.pitch =
            randomizePitch
                ? Random.Range(
                    minimumPitch,
                    maximumPitch
                )
                : 1f;

        audioSource.PlayOneShot(
            clip,
            cutSoundVolume
        );
    }

    private void PrepareAudioSource()
    {
        if (audioSource == null)
        {
            audioSource =
                GetComponent<AudioSource>();
        }

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
    }

    // =========================================================
    // PLATE
    // =========================================================

    private void FreezeAllSlices()
    {
        foreach (GameObject slice in createdSlices)
        {
            if (slice == null)
            {
                continue;
            }

            Rigidbody body =
                slice.GetComponent<Rigidbody>();

            if (body == null)
            {
                continue;
            }

            body.velocity = Vector3.zero;
            body.angularVelocity = Vector3.zero;

            body.useGravity = false;
            body.isKinematic = true;
        }
    }

    private IEnumerator MoveAllSlicesAbovePlate()
    {
        if (plateTarget == null)
        {
            Debug.LogWarning(
                "Plate Target לא מחובר."
            );

            yield break;
        }

        int count =
            createdSlices.Count;

        Vector3[] startPositions =
            new Vector3[count];

        Quaternion[] startRotations =
            new Quaternion[count];

        Vector3[] targetPositions =
            new Vector3[count];

        Quaternion[] targetRotations =
            new Quaternion[count];

        for (int i = 0; i < count; i++)
        {
            if (createdSlices[i] == null)
            {
                continue;
            }

            Transform slice =
                createdSlices[i].transform;

            startPositions[i] =
                slice.position;

            startRotations[i] =
                slice.rotation;

            Vector2 spread =
                Random.insideUnitCircle *
                plateSpreadRadius;

            targetPositions[i] =
                plateTarget.position +
                plateTarget.right * spread.x +
                plateTarget.forward * spread.y +
                plateTarget.up *
                (
                    dropHeightAbovePlate +
                    i * 0.025f
                );

            targetRotations[i] =
                plateTarget.rotation *
                Quaternion.Euler(
                    90f,
                    Random.Range(
                        0f,
                        360f
                    ),
                    0f
                );
        }

        float elapsed = 0f;

        while (elapsed < moveToPlateDuration)
        {
            elapsed += Time.deltaTime;

            float progress =
                Mathf.Clamp01(
                    elapsed /
                    moveToPlateDuration
                );

            float smoothProgress =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    progress
                );

            float arc =
                4f *
                moveToPlateArcHeight *
                progress *
                (1f - progress);

            for (int i = 0; i < count; i++)
            {
                if (createdSlices[i] == null)
                {
                    continue;
                }

                Transform slice =
                    createdSlices[i].transform;

                Vector3 position =
                    Vector3.Lerp(
                        startPositions[i],
                        targetPositions[i],
                        smoothProgress
                    );

                position +=
                    Vector3.up * arc;

                slice.position =
                    position;

                slice.rotation =
                    Quaternion.Slerp(
                        startRotations[i],
                        targetRotations[i],
                        smoothProgress
                    );
            }

            yield return null;
        }

        for (int i = 0; i < count; i++)
        {
            if (createdSlices[i] == null)
            {
                continue;
            }

            createdSlices[i].transform.position =
                targetPositions[i];

            createdSlices[i].transform.rotation =
                targetRotations[i];
        }
    }

    private void ReleaseSlicesIntoPlate()
    {
        if (plateTarget == null)
        {
            return;
        }

        foreach (GameObject slice in createdSlices)
        {
            if (slice == null)
            {
                continue;
            }

            Rigidbody body =
                slice.GetComponent<Rigidbody>();

            if (body == null)
            {
                body =
                    slice.AddComponent<Rigidbody>();
            }

            body.isKinematic = false;
            body.useGravity = true;

            body.velocity = Vector3.zero;
            body.angularVelocity = Vector3.zero;

            Vector3 randomForce =
                plateTarget.right *
                Random.Range(
                    -plateRandomForce,
                    plateRandomForce
                ) +
                plateTarget.forward *
                Random.Range(
                    -plateRandomForce,
                    plateRandomForce
                ) +
                Vector3.down *
                plateDropForce;

            body.AddForce(
                randomForce,
                ForceMode.Impulse
            );

            body.AddTorque(
                new Vector3(
                    Random.Range(-0.05f, 0.05f),
                    Random.Range(-0.05f, 0.05f),
                    Random.Range(-0.05f, 0.05f)
                ),
                ForceMode.Impulse
            );
        }
    }

    private void DeleteAllSlices()
    {
        foreach (GameObject slice in createdSlices)
        {
            if (slice != null)
            {
                Destroy(slice);
            }
        }

        createdSlices.Clear();
    }

    // =========================================================
    // STARTING DATA
    // =========================================================

    private void SaveTomatoStartingTransforms()
    {
        if (wholeTomato != null)
        {
            tomatoWholeStartPosition =
                wholeTomato.transform.position;

            tomatoWholeStartRotation =
                wholeTomato.transform.rotation;

            tomatoWholeStartScale =
                wholeTomato.transform.localScale;
        }

        if (remainingTomato != null)
        {
            tomatoRemainingStartPosition =
                remainingTomato.position;

            tomatoRemainingStartRotation =
                remainingTomato.rotation;

            tomatoRemainingStartScale =
                remainingTomato.localScale;
        }
    }

    private void LoadCucumberUnlock()
    {
        cucumberUnlocked =
            PlayerPrefs.GetInt(
                CucumberUnlockedKey,
                0
            ) == 1;
    }

    private void ValidateSettings()
    {
        cucumberUnlockPrice =
            Mathf.Max(
                1,
                cucumberUnlockPrice
            );

        cucumberReward =
            Mathf.Max(
                1,
                cucumberReward
            );

        tomatoSlicesRequired =
            Mathf.Max(
                1,
                tomatoSlicesRequired
            );

        clickCooldown =
            Mathf.Max(
                0.01f,
                clickCooldown
            );
    }

    // =========================================================
    // AXIS HELPERS
    // =========================================================

    private Vector3 GetWorldAxisDirection(
        Transform reference,
        LocalAxis axis
    )
    {
        switch (axis)
        {
            case LocalAxis.X:
                return reference.right;

            case LocalAxis.Y:
                return reference.up;

            case LocalAxis.Z:
                return reference.forward;

            default:
                return reference.right;
        }
    }

    private Vector3 GetLocalAxisVector(
        LocalAxis axis
    )
    {
        switch (axis)
        {
            case LocalAxis.X:
                return Vector3.right;

            case LocalAxis.Y:
                return Vector3.up;

            case LocalAxis.Z:
                return Vector3.forward;

            default:
                return Vector3.forward;
        }
    }

    private float GetAxisValue(
        Vector3 value,
        LocalAxis axis
    )
    {
        switch (axis)
        {
            case LocalAxis.X:
                return value.x;

            case LocalAxis.Y:
                return value.y;

            case LocalAxis.Z:
                return value.z;

            default:
                return value.z;
        }
    }
}