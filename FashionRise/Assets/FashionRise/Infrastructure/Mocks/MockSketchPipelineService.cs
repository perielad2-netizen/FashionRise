using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    /// <summary>Offline sketch/style pipeline — returns completed placeholder jobs. [AI_READY]</summary>
    public sealed class MockSketchPipelineService : ISketchProcessingService, IConceptPolishService,
        IStyleSuggestionService, IImageRefinementService
    {
        public Task<SketchEnhancementResult> CleanAsync(SketchEnhancementRequest request,
            CancellationToken cancellationToken = default) =>
            Task.FromResult(new SketchEnhancementResult
            {
                JobId = Guid.NewGuid().ToString("N"),
                Status = "completed",
                Summary = "Mock sketch cleanup — wire a real provider later."
            });

        public Task<ConceptRefinementResult> PolishAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) =>
            Task.FromResult(new ConceptRefinementResult
            {
                JobId = Guid.NewGuid().ToString("N"),
                Status = "completed",
                Summary = "Mock concept polish — placeholder result."
            });

        public Task<StyleVariationResult> SuggestAsync(StyleVariationRequest request,
            CancellationToken cancellationToken = default) =>
            Task.FromResult(new StyleVariationResult
            {
                JobId = Guid.NewGuid().ToString("N"),
                Status = "completed",
                Summary = "Mock style suggestions — placeholder result."
            });

        public Task<ConceptRefinementResult> RefineAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) => PolishAsync(request, cancellationToken);
    }
}
