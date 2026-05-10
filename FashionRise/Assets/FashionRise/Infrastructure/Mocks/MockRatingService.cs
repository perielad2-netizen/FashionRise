using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockRatingService : IRatingService
    {
        private readonly IGalleryService _gallery;
        private readonly ConcurrentDictionary<string, (double sum, int count, int? mine)> _aggregate = new();

        public MockRatingService(IGalleryService gallery)
        {
            _gallery = gallery;
        }

        public async Task<RatingSummary> GetSummaryAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            var item = await _gallery.GetByIdAsync(galleryItemId, cancellationToken).ConfigureAwait(false);
            if (item == null)
                return new RatingSummary();

            if (_aggregate.TryGetValue(galleryItemId, out var a))
                return new RatingSummary { Average = a.sum / System.Math.Max(1, a.count), Count = a.count, MyScore = a.mine };

            return item.Rating;
        }

        public async Task SubmitRatingAsync(string galleryItemId, int score1To10,
            CancellationToken cancellationToken = default)
        {
            var item = await _gallery.GetByIdAsync(galleryItemId, cancellationToken).ConfigureAwait(false);
            if (item == null)
                return;

            var clamped = System.Math.Clamp(score1To10, 1, 10);
            _aggregate.AddOrUpdate(
                galleryItemId,
                _ => (clamped, 1, clamped),
                (_, old) =>
                {
                    var newCount = old.count + 1;
                    var newSum = old.sum + clamped;
                    return (newSum, newCount, clamped);
                });
        }
    }
}
