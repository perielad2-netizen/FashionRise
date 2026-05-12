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

        public AuthApiService(ApiClient client, TokenStorageService tokens)
        {
            _client = client;
            _tokens = tokens;
        }

        public bool IsSignedIn => _tokens.HasTokens && !string.IsNullOrEmpty(_userId);

        public string? CurrentSessionUserId => _userId;

        public bool HasBackendSession => _tokens.HasTokens;

        public async Task TryRestorePersistedSessionAsync(CancellationToken cancellationToken = default)
        {
            if (!_tokens.HasTokens || !string.IsNullOrEmpty(_userId))
                return;
            try
            {
                var me = await _client.GetJsonAsync<UserReadDto>("/auth/me", cancellationToken, true)
                    .ConfigureAwait(true);
                _userId = me.Id.ToString();
            }
            catch (Exception)
            {
                _userId = null;
                _tokens.Clear();
            }
        }

        public async Task<AuthResult> SignInAsync(string email, string password,
            CancellationToken cancellationToken = default)
        {
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

        public async Task SignOutAsync(CancellationToken cancellationToken = default)
        {
            if (HasBackendSession)
            {
                try
                {
                    await _client
                        .PostExpectNoContentAsync("/auth/logout", null, cancellationToken, useBearer: true)
                        .ConfigureAwait(true);
                }
                catch (Exception)
                {
                    // Offline or expired access token — still clear local session.
                }
            }

            _userId = null;
            _tokens.Clear();
        }
    }
}
