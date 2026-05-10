using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;
namespace FashionRise.Infrastructure.Api
{
    public sealed class AuthApiService : IAuthService
    {
        readonly ApiClient _client;
        readonly TokenStorageService _tokens;
        string? _userId;
        bool _guest;

        public AuthApiService(ApiClient client, TokenStorageService tokens)
        {
            _client = client;
            _tokens = tokens;
        }

        public bool IsSignedIn => _guest || !string.IsNullOrEmpty(_userId);

        public string? CurrentSessionUserId => _userId;

        public bool HasBackendSession => !_guest && _tokens.HasTokens;

        public bool IsGuestSession => _guest;

        public Task<AuthResult> SignInGuestAsync(CancellationToken cancellationToken = default)
        {
            _guest = true;
            _userId = "guest-" + Guid.NewGuid().ToString("N")[..8];
            _tokens.Clear();
            return Task.FromResult(new AuthResult
            {
                Success = true,
                UserId = _userId,
                Message = "Guest (local). Sign in for cloud saves and uploads."
            });
        }

        public async Task<AuthResult> SignInAsync(string email, string password,
            CancellationToken cancellationToken = default)
        {
            _guest = false;
            try
            {
                var tokens = await _client.PostJsonAsync<TokenResponseDto>("/auth/login",
                    new { email, password }, cancellationToken).ConfigureAwait(true);
                _tokens.SetTokens(tokens.AccessToken, tokens.RefreshToken);
                var me = await _client.GetJsonAsync<UserReadDto>("/auth/me", cancellationToken)
                    .ConfigureAwait(true);
                _userId = me.Id.ToString();
                return new AuthResult { Success = true, UserId = _userId, Message = "Signed in." };
            }
            catch (ApiException ex)
            {
                return new AuthResult { Success = false, UserId = "", Message = ex.Message };
            }
            catch (Exception ex)
            {
                return new AuthResult { Success = false, UserId = "", Message = ex.Message };
            }
        }

        public async Task<AuthResult> RegisterAsync(string email, string username, string password,
            string? displayName, CancellationToken cancellationToken = default)
        {
            _guest = false;
            try
            {
                var tokens = await _client.PostJsonAsync<TokenResponseDto>("/auth/register",
                    new { email, username, password, display_name = displayName }, cancellationToken)
                    .ConfigureAwait(true);
                _tokens.SetTokens(tokens.AccessToken, tokens.RefreshToken);
                var me = await _client.GetJsonAsync<UserReadDto>("/auth/me", cancellationToken)
                    .ConfigureAwait(true);
                _userId = me.Id.ToString();
                return new AuthResult { Success = true, UserId = _userId, Message = "Registered." };
            }
            catch (ApiException ex)
            {
                return new AuthResult { Success = false, UserId = "", Message = ex.Message };
            }
            catch (Exception ex)
            {
                return new AuthResult { Success = false, UserId = "", Message = ex.Message };
            }
        }

        public Task SignOutAsync(CancellationToken cancellationToken = default)
        {
            _guest = false;
            _userId = null;
            _tokens.Clear();
            return Task.CompletedTask;
        }
    }
}
