using FashionRise.Domain;

namespace FashionRise.Core.Navigation
{
    /// <summary>Optional payload for <see cref="ScreenId.Gallery"/> — creator filter and/or initial community sort.</summary>
    public sealed class GalleryNavContext
    {
        /// <summary>When set, loads <c>GET /gallery/user/{id}</c> instead of the global feed.</summary>
        public string OwnerUserId { get; set; } = "";

        /// <summary>When <see cref="OwnerUserId"/> is empty, opens the community feed with this sort (e.g. <see cref="GallerySort.Following"/>).</summary>
        public GallerySort? CommunitySort { get; set; }
    }
}
