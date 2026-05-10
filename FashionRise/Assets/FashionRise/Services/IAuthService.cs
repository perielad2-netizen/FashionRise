using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Services
{
    public interface IAuthService
    {
        bool IsSignedIn { get; }
        string? CurrentSessionUserId { get; }

        Task<AuthResult> SignInGuestAsync(CancellationToken cancellationToken = default);

        Task<AuthResult> SignInAsync(string email, string password,
            CancellationToken cancellationToken = default);

        Task<AuthResult> RegisterAsync(string email, string username, string password,
            string? displayName, CancellationToken cancellationToken = default);

        /// <summary>True when a backend JWT is available (not guest-only).</summary>
        bool HasBackendSession { get; }

        /// <summary>True for continue-as-guest in API mode.</summary>
        bool IsGuestSession { get; }

        Task SignOutAsync(CancellationToken cancellationToken = default);
    }
}
