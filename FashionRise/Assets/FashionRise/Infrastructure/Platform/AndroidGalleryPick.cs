using System;
using System.IO;
using UnityEngine;

namespace FashionRise.Infrastructure.Platform
{
    /// <summary>Starts the Android system image picker (SAF); result arrives on <see cref="FashionRiseAndroidBridge.GalleryPickCompleted"/>.</summary>
    public static class AndroidGalleryPick
    {
        public static bool IsSupported =>
            Application.platform == RuntimePlatform.Android;

        public static void BeginPickToImportsFolder()
        {
            if (!IsSupported)
                return;

            try
            {
                var imports = Path.Combine(Application.persistentDataPath, "Imports");
                Directory.CreateDirectory(imports);
                using var c = new AndroidJavaClass("com.fashionrise.gallery.GalleryPick");
                c.CallStatic("beginPick", imports);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
        }
    }
}
