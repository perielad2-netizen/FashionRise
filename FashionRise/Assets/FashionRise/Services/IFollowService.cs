using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Services
{
    /// <summary>Pillar B — follow creators; drives <c>/profiles/…/follow</c> and the gallery <c>following</c> feed.</summary>
    public interface IFollowService
    {
        Task FollowAsync(string targetUserId, CancellationToken cancellationToken = default);

        Task UnfollowAsync(string targetUserId, CancellationToken cancellationToken = default);

        Task<bool> IsFollowingAsync(string targetUserId, CancellationToken cancellationToken = default);

        /// <summary>User ids the signed-in viewer follows (empty when not signed in).</summary>
        Task<IReadOnlyList<string>> GetFollowedUserIdsAsync(CancellationToken cancellationToken = default);
    }
}
