using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace FashionRise.UI
{
    public static class NativeShareSheet
    {
#if UNITY_IOS && !UNITY_EDITOR
        [DllImport("__Internal")]
        static extern void FrShareSheet_Show(string text, string subject);
#endif

        public static bool TryShareText(string text, string subject = "")
        {
            if (string.IsNullOrWhiteSpace(text))
                return false;

#if UNITY_IOS && !UNITY_EDITOR
            FrShareSheet_Show(text, subject ?? "");
            return true;
#elif UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using var unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
                using var currentActivity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity");
                using var intentClass = new AndroidJavaClass("android.content.Intent");
                using var intent = new AndroidJavaObject("android.content.Intent");
                intent.Call<AndroidJavaObject>("setAction", intentClass.GetStatic<string>("ACTION_SEND"));
                intent.Call<AndroidJavaObject>("setType", "text/plain");
                intent.Call<AndroidJavaObject>("putExtra", intentClass.GetStatic<string>("EXTRA_TEXT"), text);
                if (!string.IsNullOrEmpty(subject))
                    intent.Call<AndroidJavaObject>("putExtra", intentClass.GetStatic<string>("EXTRA_SUBJECT"), subject);

                using var chooser = intentClass.CallStatic<AndroidJavaObject>("createChooser", intent, "Share with");
                currentActivity.Call("startActivity", chooser);
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"Native share failed on Android: {ex.Message}");
                return false;
            }
#else
            return false;
#endif
        }
    }
}
