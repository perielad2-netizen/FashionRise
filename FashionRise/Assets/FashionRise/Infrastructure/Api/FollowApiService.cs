using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class FollowApiService : IFollowService
    {
        readonly ApiClient _client;

        public FollowApiService(ApiClient client) => _client = client;

        public Task FollowAsync(string targetUserId, CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(targetUserId, out var uid))
                throw new ArgumentException("Invalid user id", nameof(targetUserId));
            return _client.PostExpectNoContentAsync($"/profiles/{uid}/follow", new { }, cancellationToken, true);
        }

        public Task UnfollowAsync(string targetUserId, CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(targetUserId, out var uid))
                throw new ArgumentException("Invalid user id", nameof(targetUserId));
            return _client.DeleteAsync($"/profiles/{uid}/follow", cancellationToken, true);
        }

        public async Task<bool> IsFollowingAsync(string targetUserId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(targetUserId, out var uid))
                return false;
            var dto = await _client
                .GetJsonAsync<FollowStatusReadDto>($"/profiles/{uid}/follow-status", cancellationToken, true)
                .ConfigureAwait(true);
            return dto.Following;
        }

        public async Task<IReadOnlyList<string>> GetFollowedUserIdsAsync(CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<Guid>>("/profiles/me/following-ids", cancellationToken, true)
                .ConfigureAwait(true);
            var ids = new List<string>(list.Count);
            foreach (var g in list)
                ids.Add(g.ToString());
            return ids;
        }
    }
}
