using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface IDesignSaveService
    {
        Task<GarmentDesign> SaveDraftAsync(GarmentDesign design,
            CancellationToken cancellationToken = default);

        Task<IReadOnlyList<GarmentDesign>> ListMyDesignsAsync(
            CancellationToken cancellationToken = default);

        Task<GarmentDesign?> GetDesignByIdAsync(string designId,
            CancellationToken cancellationToken = default);
    }
}
