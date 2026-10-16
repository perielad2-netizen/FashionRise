using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// Classifies AI job poll and polish-recovery outcomes.
    /// Keep the decision table in sync with <c>backend/tests/test_magic_look_poll_policy.py</c>.
    /// </summary>
    public static class AiJobPollPolicy
    {
        public const int StatusRequestTimeout = 408;
        public const int StatusTooManyRequests = 429;

        public static bool IsRetryableHttpStatus(int statusCode)
        {
            if (statusCode == StatusRequestTimeout)
                return true;
            return statusCode >= 500 && statusCode <= 599;
        }

        public static bool IsFailFastHttpStatus(int statusCode)
        {
            if (statusCode == StatusTooManyRequests)
                return true;
            if (IsRetryableHttpStatus(statusCode))
                return false;
            return statusCode >= 400 && statusCode <= 499;
        }

        public static bool ShouldRetryPollException(Exception ex, bool userCancelRequested)
        {
            if (userCancelRequested)
                return false;
            if (ex is TaskCanceledException)
                return true;
            if (ex is OperationCanceledException)
                return false;
            if (ex is ApiException api)
                return !IsFailFastHttpStatus(api.StatusCode);
            if (ex is HttpRequestException)
                return true;
            return true;
        }

        public static bool ShouldAttemptPolishRecovery(Exception ex, bool userCancelRequested)
        {
            if (userCancelRequested)
                return false;
            if (ex is TaskCanceledException)
                return true;
            if (ex is OperationCanceledException)
                return false;
            if (ex is ApiException api && IsFailFastHttpStatus(api.StatusCode))
                return false;
            return true;
        }
    }
}
