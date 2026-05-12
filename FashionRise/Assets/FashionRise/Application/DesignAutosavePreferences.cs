using UnityEngine;

namespace FashionRise.Application
{
    /// <summary>PlayerPrefs-backed draft autosave: default interval for everyone; user can change in Settings.</summary>
    public static class DesignAutosavePreferences
    {
        const string EnabledKey = "FashionRise.design_autosave_enabled";
        const string IntervalKey = "FashionRise.design_autosave_interval_sec";

        public const int DefaultIntervalSeconds = 60;
        public const int MinIntervalSeconds = 15;
        public const int MaxIntervalSeconds = 900;

        public static bool IsEnabled => PlayerPrefs.GetInt(EnabledKey, 1) != 0;

        public static void SetEnabled(bool value)
        {
            PlayerPrefs.SetInt(EnabledKey, value ? 1 : 0);
            PlayerPrefs.Save();
        }

        public static int GetIntervalSeconds() =>
            Mathf.Clamp(PlayerPrefs.GetInt(IntervalKey, DefaultIntervalSeconds), MinIntervalSeconds, MaxIntervalSeconds);

        public static void SetIntervalSeconds(int seconds)
        {
            seconds = Mathf.Clamp(seconds, MinIntervalSeconds, MaxIntervalSeconds);
            PlayerPrefs.SetInt(IntervalKey, seconds);
            PlayerPrefs.Save();
        }
    }
}
