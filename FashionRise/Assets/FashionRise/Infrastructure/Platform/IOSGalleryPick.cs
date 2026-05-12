using System;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;

namespace FashionRise.Infrastructure.Platform
{
    /// <summary>
    /// iOS Photos picker; result is delivered via <see cref="FashionRiseAndroidBridge.OnGalleryPick"/> (same contract as Android).
    /// </summary>
    public static class IOSGalleryPick
    {
        public static bool IsSupported =>
            UnityEngine.Application.platform == RuntimePlatform.IPhonePlayer;

#if UNITY_IOS && !UNITY_EDITOR
        [DllImport("__Internal")]
        static extern void FrGalleryPick_Begin(string importsDir);
#endif

        public static void BeginPickToImportsFolder()
        {
            if (!IsSupported)
                return;

#if UNITY_IOS && !UNITY_EDITOR
            try
            {
                var imports = Path.Combine(UnityEngine.Application.persistentDataPath, "Imports");
                Directory.CreateDirectory(imports);
                FrGalleryPick_Begin(imports);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
#endif
        }
    }
}
