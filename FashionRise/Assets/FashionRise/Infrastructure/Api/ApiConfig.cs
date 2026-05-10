using System;
using UnityEngine;

namespace FashionRise.Infrastructure.Api
{
    [Serializable]
    public sealed class ApiConfig
    {
        [SerializeField] string baseUrl = "http://127.0.0.1:8000/api/v1";
        [SerializeField] int requestTimeoutSeconds = 30;
        [SerializeField] bool offlineModePlaceholder;
        [SerializeField] int retryAttemptsPlaceholder;
        [Tooltip("When on, the app uses Mock* services (no HTTP). Off by default so dev matches FastAPI.")]
        [SerializeField] bool useMockServices;
        [Tooltip("When on, the app uses the FastAPI client (default for development).")]
        [SerializeField] bool useApiServices = true;

        public string BaseUrl
        {
            get => baseUrl;
            set => baseUrl = value;
        }

        public int RequestTimeoutSeconds
        {
            get => requestTimeoutSeconds;
            set => requestTimeoutSeconds = value;
        }

        public bool OfflineModePlaceholder
        {
            get => offlineModePlaceholder;
            set => offlineModePlaceholder = value;
        }

        public int RetryAttemptsPlaceholder
        {
            get => retryAttemptsPlaceholder;
            set => retryAttemptsPlaceholder = value;
        }

        public bool UseMockServices
        {
            get => useMockServices;
            set => useMockServices = value;
        }

        public bool UseApiServices
        {
            get => useApiServices;
            set => useApiServices = value;
        }

        /// <summary>
        /// True when API backend should be wired. If both flags are true, API wins (with a console warning).
        /// </summary>
        public bool ShouldUseApiBackend()
        {
            if (useApiServices && useMockServices)
                Debug.LogWarning("FashionRise: Use Api Services and Use Mock Services are both set; using API backend.");
            if (useApiServices)
                return true;
            return !useMockServices;
        }
    }
}
