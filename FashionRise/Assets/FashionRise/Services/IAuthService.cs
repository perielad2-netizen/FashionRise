using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Services
{
    public interface IAuthService
    {
        bool IsSignedIn { get; }
        string? CurrentSessionUserId { get; }

        Task<AuthResult> SignInAsync(string email, string password,
            CancellationToken cancellationToken = default);

        Task<AuthResult> RegisterAsync(string email, string username, string password,
            string? displayName, CancellationToken cancellationToken = default);

        /// <summary>True when a stored access token is present (API mode).</summary>
        bool HasBackendSession { get; }

        /// <summary>Loads <c>/auth/me</c> when tokens exist but user id is not cached yet (e.g. cold start).</summary>
        Task TryRestorePersistedSessionAsync(CancellationToken cancellationToken = default);

        Task SignOutAsync(CancellationToken cancellationToken = default);
    }
}
