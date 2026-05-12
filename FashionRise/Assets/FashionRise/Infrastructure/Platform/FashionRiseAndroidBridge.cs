using System;
using UnityEngine;

namespace FashionRise.Infrastructure.Platform
{
    /// <summary>Receives <c>UnitySendMessage</c> from Android <c>GalleryPick</c> or iOS <c>FashionRiseGalleryPickBridge</c>.</summary>
    public sealed class FashionRiseAndroidBridge : MonoBehaviour
    {
        public const string GameObjectName = "FashionRiseAndroidBridge";

        /// <summary>Absolute path copied under persistent Imports, or null if cancelled / error.</summary>
        public static event Action<string?>? GalleryPickCompleted;

        void Awake()
        {
            gameObject.name = GameObjectName;
            DontDestroyOnLoad(gameObject);
        }

        /// <summary>Called from Java only; parameter is empty string on failure.</summary>
        public void OnGalleryPick(string path)
        {
            var p = string.IsNullOrEmpty(path) ? null : path;
            GalleryPickCompleted?.Invoke(p);
        }
    }
}
