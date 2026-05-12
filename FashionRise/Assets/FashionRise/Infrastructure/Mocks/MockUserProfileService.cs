using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockUserProfileService : IUserProfileService
    {
        private readonly IAuthService _auth;

        public MockUserProfileService(IAuthService auth)
        {
            _auth = auth;
        }

        public Task<UserProfile> GetMyProfileAsync(CancellationToken cancellationToken = default)
        {
            var id = _auth.CurrentSessionUserId ?? "unknown";
            return Task.FromResult(new UserProfile
            {
                UserId = id,
                DisplayName = "Atelier Member",
                Bio = "Building a capsule of modern, realistic silhouettes.",
                FollowersCount = 12,
                ReputationScore = 41.5,
                ReputationTier = "rising",
                IsPublic = true,
                PublicSlug = id,
                FeaturedDesignIds = Array.Empty<string>()
            });
        }

        public Task<UserProfile> GetPublicProfileAsync(string userId,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new UserProfile
            {
                UserId = userId,
                DisplayName = "Public Creator",
                Bio = "FashionRise profile (mock).",
                FollowersCount = 8,
                ReputationScore = 29.0,
                ReputationTier = "rising",
                IsPublic = true,
                PublicSlug = userId
            });
        }

        public Task<CreatorStats> GetMyStatsAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CreatorStats
            {
                DesignCount = 6,
                PublishedCount = 2,
                AverageRating = 8.2,
                RatingCount = 24
            });
        }
    }
}
