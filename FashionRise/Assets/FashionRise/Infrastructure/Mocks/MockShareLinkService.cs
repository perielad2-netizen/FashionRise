using System.Text;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockShareLinkService : IShareLinkService
    {
        public string BuildGalleryItemUrl(string galleryItemId) =>
            string.IsNullOrWhiteSpace(galleryItemId)
                ? ""
                : $"https://mock.fashionrise.local/gallery/item/{galleryItemId.Trim()}";

        public string BuildShareCardText(string title, string galleryItemId, string? previewImageUrl)
        {
            var url = BuildGalleryItemUrl(galleryItemId);
            var sb = new StringBuilder();
            sb.AppendLine(string.IsNullOrWhiteSpace(title) ? "FashionRise look" : title.Trim());
            sb.AppendLine(url);
            if (!string.IsNullOrWhiteSpace(previewImageUrl))
                sb.AppendLine(previewImageUrl.Trim());
            return sb.ToString().TrimEnd();
        }
    }
}
