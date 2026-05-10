using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Data;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockColorPaletteService : IColorPaletteService
    {
        private readonly IReadOnlyList<ColorPalette> _all = PaletteCatalogSeed.All;

        public Task<IReadOnlyList<ColorPalette>> GetPalettesAsync(
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(_all);
        }

        public Task<ColorPalette?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default)
        {
            ColorPalette? p = _all.FirstOrDefault(x => x.Id == id);
            return Task.FromResult<ColorPalette?>(p);
        }
    }
}
