using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Infrastructure.Mocks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// Calls FastAPI sketch routes when <see cref="IAuthService.HasBackendSession"/>; otherwise local mocks (offline / mock backend).
    /// </summary>
    public sealed class TokenAwareSketchPipelineService : ISketchProcessingService, IConceptPolishService,
        IStyleSuggestionService, IImageRefinementService
    {
        readonly IAuthService _auth;
        readonly SketchPipelineApiService _api;
        readonly MockSketchPipelineService _mock = new();

        public TokenAwareSketchPipelineService(IAuthService auth, SketchPipelineApiService api)
        {
            _auth = auth;
            _api = api;
        }

        public Task<SketchEnhancementResult> CleanAsync(SketchEnhancementRequest request,
            CancellationToken cancellationToken = default) =>
            _auth.HasBackendSession
                ? _api.CleanAsync(request, cancellationToken)
                : _mock.CleanAsync(request, cancellationToken);

        public Task<ConceptRefinementResult> PolishAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) =>
            _auth.HasBackendSession
                ? _api.PolishAsync(request, cancellationToken)
                : _mock.PolishAsync(request, cancellationToken);

        public Task<StyleVariationResult> SuggestAsync(StyleVariationRequest request,
            CancellationToken cancellationToken = default) =>
            _auth.HasBackendSession
                ? _api.SuggestAsync(request, cancellationToken)
                : _mock.SuggestAsync(request, cancellationToken);

        public Task<ConceptRefinementResult> RefineAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) =>
            _auth.HasBackendSession
                ? _api.RefineAsync(request, cancellationToken)
                : _mock.RefineAsync(request, cancellationToken);
    }
}
