using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class UserProfileApiService : IUserProfileService
    {
        readonly ApiClient _client;

        public UserProfileApiService(ApiClient client) => _client = client;

        public async Task<UserProfile> GetMyProfileAsync(CancellationToken cancellationToken = default)
        {
            var p = await _client.GetJsonAsync<ProfileReadDto>("/profiles/me", cancellationToken)
                .ConfigureAwait(true);
            return ToUserProfile(p);
        }

        public async Task<UserProfile> GetPublicProfileAsync(string userId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(userId, out var gid))
                throw new ArgumentException("Invalid user id", nameof(userId));
            var p = await _client.GetJsonAsync<ProfileReadDto>($"/profiles/{gid}", cancellationToken)
                .ConfigureAwait(true);
            return ToUserProfile(p);
        }

        public async Task<CreatorStats> GetMyStatsAsync(CancellationToken cancellationToken = default)
        {
            var p = await _client.GetJsonAsync<ProfileReadDto>("/profiles/me", cancellationToken)
                .ConfigureAwait(true);
            return new CreatorStats
            {
                DesignCount = p.DesignsCount,
                PublishedCount = p.PublishedCount,
                AverageRating = p.RatingAverage ?? 0,
                RatingCount = p.RatingCount
            };
        }

        static UserProfile ToUserProfile(ProfileReadDto p) =>
            new()
            {
                UserId = p.UserId.ToString(),
                DisplayName = p.DisplayName,
                Bio = p.Bio ?? "",
                FollowersCount = p.FollowersCount,
                ReputationScore = p.ReputationScore,
                ReputationTier = p.ReputationTier ?? "",
                IsPublic = true,
                PublicSlug = p.DisplayName.Replace(" ", "-").ToLowerInvariant(),
                FeaturedDesignIds = Array.Empty<string>()
            };
    }
}
