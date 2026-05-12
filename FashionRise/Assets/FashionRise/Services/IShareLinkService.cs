namespace FashionRise.Services
{
    /// <summary>Builds public or app-scheme URLs and shareable text for gallery items.</summary>
    public interface IShareLinkService
    {
        /// <summary>HTTPS when <c>ShareWebBaseUrl</c> is set on API config; otherwise <c>fashionrise://gallery/{id}</c> for future app links.</summary>
        string BuildGalleryItemUrl(string galleryItemId);

        /// <summary>Plain-text “card”: title, deep link, optional preview image URL (for rich previews in chat apps).</summary>
        string BuildShareCardText(string title, string galleryItemId, string? previewImageUrl);
    }
}
