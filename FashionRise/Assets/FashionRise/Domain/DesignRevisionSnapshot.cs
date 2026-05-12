using System;

namespace FashionRise.Domain
{
    /// <summary>Lightweight row from <c>GET /designs/{id}/revisions</c> for history UI.</summary>
    [Serializable]
    public sealed class DesignRevisionSnapshot
    {
        public string Id { get; set; } = "";
        public string DesignId { get; set; } = "";
        public int RevisionNumber { get; set; }
        public string? Notes { get; set; }
        public DateTime CreatedAtUtc { get; set; }
    }
}
