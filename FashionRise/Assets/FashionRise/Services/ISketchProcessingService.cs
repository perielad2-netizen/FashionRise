using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    /// <summary>[AI_READY] Sketch cleanup pipeline (backend: POST /ai/sketch/clean).</summary>
    public interface ISketchProcessingService
    {
        Task<SketchEnhancementResult> CleanAsync(SketchEnhancementRequest request,
            CancellationToken cancellationToken = default);
    }
}
