using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockDesignSaveService : IDesignSaveService
    {
        private readonly List<GarmentDesign> _designs = new();

        public Task<GarmentDesign> SaveDraftAsync(GarmentDesign design,
            CancellationToken cancellationToken = default)
        {
            _designs.RemoveAll(d => d.Id == design.Id);
            _designs.Insert(0, design);
            return Task.FromResult(design);
        }

        public Task<IReadOnlyList<GarmentDesign>> ListMyDesignsAsync(
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult((IReadOnlyList<GarmentDesign>)_designs.ToArray());
        }

        public Task<GarmentDesign?> GetDesignByIdAsync(string designId,
            CancellationToken cancellationToken = default)
        {
            GarmentDesign? d = _designs.FirstOrDefault(x => x.Id == designId);
            return Task.FromResult<GarmentDesign?>(d);
        }
    }
}
