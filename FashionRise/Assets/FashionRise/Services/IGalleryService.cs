using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IGalleryService
    {
        Task<IReadOnlyList<GalleryItem>> GetFeedAsync(GallerySort sort = GallerySort.Newest,
            CancellationToken cancellationToken = default);

        /// <summary>GET <c>/gallery/user/{owner_user_id}</c> — public posts by that account.</summary>
        Task<IReadOnlyList<GalleryItem>> GetUserPublicGalleryAsync(string ownerUserId,
            CancellationToken cancellationToken = default);

        Task<GalleryItem?> GetByIdAsync(string galleryItemId,
            CancellationToken cancellationToken = default);

        Task LikeAsync(string galleryItemId, CancellationToken cancellationToken = default);

        Task UnlikeAsync(string galleryItemId, CancellationToken cancellationToken = default);

        Task<IReadOnlyList<GalleryComment>> GetCommentsAsync(string galleryItemId,
            CancellationToken cancellationToken = default);

        Task<GalleryComment> PostCommentAsync(string galleryItemId, string body,
            CancellationToken cancellationToken = default);

        /// <summary>POST <c>/gallery</c> — publish your design (public). <paramref name="imageUrl"/> optional preview URL.</summary>
        Task<GalleryItem> PublishDesignAsync(string designId, string title, string? imageUrl,
            CancellationToken cancellationToken = default);
    }
}
