using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    /// <summary>[AI_READY] Image refinement placeholder — maps to polish pipeline until a dedicated route exists.</summary>
    public interface IImageRefinementService
    {
        Task<ConceptRefinementResult> RefineAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default);
    }
}
