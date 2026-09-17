using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Services
{
    /// <summary>
    /// [AI_READY] Provider-agnostic sketch / concept enhancement jobs.
    /// </summary>
    public interface IAIEnhancementService
    {
        Task<string> EnqueueJobAsync(string designId, string jobType,
            CancellationToken cancellationToken = default);

        Task<string> GetJobStatusAsync(string jobId, CancellationToken cancellationToken = default);

        /// <summary>Multi-line detail from job <c>result_data</c> (OpenAI bullets, source line). Null if unavailable.</summary>
        Task<string?> GetJobStructuredDetailTextAsync(string jobId, CancellationToken cancellationToken = default);

        /// <summary>Public polished look URL from job <c>result_data.image_url</c>, if present.</summary>
        Task<string?> GetJobImageUrlAsync(string jobId, CancellationToken cancellationToken = default);
    }
}
