using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class TemplateApiService : IGarmentTemplateService
    {
        readonly ApiClient _client;

        public TemplateApiService(ApiClient client) => _client = client;

        public async Task<IReadOnlyList<GarmentTemplate>> GetTemplatesAsync(GarmentCategory? category,
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<GarmentTemplateReadDto>>("/templates", cancellationToken, useBearer: false)
                .ConfigureAwait(true);
            var mapped = list.Select(ApiDomainMapper.ToTemplate).ToList();
            if (category == null)
                return mapped;
            return mapped.Where(t => t.Category == category.Value).ToList();
        }

        public async Task<GarmentTemplate?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var t = await _client.GetJsonAsync<GarmentTemplateReadDto>($"/templates/{id}", cancellationToken, false)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToTemplate(t);
            }
            catch (ApiException)
            {
                return null;
            }
        }
    }
}
