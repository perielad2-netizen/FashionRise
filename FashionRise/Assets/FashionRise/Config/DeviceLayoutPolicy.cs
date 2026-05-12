using UnityEngine;

namespace FashionRise.Config
{
    /// <summary>
    /// Tablet-first density hints. [DESKTOP_READY] extend with standalone breakpoints.
    /// </summary>
    public static class DeviceLayoutPolicy
    {
        public const float TabletMinShortEdgeDp = 600f;

        public static bool IsTabletLike()
        {
            var shortEdge = Mathf.Min(Screen.width, Screen.height);
            var dpi = Screen.dpi > 1f ? Screen.dpi : 160f;
            var dp = shortEdge / dpi * 160f;
            return dp >= TabletMinShortEdgeDp;
        }

        public static float ContentPadding => IsTabletLike() ? 44f : 28f;

        public static float TitleFontSize => IsTabletLike() ? 34f : 26f;

        public static float BodyFontSize => IsTabletLike() ? 22f : 18f;
    }
}
