using UnityEngine;

namespace MathGame.Dialogue
{
    [CreateAssetMenu(fileName = "Dialogue", menuName = "MathGame/Dialogue")]
    public class DialogueAsset : ScriptableObject
    {
        [SerializeField] string speakerName = "NPC";
        [SerializeField] string[] lines = { "" };

        public string SpeakerName => speakerName;
        public int LineCount => lines == null ? 0 : lines.Length;

        public string GetLine(int index)
        {
            if (lines == null || index < 0 || index >= lines.Length)
                return string.Empty;

            return lines[index];
        }
    }
}
