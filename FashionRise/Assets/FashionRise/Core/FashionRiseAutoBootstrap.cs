using UnityEngine;

namespace FashionRise.Core
{
    /// <summary>
    /// So a fresh URP scene shows the app when you press Play — no manual menu step required.
    /// </summary>
    public static class FashionRiseAutoBootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AfterSceneLoad()
        {
            // Before the hierarchy exists, so even a screen that fails in Awake is on record.
            FrDiag.Install();
            FashionRiseBootstrapBuilder.CreateBootstrapIfMissing();
        }
    }
}
