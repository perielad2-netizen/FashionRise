using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IMaterialCatalogService
    {
        Task<IReadOnlyList<MaterialDefinition>> GetMaterialsAsync(
            CancellationToken cancellationToken = default);

        Task<MaterialDefinition?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default);
    }
}
