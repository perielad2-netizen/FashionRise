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
                DisplayName = id.StartsWith("guest", StringComparison.OrdinalIgnoreCase)
                    ? "Guest Creator"
                    : "Atelier Member",
                Bio = "Building a capsule of modern, realistic silhouettes.",
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
