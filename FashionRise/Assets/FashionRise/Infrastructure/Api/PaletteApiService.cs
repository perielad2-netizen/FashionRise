using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    public sealed class PaletteApiService : IColorPaletteService
    {
        readonly ApiClient _client;

        public PaletteApiService(ApiClient client) => _client = client;

        public async Task<IReadOnlyList<ColorPalette>> GetPalettesAsync(
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<ColorPaletteReadDto>>("/palettes", cancellationToken, useBearer: false)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToPalette).ToList();
        }

        public async Task<ColorPalette?> GetByIdAsync(string id, CancellationToken cancellationToken = default)
        {
            var all = await GetPalettesAsync(cancellationToken).ConfigureAwait(true);
            return all.FirstOrDefault(p => p.Id == id);
        }
    }
}
