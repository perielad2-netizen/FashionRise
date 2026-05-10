using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class MaterialApiService : IMaterialCatalogService
    {
        readonly ApiClient _client;

        public MaterialApiService(ApiClient client) => _client = client;

        public async Task<IReadOnlyList<MaterialDefinition>> GetMaterialsAsync(
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<MaterialReadDto>>("/materials", cancellationToken, useBearer: false)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToMaterial).ToList();
        }

        public async Task<MaterialDefinition?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var m = await _client.GetJsonAsync<MaterialReadDto>($"/materials/{id}", cancellationToken, false)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToMaterial(m);
            }
            catch (ApiException)
            {
                return null;
            }
        }
    }
}
