using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ClickTomatoSlicer : MonoBehaviour
{
    public enum LocalAxis
    {
        X,
        Y,
        Z
    }

    [Header("Tomato")]
    [SerializeField] private GameObject wholeTomato;
    [SerializeField] private Transform remainingTomato;

    [Header("Slice")]
    [SerializeField] private GameObject slicePrefab;

    [Tooltip("נקודה שנמצאת בצד החתוך של העגבנייה")]
    [SerializeField] private Transform sliceSpawnPoint;

    [Tooltip("אובייקט ריק שעל הקרש")]
    [SerializeField] private Transform boardSlicesParent;

    [Header("Real Gravity")]
    [SerializeField] private float upwardForce = 0.25f;
    [SerializeField] private float sideForce = 0.55f;
    [SerializeField] private float torqueForce = 0.35f;
    [SerializeField] private float sliceMass = 0.25f;
    [SerializeField] private float sliceDrag = 0.25f;
    [SerializeField] private float sliceAngularDrag = 1.5f;

    [Tooltip("כמה זמן מחכים לפרוסה שתסיים ליפול")]
    [SerializeField] private float settleTimeout = 2f;

    [Tooltip("מהירות נמוכה שנחשבת לעצירה")]
    [SerializeField] private float settleVelocity = 0.05f;

    [Header("Slice Direction")]
    [SerializeField] private LocalAxis pushAxis = LocalAxis.X;

    [Tooltip("שנה ל־1 או מינוס 1 אם הפרוסה נזרקת לצד הלא נכון")]
    [SerializeField] private float pushDirection = 1f;

    [Tooltip("הזזה קטנה לכל פרוסה נוספת")]
    [SerializeField] private float sliceSpacing = 0.07f;

    [Header("Tomato Shrinking")]
    [SerializeField] private LocalAxis shrinkAxis = LocalAxis.Z;
    [SerializeField] private float shrinkAmount = 0.11f;
    [SerializeField] private float minimumScale = 0.18f;

    [Tooltip("שנה ל־1 או מינוס 1 אם החלק זז לצד הלא נכון")]
    [SerializeField] private float shrinkMoveDirection = -1f;

    [Header("Cut Effect")]
    [SerializeField] private float cutImpactDuration = 0.07f;
    [SerializeField] private float squashAmount = 0.05f;

    [Header("Plate")]
    [SerializeField] private Transform plateTarget;
    [SerializeField] private float moveToPlateDuration = 0.45f;
    [SerializeField] private float moveToPlateArcHeight = 0.35f;
    [SerializeField] private float timeOnPlate = 5f;

    [Header("Plate Positions")]
    [SerializeField] private float plateSpacingX = 0.13f;
    [SerializeField] private float plateSpacingZ = 0.11f;
    [SerializeField] private float plateHeight = 0.025f;

    [Tooltip("סיבוב הפרוסה כשהיא שוכבת בצלחת")]
    [SerializeField]
    private Vector3 plateSliceRotation =
        new Vector3(90f, 0f, 0f);

    [SerializeField] private float plateRandomRotation = 20f;

    [Header("Game")]
    [SerializeField] private int slicesPerTomato = 8;
    [SerializeField] private float clickCooldown = 0.08f;

    private readonly List<GameObject> createdSlices =
        new List<GameObject>();

    private Vector3 originalRemainingScale;
    private Vector3 originalRemainingPosition;

    private bool firstCut = true;
    private bool isBusy;
    private int cutCount;

    private void Awake()
    {
        if (!ValidateReferences())
        {
            enabled = false;
            return;
        }

        originalRemainingScale = remainingTomato.localScale;
        originalRemainingPosition = remainingTomato.localPosition;

        ResetTomato();
    }

    private void Update()
    {
        if (Input.GetMouseButtonDown(0) && !isBusy)
        {
            StartCoroutine(CutRoutine());
        }
    }

    private IEnumerator CutRoutine()
    {
        isBusy = true;

        yield return StartCoroutine(PlayCutImpact());

        if (firstCut)
        {
            wholeTomato.SetActive(false);
            remainingTomato.gameObject.SetActive(true);
            firstCut = false;
        }
        else
        {
            ShrinkRemainingTomato();
        }

        GameObject newSlice = CreatePhysicalSlice();

        createdSlices.Add(newSlice);
        cutCount++;

        yield return new WaitForSeconds(clickCooldown);

        if (cutCount >= slicesPerTomato)
        {
            yield return StartCoroutine(
                WaitForAllSlicesAndFinish()
            );
        }

        isBusy = false;
    }

    private GameObject CreatePhysicalSlice()
    {
        Vector3 spacingDirection =
            GetWorldAxisDirection(
                sliceSpawnPoint,
                pushAxis
            ) * pushDirection;

        Vector3 spawnPosition =
            sliceSpawnPoint.position +
            spacingDirection *
            sliceSpacing *
            cutCount;

        GameObject newSlice = Instantiate(
            slicePrefab,
            spawnPosition,
            sliceSpawnPoint.rotation
        );

        newSlice.name =
            "TomatoSlice_" + (cutCount + 1);

        /*
         * לא משנים Scale.
         * הפרוסה נשארת בדיוק בגודל של ה-Prefab.
         */

        Collider sliceCollider =
            newSlice.GetComponentInChildren<Collider>();

        if (sliceCollider == null)
        {
            MeshFilter meshFilter =
                newSlice.GetComponentInChildren<MeshFilter>();

            if (meshFilter != null &&
                meshFilter.sharedMesh != null)
            {
                MeshCollider meshCollider =
                    newSlice.AddComponent<MeshCollider>();

                meshCollider.sharedMesh =
                    meshFilter.sharedMesh;

                meshCollider.convex = true;
                sliceCollider = meshCollider;
            }
            else
            {
                sliceCollider =
                    newSlice.AddComponent<BoxCollider>();
            }
        }

        Rigidbody body =
            newSlice.GetComponent<Rigidbody>();

        if (body == null)
        {
            body = newSlice.AddComponent<Rigidbody>();
        }

        body.mass = sliceMass;
        body.drag = sliceDrag;
        body.angularDrag = sliceAngularDrag;
        body.useGravity = true;
        body.isKinematic = false;
        body.collisionDetectionMode =
            CollisionDetectionMode.Continuous;
        body.interpolation =
            RigidbodyInterpolation.Interpolate;

        body.velocity = Vector3.zero;
        body.angularVelocity = Vector3.zero;

        Vector3 force =
            spacingDirection * sideForce +
            Vector3.up * upwardForce;

        body.AddForce(
            force,
            ForceMode.Impulse
        );

        body.AddTorque(
            new Vector3(
                Random.Range(-torqueForce, torqueForce),
                Random.Range(-torqueForce, torqueForce),
                Random.Range(-torqueForce, torqueForce)
            ),
            ForceMode.Impulse
        );

        return newSlice;
    }

    private IEnumerator WaitForAllSlicesAndFinish()
    {
        float elapsed = 0f;

        while (elapsed < settleTimeout)
        {
            elapsed += Time.deltaTime;

            bool allStopped = true;

            foreach (GameObject slice in createdSlices)
            {
                if (slice == null)
                    continue;

                Rigidbody body =
                    slice.GetComponent<Rigidbody>();

                if (body != null &&
                    body.velocity.sqrMagnitude >
                    settleVelocity * settleVelocity)
                {
                    allStopped = false;
                    break;
                }
            }

            if (allStopped)
                break;

            yield return null;
        }

        remainingTomato.gameObject.SetActive(false);

        FreezeAllSlices();

        yield return StartCoroutine(
            MoveSlicesToPlate()
        );

        yield return new WaitForSeconds(
            timeOnPlate
        );

        DeleteAllSlices();
        ResetTomato();
    }

    private void FreezeAllSlices()
    {
        foreach (GameObject slice in createdSlices)
        {
            if (slice == null)
                continue;

            Rigidbody body =
                slice.GetComponent<Rigidbody>();

            if (body != null)
            {
                body.velocity = Vector3.zero;
                body.angularVelocity = Vector3.zero;
                body.useGravity = false;
                body.isKinematic = true;
            }
        }
    }

    private IEnumerator PlayCutImpact()
    {
        Transform tomato =
            firstCut
                ? wholeTomato.transform
                : remainingTomato;

        Vector3 startScale =
            tomato.localScale;

        Vector3 squashScale =
            new Vector3(
                startScale.x * (1f + squashAmount),
                startScale.y * (1f - squashAmount),
                startScale.z * (1f + squashAmount)
            );

        float halfTime =
            cutImpactDuration * 0.5f;

        float elapsed = 0f;

        while (elapsed < halfTime)
        {
            elapsed += Time.deltaTime;

            float t =
                Mathf.Clamp01(
                    elapsed / halfTime
                );

            tomato.localScale =
                Vector3.Lerp(
                    startScale,
                    squashScale,
                    t
                );

            yield return null;
        }

        elapsed = 0f;

        while (elapsed < halfTime)
        {
            elapsed += Time.deltaTime;

            float t =
                Mathf.Clamp01(
                    elapsed / halfTime
                );

            tomato.localScale =
                Vector3.Lerp(
                    squashScale,
                    startScale,
                    t
                );

            yield return null;
        }

        tomato.localScale = startScale;
    }

    private void ShrinkRemainingTomato()
    {
        Vector3 oldScale =
            remainingTomato.localScale;

        Vector3 newScale = oldScale;

        switch (shrinkAxis)
        {
            case LocalAxis.X:
                newScale.x = Mathf.Max(
                    minimumScale,
                    oldScale.x - shrinkAmount
                );
                break;

            case LocalAxis.Y:
                newScale.y = Mathf.Max(
                    minimumScale,
                    oldScale.y - shrinkAmount
                );
                break;

            case LocalAxis.Z:
                newScale.z = Mathf.Max(
                    minimumScale,
                    oldScale.z - shrinkAmount
                );
                break;
        }

        float removed =
            GetAxisValue(oldScale, shrinkAxis) -
            GetAxisValue(newScale, shrinkAxis);

        remainingTomato.localScale =
            newScale;

        remainingTomato.localPosition +=
            GetLocalAxisVector(shrinkAxis) *
            shrinkMoveDirection *
            removed *
            0.5f;
    }

    private IEnumerator MoveSlicesToPlate()
    {
        int count = createdSlices.Count;

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
            GameObject sliceObject =
                createdSlices[i];

            if (sliceObject == null)
                continue;

            Transform slice =
                sliceObject.transform;

            startPositions[i] =
                slice.position;

            startRotations[i] =
                slice.rotation;

            targetPositions[i] =
                plateTarget.TransformPoint(
                    GetPlatePosition(i)
                );

            targetRotations[i] =
                plateTarget.rotation *
                Quaternion.Euler(
                    plateSliceRotation
                ) *
                Quaternion.Euler(
                    0f,
                    Random.Range(
                        -plateRandomRotation,
                        plateRandomRotation
                    ),
                    0f
                );
        }

        float elapsed = 0f;

        while (elapsed < moveToPlateDuration)
        {
            elapsed += Time.deltaTime;

            float t =
                Mathf.Clamp01(
                    elapsed / moveToPlateDuration
                );

            float smoothT =
                Mathf.SmoothStep(0f, 1f, t);

            float arc =
                4f *
                moveToPlateArcHeight *
                t *
                (1f - t);

            for (int i = 0; i < count; i++)
            {
                GameObject sliceObject =
                    createdSlices[i];

                if (sliceObject == null)
                    continue;

                Transform slice =
                    sliceObject.transform;

                Vector3 position =
                    Vector3.Lerp(
                        startPositions[i],
                        targetPositions[i],
                        smoothT
                    );

                position +=
                    Vector3.up * arc;

                slice.position =
                    position;

                slice.rotation =
                    Quaternion.Slerp(
                        startRotations[i],
                        targetRotations[i],
                        smoothT
                    );
            }

            yield return null;
        }

        for (int i = 0; i < count; i++)
        {
            if (createdSlices[i] == null)
                continue;

            Transform slice =
                createdSlices[i].transform;

            slice.position =
                targetPositions[i];

            slice.rotation =
                targetRotations[i];

            slice.SetParent(
                plateTarget,
                true
            );
        }
    }

    private Vector3 GetPlatePosition(int index)
    {
        Vector3[] layout =
        {
            new Vector3(-1f, 0f, -0.60f),
            new Vector3( 0f, 0f, -0.70f),
            new Vector3( 1f, 0f, -0.55f),

            new Vector3(-1f, 0f,  0.05f),
            new Vector3( 0f, 0f,  0.00f),
            new Vector3( 1f, 0f,  0.10f),

            new Vector3(-0.55f, 0f, 0.75f),
            new Vector3( 0.55f, 0f, 0.78f)
        };

        int safeIndex =
            Mathf.Clamp(
                index,
                0,
                layout.Length - 1
            );

        Vector3 result =
            layout[safeIndex];

        result.x *= plateSpacingX;
        result.z *= plateSpacingZ;

        result.y =
            plateHeight +
            index * 0.003f;

        return result;
    }

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

    private void ResetTomato()
    {
        cutCount = 0;
        firstCut = true;

        remainingTomato.localScale =
            originalRemainingScale;

        remainingTomato.localPosition =
            originalRemainingPosition;

        remainingTomato.gameObject.SetActive(false);
        wholeTomato.SetActive(true);
    }

    private bool ValidateReferences()
    {
        bool valid = true;

        if (wholeTomato == null)
        {
            Debug.LogError(
                "Whole Tomato לא מחובר."
            );

            valid = false;
        }

        if (remainingTomato == null)
        {
            Debug.LogError(
                "Remaining Tomato לא מחובר."
            );

            valid = false;
        }

        if (slicePrefab == null)
        {
            Debug.LogError(
                "Slice Prefab לא מחובר."
            );

            valid = false;
        }

        if (sliceSpawnPoint == null)
        {
            Debug.LogError(
                "Slice Spawn Point לא מחובר."
            );

            valid = false;
        }

        if (boardSlicesParent == null)
        {
            Debug.LogError(
                "Board Slices Parent לא מחובר."
            );

            valid = false;
        }

        if (plateTarget == null)
        {
            Debug.LogError(
                "Plate Target לא מחובר."
            );

            valid = false;
        }

        return valid;
    }
}