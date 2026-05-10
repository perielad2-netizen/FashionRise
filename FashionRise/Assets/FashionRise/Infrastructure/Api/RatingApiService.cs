using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class RatingApiService : IRatingService
    {
        readonly ApiClient _client;

        public RatingApiService(ApiClient client) => _client = client;

        public async Task<RatingSummary> GetSummaryAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var list = await _client
                    .GetJsonAsync<List<RatingReadDto>>($"/ratings/gallery/{galleryItemId}", cancellationToken, false)
                    .ConfigureAwait(true);
                if (list.Count == 0)
                    return new RatingSummary();
                return new RatingSummary
                {
                    Average = list.Average(r => r.Score),
                    Count = list.Count
                };
            }
            catch (ApiException)
            {
                return new RatingSummary();
            }
        }

        public async Task SubmitRatingAsync(string galleryItemId, int score1To10,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(galleryItemId, out var gid))
                throw new ArgumentException("Invalid gallery item id", nameof(galleryItemId));
            await _client
                .PostJsonAsync<RatingReadDto>("/ratings",
                    new { gallery_item_id = gid, score = score1To10 }, cancellationToken, useBearer: true)
                .ConfigureAwait(true);
        }
    }
}
