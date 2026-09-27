using UnityEngine;

namespace MathGame.Rendering
{
    [RequireComponent(typeof(SpriteRenderer))]
    public class YSort : MonoBehaviour
    {
        [SerializeField] int orderOffset;

        SpriteRenderer _renderer;

        void Awake()
        {
            _renderer = GetComponent<SpriteRenderer>();
        }

        void LateUpdate()
        {
            if (_renderer == null)
                return;

            _renderer.sortingOrder = orderOffset + Mathf.RoundToInt(-transform.position.y * 100f);
        }
    }
}
