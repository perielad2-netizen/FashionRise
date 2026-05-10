using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class GalleryComment
    {
        public string Id { get; set; } = "";
        public string GalleryItemId { get; set; } = "";
        public string AuthorUserId { get; set; } = "";
        public string Body { get; set; } = "";
        public DateTime CreatedAtUtc { get; set; }
    }
}
