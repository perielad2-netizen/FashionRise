using FashionRise.Application;
using UnityEngine;

namespace FashionRise.Presentation.Preview
{
    /// <summary>
    /// Orchestrates preview subsystems. [DESKTOP_READY] hotkeys for orbit/zoom.
    /// </summary>
    public sealed class ModelPreviewController : MonoBehaviour
    {
        [SerializeField] GarmentPreviewApplier? applier;
        [SerializeField] PreviewCameraController? cameraController;
        [SerializeField] StudioLightingController? lighting;
        [SerializeField] AvatarPresentationConfig? config;

        public void Present(CreateDesignSession session)
        {
            if (cameraController != null)
                cameraController.FrameDefault();
            if (lighting != null)
                lighting.ApplyStudioPreset();
            if (applier != null)
                applier.ApplySession(session);
            if (config != null)
                transform.localScale = config.ModelScale;
        }
    }
}
