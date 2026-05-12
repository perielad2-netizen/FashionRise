using UnityEngine;

namespace FashionRise.Application
{
    /// <summary>PlayerPrefs-backed authoring mode: Guided (default) or Pro controls in Create Design.</summary>
    public static class AuthoringModePreferences
    {
        const string ProModeKey = "FashionRise.authoring_pro_mode";

        public static bool IsProMode => PlayerPrefs.GetInt(ProModeKey, 0) != 0;

        public static void SetProMode(bool value)
        {
            PlayerPrefs.SetInt(ProModeKey, value ? 1 : 0);
            PlayerPrefs.Save();
        }
    }
}
