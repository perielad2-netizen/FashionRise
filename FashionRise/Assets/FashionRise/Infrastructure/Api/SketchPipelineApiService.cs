using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>Maps V2 sketch/style routes to AI job responses. [AI_READY]</summary>
    public sealed class SketchPipelineApiService : ISketchProcessingService, IConceptPolishService,
        IStyleSuggestionService, IImageRefinementService
    {
        readonly ApiClient _client;

        public SketchPipelineApiService(ApiClient client) => _client = client;

        public async Task<SketchEnhancementResult> CleanAsync(SketchEnhancementRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object>
            {
                ["notes"] = request.Input.Notes,
                ["local_path_placeholder"] = request.Input.LocalImagePathPlaceholder ?? ""
            };
            await EmbedVisionImageAsync(inputData, request.Input.LocalImagePathPlaceholder, cancellationToken)
                .ConfigureAwait(true);
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/sketch/clean",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            var final = await WaitForJobCompletionAsync(_client, job.Id, cancellationToken).ConfigureAwait(true);
            return ToEnhance(final);
        }

        public async Task<ConceptRefinementResult> PolishAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object>
            {
                ["notes"] = request.Notes,
                ["local_path_placeholder"] = request.LocalSketchForVision ?? ""
            };
            await EmbedVisionImageAsync(inputData, request.LocalSketchForVision, cancellationToken)
                .ConfigureAwait(true);
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/sketch/polish",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            var final = await WaitForJobCompletionAsync(_client, job.Id, cancellationToken).ConfigureAwait(true);
            return ToConcept(final);
        }

        public async Task<StyleVariationResult> SuggestAsync(StyleVariationRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object> { ["mood_notes"] = request.MoodNotes };
            if (!string.IsNullOrWhiteSpace(request.LocalSketchForVision))
                inputData["local_path_placeholder"] = request.LocalSketchForVision;
            await EmbedVisionImageAsync(inputData, request.LocalSketchForVision, cancellationToken)
                .ConfigureAwait(true);
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/style/suggest",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            var final = await WaitForJobCompletionAsync(_client, job.Id, cancellationToken).ConfigureAwait(true);
            return ToStyle(final);
        }

        public Task<ConceptRefinementResult> RefineAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) =>
            PolishAsync(request, cancellationToken);

        /// <summary>
        /// Adds <c>image_url</c> (public HTTP only) or <c>image_base64</c> (data URL) so the worker can call OpenAI vision.
        /// Localhost URLs are skipped (OpenAI cannot fetch them); local files become data URLs.
        /// </summary>
        static async Task EmbedVisionImageAsync(Dictionary<string, object> inputData, string? sketchRef,
            CancellationToken cancellationToken)
        {
            if (string.IsNullOrWhiteSpace(sketchRef))
                return;
            var t = sketchRef.Trim();
            if (t.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                t.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                if (!IsLoopbackOrUnresolvedForOpenAi(t))
                    inputData["image_url"] = t;
                return;
            }

            if (t.StartsWith("job:", StringComparison.OrdinalIgnoreCase))
                return;

            string? path = null;
            try
            {
                if (t.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
                    path = new Uri(t).LocalPath;
                else if (File.Exists(t))
                    path = t;
            }
            catch
            {
                /* ignore */
            }

            if (path == null || !File.Exists(path))
                return;

            var bytes = await File.ReadAllBytesAsync(path, cancellationToken).ConfigureAwait(true);
            var ext = Path.GetExtension(path).ToLowerInvariant();
            var mime = ext is ".jpg" or ".jpeg" ? "image/jpeg" : ext == ".webp" ? "image/webp" : "image/png";
            var b64 = Convert.ToBase64String(bytes);
            inputData["image_base64"] = $"data:{mime};base64,{b64}";
        }

        static bool IsLoopbackOrUnresolvedForOpenAi(string url)
        {
            try
            {
                var u = new Uri(url, UriKind.Absolute);
                if (u.Host == "localhost" || u.Host == "127.0.0.1")
                    return true;
                if (IPAddress.TryParse(u.Host, out var ip) && IPAddress.IsLoopback(ip))
                    return true;
            }
            catch
            {
                return true;
            }

            return false;
        }

        static Guid? TryGuid(string? id) =>
            string.IsNullOrEmpty(id) || !Guid.TryParse(id, out var g) ? null : g;

        static async Task<AIJobReadDto> WaitForJobCompletionAsync(ApiClient client, Guid jobId,
            CancellationToken cancellationToken)
        {
            const int delayMs = 500;
            const int maxAttempts = 480; // ~4 min — polish + DALL·E can be slow
            for (var attempt = 0; attempt < maxAttempts; attempt++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    var j = await client.GetJsonAsync<AIJobReadDto>($"/ai/jobs/{jobId}", cancellationToken, true)
                        .ConfigureAwait(true);
                    if (string.Equals(j.Status, "completed", StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(j.Status, "failed", StringComparison.OrdinalIgnoreCase))
                        return j;
                }
                catch (ApiException ex) when (ex.IsRateLimited)
                {
                    throw new ApiException(ex.StatusCode,
                        "Rate limited while polling the AI job. Wait briefly and retry, or avoid many parallel sketch runs from the same network.",
                        ex.ResponseBody, ex);
                }

                await Task.Delay(delayMs, cancellationToken).ConfigureAwait(true);
            }

            throw new ApiException(0,
                "AI job timed out while waiting for completion. Check that the API worker is running (in-process loop or enable AI_WORKER_ENABLED).");
        }

        static string MessageFrom(AIJobReadDto j)
        {
            if (string.Equals(j.Status, "failed", StringComparison.OrdinalIgnoreCase))
                return string.IsNullOrEmpty(j.ErrorMessage) ? "failed" : j.ErrorMessage;
            if (j.ResultData == null)
                return j.Status;
            var summary = j.ResultData.Value<string>("summary");
            if (!string.IsNullOrEmpty(summary))
                return summary;
            return j.ResultData.Value<string>("message") ?? j.Status;
        }

        static SketchEnhancementResult ToEnhance(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };

        static ConceptRefinementResult ToConcept(AIJobReadDto j)
        {
            var imageUrl = AIJobApiService.ExtractImageUrl(j.ResultData) ?? "";
            if (!string.IsNullOrEmpty(imageUrl))
                UnityEngine.Debug.Log($"FashionRise polish job {j.Id}: image_url={imageUrl}");
            else if (j.ResultData != null)
                UnityEngine.Debug.LogWarning(
                    $"FashionRise polish job {j.Id}: completed but no image_url in result_data keys=[{string.Join(",", j.ResultData.Properties().Select(p => p.Name))}]");
            return new ConceptRefinementResult
            {
                JobId = j.Id.ToString(),
                Status = j.Status,
                Summary = MessageFrom(j),
                ImageUrl = imageUrl
            };
        }

        static StyleVariationResult ToStyle(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };
    }
}
