using System;
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

        public Task<int> AppendRevisionSnapshotAsync(string designId, GarmentDesign design, string? notes = null,
            CancellationToken cancellationToken = default) =>
            Task.FromResult(1);

        public Task<IReadOnlyList<DesignRevisionSnapshot>> ListRevisionSnapshotsAsync(string designId,
            int limit = 30, int offset = 0, CancellationToken cancellationToken = default) =>
            Task.FromResult((IReadOnlyList<DesignRevisionSnapshot>)Array.Empty<DesignRevisionSnapshot>());

        public Task<GarmentDesign?> ApplyRevisionToDesignAsync(string designId, int revisionNumber, GarmentDesign baseDesign,
            CancellationToken cancellationToken = default) =>
            Task.FromResult<GarmentDesign?>(baseDesign);

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
