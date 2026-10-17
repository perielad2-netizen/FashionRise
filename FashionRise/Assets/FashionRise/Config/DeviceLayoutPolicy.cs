using UnityEngine;

namespace FashionRise.Config
{
    /// <summary>
    /// Tablet-first density hints. Studio shell uses <see cref="IsWideLayout"/> for rail/inspector collapse.
    /// [DESKTOP_READY] extend with standalone breakpoints.
    /// </summary>
    public static class DeviceLayoutPolicy
    {
        public const float TabletMinShortEdgeDp = 600f;
        public const float WideAspect = 1.15f;

        public static bool IsTabletLike()
        {
            var shortEdge = Mathf.Min(Screen.width, Screen.height);
            var dpi = Screen.dpi > 1f ? Screen.dpi : 160f;
            var dp = shortEdge / dpi * 160f;
            return dp >= TabletMinShortEdgeDp;
        }

        /// <summary>Landscape tablet / desktop composition: side rails stay visible.</summary>
        public static bool IsWideLayout()
        {
            if (Screen.height <= 1)
                return false;
            return Screen.width / (float)Screen.height >= WideAspect;
        }

        public static float ContentPadding => IsTabletLike() ? 44f : 28f;

        public static float TitleFontSize => IsTabletLike() ? 34f : 26f;

        public static float BodyFontSize => IsTabletLike() ? 22f : 18f;

        public static float StudioTopBarHeight => IsTabletLike() ? 76f : 68f;

        public static float StudioLeftRailWidth => IsTabletLike() ? 228f : 196f;

        public static float StudioToolRailWidth => 76f;

        public static float StudioInspectorWidth => IsTabletLike() ? 292f : 248f;

        public static float StudioNarrowStripHeight => 128f;

        public static float StudioNarrowDockHeight => IsTabletLike() ? 228f : 216f;

        public static float StudioMinTouch => 48f;

        public static float StudioBodyPad => IsTabletLike() ? 18f : 12f;
    }
}
