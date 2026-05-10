using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    /// <summary>[AI_READY] Style suggestions (POST /ai/style/suggest).</summary>
    public interface IStyleSuggestionService
    {
        Task<StyleVariationResult> SuggestAsync(StyleVariationRequest request,
            CancellationToken cancellationToken = default);
    }
}
