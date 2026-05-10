using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IGarmentTemplateService
    {
        Task<IReadOnlyList<GarmentTemplate>> GetTemplatesAsync(GarmentCategory? category,
            CancellationToken cancellationToken = default);

        Task<GarmentTemplate?> GetByIdAsync(string id, CancellationToken cancellationToken = default);
    }
}
