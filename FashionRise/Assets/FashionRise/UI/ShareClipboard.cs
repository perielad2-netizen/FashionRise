using UnityEngine;

namespace FashionRise.UI
{
    public static class ShareClipboard
    {
        public static void Copy(string text)
        {
            if (string.IsNullOrEmpty(text))
                return;
            GUIUtility.systemCopyBuffer = text;
        }
    }
}
