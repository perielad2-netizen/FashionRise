using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IRatingService
    {
        Task<RatingSummary> GetSummaryAsync(string galleryItemId,
            CancellationToken cancellationToken = default);

        Task SubmitRatingAsync(string galleryItemId, int score1To10,
            CancellationToken cancellationToken = default);
    }
}
