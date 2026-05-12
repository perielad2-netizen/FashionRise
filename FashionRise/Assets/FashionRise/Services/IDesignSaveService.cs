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

        /// <summary>POST <c>/designs/{id}/revisions</c> — owner snapshot (autosave / checkpoint).</summary>
        Task<int> AppendRevisionSnapshotAsync(string designId, GarmentDesign design, string? notes = null,
            CancellationToken cancellationToken = default);

        /// <summary>GET <c>/designs/{id}/revisions</c> — newest first.</summary>
        Task<IReadOnlyList<DesignRevisionSnapshot>> ListRevisionSnapshotsAsync(string designId,
            int limit = 30, int offset = 0, CancellationToken cancellationToken = default);

        /// <summary>GET <c>/designs/{id}/revisions/{n}</c> and apply <c>design_data</c> onto a base draft.</summary>
        Task<GarmentDesign?> ApplyRevisionToDesignAsync(string designId, int revisionNumber, GarmentDesign baseDesign,
            CancellationToken cancellationToken = default);
    }
}
