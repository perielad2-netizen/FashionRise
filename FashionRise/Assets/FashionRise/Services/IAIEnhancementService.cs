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
    }
}
