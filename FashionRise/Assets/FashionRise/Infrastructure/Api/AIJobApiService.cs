using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace FashionRise.Infrastructure.Api
{
    public sealed class AIJobApiService : FashionRise.Services.IAIEnhancementService
    {
        readonly ApiClient _client;

        public AIJobApiService(ApiClient client) => _client = client;

        public async Task<string> EnqueueJobAsync(string designId, string jobType,
            CancellationToken cancellationToken = default)
        {
            Guid? did = string.IsNullOrEmpty(designId) ? null : Guid.TryParse(designId, out var g) ? g : null;
            var job = await _client.PostJsonAsync<AIJobReadDto>("/ai/jobs",
                    new { design_id = did, job_type = jobType, input_data = new Dictionary<string, object>() },
                    cancellationToken, useBearer: true)
                .ConfigureAwait(true);
            return job.Id.ToString();
        }

        public async Task<string> GetJobStatusAsync(string jobId, CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(jobId, out var jid))
                return "invalid_job_id";
            var job = await _client.GetJsonAsync<AIJobReadDto>($"/ai/jobs/{jid}", cancellationToken, true)
                .ConfigureAwait(true);
            return job.Status;
        }

        public async Task<string?> GetJobStructuredDetailTextAsync(string jobId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(jobId, out var jid))
                return null;
            var job = await _client.GetJsonAsync<AIJobReadDto>($"/ai/jobs/{jid}", cancellationToken, true)
                .ConfigureAwait(true);
            return AiJobResultFormatter.FormatJobBody(job.Status, job.ResultData, job.ErrorMessage);
        }

        public async Task<string?> GetJobImageUrlAsync(string jobId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(jobId, out var jid))
                return null;
            var job = await _client.GetJsonAsync<AIJobReadDto>($"/ai/jobs/{jid}", cancellationToken, true)
                .ConfigureAwait(true);
            return ExtractImageUrl(job.ResultData);
        }

        internal static string? ExtractImageUrl(Newtonsoft.Json.Linq.JObject? resultData)
        {
            if (resultData == null || resultData.Count == 0)
                return null;
            var url = resultData.Value<string>("image_url")?.Trim()
                      ?? resultData.Value<string>("imageUrl")?.Trim();
            return string.IsNullOrEmpty(url) ? null : url;
        }
    }
}
