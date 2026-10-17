using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockAIEnhancementService : IAIEnhancementService
    {
        private readonly ConcurrentDictionary<string, string> _jobs = new();

        public Task<string> EnqueueJobAsync(string designId, string jobType,
            CancellationToken cancellationToken = default)
        {
            var id = "job_" + Guid.NewGuid().ToString("N")[..12];
            _jobs[id] = "queued";
            _jobs[id] = "completed";
            return Task.FromResult(id);
        }

        public Task<string> GetJobStatusAsync(string jobId, CancellationToken cancellationToken = default)
        {
            _jobs.TryGetValue(jobId, out var s);
            return Task.FromResult(s ?? "unknown");
        }

        public Task<string?> GetJobStructuredDetailTextAsync(string jobId,
            CancellationToken cancellationToken = default) =>
            Task.FromResult<string?>(null);

        public Task<string?> GetJobImageUrlAsync(string jobId,
            CancellationToken cancellationToken = default) =>
            Task.FromResult<string?>(null);
    }
}
