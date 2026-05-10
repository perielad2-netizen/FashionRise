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
            FashionRiseBootstrapBuilder.CreateBootstrapIfMissing();
        }
    }
}
