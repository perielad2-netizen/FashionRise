using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IColorPaletteService
    {
        Task<IReadOnlyList<ColorPalette>> GetPalettesAsync(
            CancellationToken cancellationToken = default);

        Task<ColorPalette?> GetByIdAsync(string id, CancellationToken cancellationToken = default);
    }
}
