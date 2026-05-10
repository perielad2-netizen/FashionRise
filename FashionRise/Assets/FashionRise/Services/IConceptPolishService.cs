using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    /// <summary>[AI_READY] Concept polish (POST /ai/sketch/polish).</summary>
    public interface IConceptPolishService
    {
        Task<ConceptRefinementResult> PolishAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default);
    }
}
