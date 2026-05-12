using System.Text;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class ShareLinkService : IShareLinkService
    {
        readonly ApiConfig _config;

        public ShareLinkService(ApiConfig config) => _config = config;

        public string BuildGalleryItemUrl(string galleryItemId)
        {
            if (string.IsNullOrWhiteSpace(galleryItemId))
                return "";
            var web = _config.ShareWebBaseUrl?.Trim();
            if (!string.IsNullOrEmpty(web))
                return $"{web.TrimEnd('/')}/gallery/item/{galleryItemId.Trim()}";
            var scheme = string.IsNullOrWhiteSpace(_config.ShareUrlScheme)
                ? "fashionrise"
                : _config.ShareUrlScheme.Trim();
            return $"{scheme}://gallery/{galleryItemId.Trim()}";
        }

        public string BuildShareCardText(string title, string galleryItemId, string? previewImageUrl)
        {
            var url = BuildGalleryItemUrl(galleryItemId);
            var sb = new StringBuilder();
            var t = string.IsNullOrWhiteSpace(title) ? "FashionRise look" : title.Trim();
            sb.AppendLine(t);
            sb.AppendLine(url);
            if (!string.IsNullOrWhiteSpace(previewImageUrl))
                sb.AppendLine(previewImageUrl.Trim());
            return sb.ToString().TrimEnd();
        }
    }
}
