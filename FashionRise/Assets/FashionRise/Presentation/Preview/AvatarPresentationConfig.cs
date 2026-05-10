using UnityEngine;

namespace FashionRise.Presentation.Preview
{
    /// <summary>
    /// [V2_READY] Rig, LOD, and studio framing for high-quality avatar assets.
    /// </summary>
    [CreateAssetMenu(menuName = "FashionRise/Preview/Avatar Presentation", fileName = "AvatarPresentationConfig")]
    public sealed class AvatarPresentationConfig : ScriptableObject
    {
        public Vector3 ModelRootEuler = new(0f, 180f, 0f);
        public Vector3 ModelScale = Vector3.one;
        public float OrbitDegreesPerSecond = 8f;
    }
}
