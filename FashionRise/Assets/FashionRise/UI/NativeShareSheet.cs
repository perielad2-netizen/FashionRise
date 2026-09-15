using System;
using System.IO;
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

        /// <summary>
        /// Share a local image file when possible; falls back to caption text / clipboard path on Editor &amp; PC.
        /// </summary>
        public static bool TryShareImageFile(string absolutePath, string caption = "", string subject = "FashionRise")
        {
            if (string.IsNullOrWhiteSpace(absolutePath) || !File.Exists(absolutePath))
                return TryShareText(string.IsNullOrWhiteSpace(caption) ? absolutePath : caption, subject);

#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using var unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
                using var currentActivity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity");
                using var intentClass = new AndroidJavaClass("android.content.Intent");
                using var uriClass = new AndroidJavaClass("android.net.Uri");
                using var file = new AndroidJavaObject("java.io.File", absolutePath);
                using var uri = uriClass.CallStatic<AndroidJavaObject>("fromFile", file);
                using var intent = new AndroidJavaObject("android.content.Intent");
                intent.Call<AndroidJavaObject>("setAction", intentClass.GetStatic<string>("ACTION_SEND"));
                intent.Call<AndroidJavaObject>("setType", "image/png");
                intent.Call<AndroidJavaObject>("putExtra", intentClass.GetStatic<string>("EXTRA_STREAM"), uri);
                if (!string.IsNullOrWhiteSpace(caption))
                    intent.Call<AndroidJavaObject>("putExtra", intentClass.GetStatic<string>("EXTRA_TEXT"), caption);
                if (!string.IsNullOrEmpty(subject))
                    intent.Call<AndroidJavaObject>("putExtra", intentClass.GetStatic<string>("EXTRA_SUBJECT"), subject);
                intent.Call<AndroidJavaObject>("addFlags", intentClass.GetStatic<int>("FLAG_GRANT_READ_URI_PERMISSION"));

                using var chooser = intentClass.CallStatic<AndroidJavaObject>("createChooser", intent, "Share look");
                currentActivity.Call("startActivity", chooser);
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"Native image share failed on Android: {ex.Message}");
                return TryShareText(string.IsNullOrWhiteSpace(caption)
                    ? $"Made with FashionRise\n{absolutePath}"
                    : caption, subject);
            }
#elif UNITY_IOS && !UNITY_EDITOR
            var text = string.IsNullOrWhiteSpace(caption)
                ? $"Made with FashionRise — {absolutePath}"
                : $"{caption}\n{absolutePath}";
            return TryShareText(text, subject);
#else
            var line = string.IsNullOrWhiteSpace(caption)
                ? $"Made with FashionRise\n{absolutePath}"
                : $"{caption}\n{absolutePath}";
            ShareClipboard.Copy(line);
            try
            {
                var folder = Path.GetDirectoryName(absolutePath);
                if (!string.IsNullOrEmpty(folder))
                    UnityEngine.Application.OpenURL(new Uri(folder).AbsoluteUri);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"Open sketch folder failed: {ex.Message}");
            }

            return true;
#endif
        }
    }
}
