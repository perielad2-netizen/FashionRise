using UnityEngine;

namespace FashionRise.Presentation.Preview
{
    public enum PreviewFraming
    {
        Front,
        Back,
        Side,
        Turntable,
        Runway,
        Lookbook
    }

    /// <summary>
    /// [V2_READY] Dolly, framing presets, and export aspect.
    /// </summary>
    public sealed class PreviewCameraController : MonoBehaviour
    {
        [SerializeField] Camera? previewCamera;
        [SerializeField] Vector3 focusOffset = new(0f, 1.4f, 0f);

        public Camera CameraOrMain => previewCamera != null ? previewCamera : Camera.main!;

        public void FrameDefault() => ApplyFraming(PreviewFraming.Front);

        public void ApplyFraming(PreviewFraming framing)
        {
            var cam = CameraOrMain;
            if (cam == null)
                return;
            var eye = framing switch
            {
                PreviewFraming.Back => focusOffset + new Vector3(0f, 0.25f, -2.8f),
                PreviewFraming.Side => focusOffset + new Vector3(2.8f, 0.2f, 0.6f),
                PreviewFraming.Turntable => focusOffset + new Vector3(2.2f, 0.35f, 2.2f),
                PreviewFraming.Runway => focusOffset + new Vector3(-0.4f, 0.15f, 3.4f),
                PreviewFraming.Lookbook => focusOffset + new Vector3(0.15f, 0.45f, 2.0f),
                _ => focusOffset + new Vector3(0f, 0.2f, 2.6f)
            };
            cam.transform.position = eye;
            cam.transform.LookAt(focusOffset + new Vector3(0f, framing == PreviewFraming.Runway ? 0.35f : 0f, 0f));
        }
    }
}
