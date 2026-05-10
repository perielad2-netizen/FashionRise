using UnityEngine;

namespace FashionRise.Presentation.Preview
{
    /// <summary>
    /// [V2_READY] Key/fill/rim rig tuned for fabric read.
    /// </summary>
    public sealed class StudioLightingController : MonoBehaviour
    {
        [SerializeField] Light[] lights = System.Array.Empty<Light>();

        public void ApplyStudioPreset()
        {
            for (var i = 0; i < lights.Length; i++)
            {
                if (lights[i] == null)
                    continue;
                lights[i].intensity = i == 0 ? 1.1f : 0.45f;
            }
        }
    }
}
