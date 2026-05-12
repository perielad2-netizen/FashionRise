using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class DesignHandoffApiService : IDesignHandoffService
    {
        readonly ApiClient _client;

        public DesignHandoffApiService(ApiClient client) => _client = client;

        public async Task<string?> GetHandoffManifestJsonAsync(string designId,
            string exportKind = "manifest_v1",
            CancellationToken cancellationToken = default) =>
            await _client.GetRawJsonAsync($"/designs/{designId}/handoff?export_kind={exportKind}", cancellationToken,
                    true)
                .ConfigureAwait(false);
    }
}
