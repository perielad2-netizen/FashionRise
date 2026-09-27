using UnityEngine;
using UnityEngine.UI;

namespace MathGame.UI
{
    public class InteractionPrompt : MonoBehaviour
    {
        [SerializeField] GameObject root;
        [SerializeField] Text label;

        public void Show(string message)
        {
            if (label != null)
                label.text = message;

            if (root != null && !root.activeSelf)
                root.SetActive(true);
        }

        public void Hide()
        {
            if (root != null && root.activeSelf)
                root.SetActive(false);
        }
    }
}
