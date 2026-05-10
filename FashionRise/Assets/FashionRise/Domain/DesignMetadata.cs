using System;
using System.Collections.Generic;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class DesignMetadata
    {
        public string Title { get; set; } = "";
        public string Description { get; set; } = "";
        public IReadOnlyList<string> StyleTagIds { get; set; } = Array.Empty<string>();
        public DateTime CreatedAtUtc { get; set; }
        public DateTime? UpdatedAtUtc { get; set; }
    }
}
