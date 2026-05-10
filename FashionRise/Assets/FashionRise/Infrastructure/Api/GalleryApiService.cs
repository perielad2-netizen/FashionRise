using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class GalleryApiService : IGalleryService
    {
        readonly ApiClient _client;

        public GalleryApiService(ApiClient client) => _client = client;

        static string SortParam(GallerySort sort) =>
            sort switch
            {
                GallerySort.TopRated => "top_rated",
                GallerySort.Trending => "trending",
                _ => "newest"
            };

        public async Task<IReadOnlyList<GalleryItem>> GetFeedAsync(GallerySort sort = GallerySort.Newest,
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<GalleryReadDto>>($"/gallery?sort={SortParam(sort)}", cancellationToken,
                    useBearer: false)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToGalleryItem).ToList();
        }

        public async Task<GalleryItem?> GetByIdAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var g = await _client
                    .GetJsonAsync<GalleryReadDto>($"/gallery/{galleryItemId}", cancellationToken, true)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToGalleryItem(g);
            }
            catch (ApiException)
            {
                return null;
            }
        }

        public Task LikeAsync(string galleryItemId, CancellationToken cancellationToken = default) =>
            _client.PostExpectNoContentAsync($"/gallery/{galleryItemId}/like", new { }, cancellationToken, true);

        public Task UnlikeAsync(string galleryItemId, CancellationToken cancellationToken = default) =>
            _client.DeleteAsync($"/gallery/{galleryItemId}/like", cancellationToken, true);

        public async Task<IReadOnlyList<GalleryComment>> GetCommentsAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<GalleryCommentReadDto>>($"/gallery/{galleryItemId}/comments",
                    cancellationToken, false)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToGalleryComment).ToList();
        }

        public async Task<GalleryComment> PostCommentAsync(string galleryItemId, string body,
            CancellationToken cancellationToken = default)
        {
            var c = await _client
                .PostJsonAsync<GalleryCommentReadDto>($"/gallery/{galleryItemId}/comments", new { body },
                    cancellationToken, true)
                .ConfigureAwait(true);
            return ApiDomainMapper.ToGalleryComment(c);
        }
    }
}
