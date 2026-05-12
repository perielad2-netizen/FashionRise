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
                GallerySort.Following => "following",
                _ => "newest"
            };

        public async Task<IReadOnlyList<GalleryItem>> GetFeedAsync(GallerySort sort = GallerySort.Newest,
            CancellationToken cancellationToken = default)
        {
            var useBearer = sort == GallerySort.Following;
            var list = await _client
                .GetJsonAsync<List<GalleryReadDto>>($"/gallery?sort={SortParam(sort)}", cancellationToken,
                    useBearer)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToGalleryItem).ToList();
        }

        public async Task<IReadOnlyList<GalleryItem>> GetUserPublicGalleryAsync(string ownerUserId,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(ownerUserId) || !Guid.TryParse(ownerUserId.Trim(), out var uid))
                return Array.Empty<GalleryItem>();
            var list = await _client
                .GetJsonAsync<List<GalleryReadDto>>($"/gallery/user/{uid:D}", cancellationToken, false)
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

        public async Task<GalleryItem> PublishDesignAsync(string designId, string title, string? imageUrl,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                throw new ArgumentException("designId must be a server design UUID.", nameof(designId));
            var t = string.IsNullOrWhiteSpace(title) ? "Untitled" : title.Trim();
            if (t.Length > 300)
                t = t.Substring(0, 300);
            var body = new
            {
                design_id = gid,
                title = t,
                image_url = imageUrl,
                visibility = "public"
            };
            var dto = await _client
                .PostJsonAsync<GalleryReadDto>("/gallery", body, cancellationToken, true)
                .ConfigureAwait(true);
            return ApiDomainMapper.ToGalleryItem(dto);
        }
    }
}
