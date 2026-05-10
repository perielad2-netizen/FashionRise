using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Data;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockMaterialCatalogService : IMaterialCatalogService
    {
        private readonly IReadOnlyList<MaterialDefinition> _all = MaterialCatalogSeed.All;

        public Task<IReadOnlyList<MaterialDefinition>> GetMaterialsAsync(
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(_all);
        }

        public Task<MaterialDefinition?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default)
        {
            MaterialDefinition? m = _all.FirstOrDefault(x => x.Id == id);
            return Task.FromResult<MaterialDefinition?>(m);
        }
    }
}
