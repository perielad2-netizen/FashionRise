using UnityEngine;

namespace FashionRise.Application
{
    /// <summary>PlayerPrefs-backed “Remember me” for the login form (device-local; replace with secure storage later).</summary>
    public static class LoginRememberPreferences
    {
        const string EnabledKey = "FashionRise.login_remember_enabled";
        const string EmailKey = "FashionRise.login_remember_email";
        const string PasswordKey = "FashionRise.login_remember_password";

        public static bool IsEnabled => PlayerPrefs.GetInt(EnabledKey, 0) != 0;

        public static string SavedEmail => PlayerPrefs.GetString(EmailKey, "") ?? "";

        public static string SavedPassword => PlayerPrefs.GetString(PasswordKey, "") ?? "";

        public static void Save(string email, string password)
        {
            PlayerPrefs.SetInt(EnabledKey, 1);
            PlayerPrefs.SetString(EmailKey, email ?? "");
            PlayerPrefs.SetString(PasswordKey, password ?? "");
            PlayerPrefs.Save();
        }

        public static void Clear()
        {
            PlayerPrefs.SetInt(EnabledKey, 0);
            PlayerPrefs.DeleteKey(EmailKey);
            PlayerPrefs.DeleteKey(PasswordKey);
            PlayerPrefs.Save();
        }
    }
}
