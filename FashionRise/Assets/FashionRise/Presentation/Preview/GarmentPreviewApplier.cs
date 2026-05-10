using FashionRise.Application;
using UnityEngine;

namespace FashionRise.Presentation.Preview
{
    /// <summary>
    /// Single entry point for preview materials / mesh swaps. [V2_READY] bind to real garment system.
    /// </summary>
    public sealed class GarmentPreviewApplier : MonoBehaviour
    {
        [SerializeField] Renderer[] targetRenderers = System.Array.Empty<Renderer>();

        public void ApplySession(CreateDesignSession session)
        {
            foreach (var r in targetRenderers)
            {
                if (r == null)
                    continue;
                foreach (var m in r.materials)
                    m.color = Color.Lerp(Color.white, new Color(0.92f, 0.88f, 0.84f), 0.35f);
            }

            _ = session;
        }
    }
}
