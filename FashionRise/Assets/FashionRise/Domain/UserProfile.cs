using System;
using System.Collections.Generic;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class UserProfile
    {
        public string UserId { get; set; } = "";
        public string DisplayName { get; set; } = "";
        public string Bio { get; set; } = "";
        public bool IsPublic { get; set; } = true;
        public string PublicSlug { get; set; } = "";
        public IReadOnlyList<string> FeaturedDesignIds { get; set; } = Array.Empty<string>();
    }
}
