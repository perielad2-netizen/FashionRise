using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class DesignApiService : IDesignSaveService
    {
        readonly ApiClient _client;

        public DesignApiService(ApiClient client) => _client = client;

        public async Task<GarmentDesign> SaveDraftAsync(GarmentDesign design,
            CancellationToken cancellationToken = default)
        {
            if (ApiDomainMapper.LooksLikeClientGeneratedDesignId(design.Id))
            {
                var created = await _client
                    .PostJsonAsync<DesignReadDto>("/designs", ApiDomainMapper.ToDesignCreateBody(design),
                        cancellationToken, useBearer: true)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToGarmentDesign(created);
            }

            if (!Guid.TryParse(design.Id, out var gid))
            {
                var created = await _client
                    .PostJsonAsync<DesignReadDto>("/designs", ApiDomainMapper.ToDesignCreateBody(design),
                        cancellationToken, useBearer: true)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToGarmentDesign(created);
            }

            var updated = await _client
                .PutJsonAsync<DesignReadDto>($"/designs/{gid}", ApiDomainMapper.ToDesignUpdateBody(design),
                    cancellationToken, useBearer: true)
                .ConfigureAwait(true);
            return ApiDomainMapper.ToGarmentDesign(updated);
        }

        public async Task<IReadOnlyList<GarmentDesign>> ListMyDesignsAsync(
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<DesignReadDto>>("/designs/my", cancellationToken, useBearer: true)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToGarmentDesign).ToList();
        }

        public async Task<GarmentDesign?> GetDesignByIdAsync(string designId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                return null;
            try
            {
                var d = await _client.GetJsonAsync<DesignReadDto>($"/designs/{gid}", cancellationToken, true)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToGarmentDesign(d);
            }
            catch (ApiException)
            {
                return null;
            }
        }
    }
}
