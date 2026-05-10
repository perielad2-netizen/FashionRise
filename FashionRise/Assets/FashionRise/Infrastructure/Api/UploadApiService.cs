using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Infrastructure.Api
{
    public sealed class UploadApiService
    {
        readonly ApiClient _client;

        public UploadApiService(ApiClient client) => _client = client;

        public async Task<string> UploadImageAsync(byte[] pngBytes, string fileName,
            CancellationToken cancellationToken = default)
        {
            var safe = string.IsNullOrWhiteSpace(fileName) ? "upload.png" : Path.GetFileName(fileName);
            if (!safe.EndsWith(".png", System.StringComparison.OrdinalIgnoreCase))
                safe += ".png";
            var resp = await _client
                .PostMultipartImageAsync<ImageUploadResponseDto>("/uploads/image", pngBytes, safe, "image/png",
                    cancellationToken)
                .ConfigureAwait(true);
            return resp.Url;
        }
    }
}
