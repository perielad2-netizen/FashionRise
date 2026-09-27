using UnityEngine;

namespace MathGame.Camera
{
    public class CameraFollow : MonoBehaviour
    {
        [SerializeField] Transform target;
        [SerializeField, Min(0.01f)] float smoothTime = 0.18f;
        [SerializeField] Vector3 offset = new Vector3(0f, 0f, -10f);

        Vector3 _velocity;

        void LateUpdate()
        {
            if (target == null)
                return;

            Vector3 desired = target.position + offset;
            desired.z = offset.z;
            transform.position = Vector3.SmoothDamp(transform.position, desired, ref _velocity, smoothTime);
        }
    }
}
