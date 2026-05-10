using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Data;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockGarmentTemplateService : IGarmentTemplateService
    {
        private readonly IReadOnlyList<GarmentTemplate> _all = TemplateCatalogSeed.All;

        public Task<IReadOnlyList<GarmentTemplate>> GetTemplatesAsync(GarmentCategory? category,
            CancellationToken cancellationToken = default)
        {
            if (category == null)
                return Task.FromResult(_all);

            var list = _all.Where(t => t.Category == category.Value).ToArray();
            return Task.FromResult((IReadOnlyList<GarmentTemplate>)list);
        }

        public Task<GarmentTemplate?> GetByIdAsync(string id,
            CancellationToken cancellationToken = default)
        {
            GarmentTemplate? t = _all.FirstOrDefault(x => x.Id == id);
            return Task.FromResult<GarmentTemplate?>(t);
        }
    }
}
