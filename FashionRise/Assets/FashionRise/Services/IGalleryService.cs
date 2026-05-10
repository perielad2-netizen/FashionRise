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

        Task<GalleryItem?> GetByIdAsync(string galleryItemId,
            CancellationToken cancellationToken = default);

        Task LikeAsync(string galleryItemId, CancellationToken cancellationToken = default);

        Task UnlikeAsync(string galleryItemId, CancellationToken cancellationToken = default);

        Task<IReadOnlyList<GalleryComment>> GetCommentsAsync(string galleryItemId,
            CancellationToken cancellationToken = default);

        Task<GalleryComment> PostCommentAsync(string galleryItemId, string body,
            CancellationToken cancellationToken = default);
    }
}
