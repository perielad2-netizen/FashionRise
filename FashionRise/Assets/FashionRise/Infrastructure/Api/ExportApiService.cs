using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Infrastructure.Api
{
    public sealed class ExportApiService
    {
        readonly ApiClient _client;

        public ExportApiService(ApiClient client) => _client = client;

        public async Task<ExportReadDto> RegisterExportAsync(string designId, string exportType, string fileUrl,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var did))
                throw new ArgumentException("Invalid design id", nameof(designId));
            return await _client.PostJsonAsync<ExportReadDto>("/exports",
                    new
                    {
                        design_id = did,
                        export_type = exportType,
                        file_url = fileUrl,
                        metadata = new Dictionary<string, object>()
                    }, cancellationToken, useBearer: true)
                .ConfigureAwait(true);
        }

        public Task<List<ExportReadDto>> ListForDesignAsync(string designId,
            CancellationToken cancellationToken = default) =>
            _client.GetJsonAsync<List<ExportReadDto>>($"/exports/design/{designId}", cancellationToken, true);
    }
}
