using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IUserProfileService
    {
        Task<UserProfile> GetMyProfileAsync(CancellationToken cancellationToken = default);

        Task<UserProfile> GetPublicProfileAsync(string userId,
            CancellationToken cancellationToken = default);

        Task<CreatorStats> GetMyStatsAsync(CancellationToken cancellationToken = default);
    }
}
