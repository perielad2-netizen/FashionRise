using UnityEngine;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// PlayerPrefs-backed token store. Replace with platform secure storage later without changing callers.
    /// </summary>
    public sealed class TokenStorageService
    {
        const string AccessKey = "fr_access_token";
        const string RefreshKey = "fr_refresh_token";

        public string? AccessToken { get; private set; }
        public string? RefreshToken { get; private set; }

        public bool HasTokens => !string.IsNullOrEmpty(AccessToken);

        public TokenStorageService()
        {
            Load();
        }

        public void Load()
        {
            AccessToken = PlayerPrefs.GetString(AccessKey, "");
            if (string.IsNullOrEmpty(AccessToken))
                AccessToken = null;
            RefreshToken = PlayerPrefs.GetString(RefreshKey, "");
            if (string.IsNullOrEmpty(RefreshToken))
                RefreshToken = null;
        }

        public void SetTokens(string accessToken, string refreshToken)
        {
            AccessToken = accessToken;
            RefreshToken = refreshToken;
            PlayerPrefs.SetString(AccessKey, accessToken);
            PlayerPrefs.SetString(RefreshKey, refreshToken);
            PlayerPrefs.Save();
        }

        public void Clear()
        {
            AccessToken = null;
            RefreshToken = null;
            PlayerPrefs.DeleteKey(AccessKey);
            PlayerPrefs.DeleteKey(RefreshKey);
            PlayerPrefs.Save();
        }
    }
}
