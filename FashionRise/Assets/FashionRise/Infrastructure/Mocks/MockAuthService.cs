using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockAuthService : IAuthService
    {
        private string? _userId;
        private bool _guest;

        public bool IsSignedIn => !string.IsNullOrEmpty(_userId);

        public string? CurrentSessionUserId => _userId;

        public bool HasBackendSession => false;

        public bool IsGuestSession => _guest;

        public Task<AuthResult> SignInGuestAsync(CancellationToken cancellationToken = default)
        {
            _guest = true;
            _userId = "guest-" + Guid.NewGuid().ToString("N")[..8];
            return Task.FromResult(new AuthResult { Success = true, UserId = _userId });
        }

        public Task<AuthResult> SignInAsync(string email, string password,
            CancellationToken cancellationToken = default)
        {
            _guest = false;
            _userId = "user-" + (email?.GetHashCode() ?? 0).ToString("x8");
            return Task.FromResult(new AuthResult { Success = true, UserId = _userId });
        }

        public Task<AuthResult> RegisterAsync(string email, string username, string password,
            string? displayName, CancellationToken cancellationToken = default)
        {
            _guest = false;
            _userId = "user-" + (username?.GetHashCode() ?? 0).ToString("x8");
            return Task.FromResult(new AuthResult { Success = true, UserId = _userId, Message = "Mock register." });
        }

        public Task SignOutAsync(CancellationToken cancellationToken = default)
        {
            _userId = null;
            _guest = false;
            return Task.CompletedTask;
        }
    }
}
