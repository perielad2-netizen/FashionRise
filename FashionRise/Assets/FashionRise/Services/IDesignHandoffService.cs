using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Services
{
    /// <summary>Maker / atelier handoff bundle (JSON manifest).</summary>
    public interface IDesignHandoffService
    {
        /// <param name="exportKind">
        /// Server handoff variant: <c>manifest_v1</c>, <c>spec_sheet_v1</c>, <c>spec_sheet_pdf</c>.
        /// </param>
        Task<string?> GetHandoffManifestJsonAsync(string designId, string exportKind = "manifest_v1",
            CancellationToken cancellationToken = default);
    }
}
