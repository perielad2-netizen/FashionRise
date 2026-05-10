using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class GalleryItem
    {
        public string Id { get; set; } = "";
        public string OwnerUserId { get; set; } = "";
        public string DesignId { get; set; } = "";
        public string Title { get; set; } = "";
        public string ThumbnailPlaceholderKey { get; set; } = "";
        public RatingSummary Rating { get; set; } = new();
        public int LikesCount { get; set; }
        public bool LikedByMe { get; set; }
    }
}
