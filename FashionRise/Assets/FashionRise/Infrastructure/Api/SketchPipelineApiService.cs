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
        IStyleSuggestionService, IImageRefinementService, ITechPackService
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
            // Optional studio chips — backend folds these into the image edit prompt.
            if (!string.IsNullOrWhiteSpace(request.FabricName))
                inputData["fabric"] = request.FabricName.Trim();
            var regions = request.ColorRegions?.Trim() ?? "";
            if (!string.IsNullOrEmpty(regions))
                inputData["color_regions"] = regions;
            // A single palette colour reads as "paint everything this colour", so only send it
            // when the sketch really is one colour.
            if (!string.IsNullOrWhiteSpace(request.ColorName) && CountColorRegions(regions) <= 1)
                inputData["color"] = request.ColorName.Trim();
            if (!string.IsNullOrWhiteSpace(request.MaterialPairs))
                inputData["material_pairs"] = request.MaterialPairs.Trim();
            await EmbedVisionImageAsync(inputData, request.LocalSketchForVision, cancellationToken)
                .ConfigureAwait(true);
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/sketch/polish",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            try
            {
                request.OnJobStarted?.Invoke(job.Id.ToString());
            }
            catch (Exception callbackEx)
            {
                UnityEngine.Debug.LogWarning($"FashionRise OnJobStarted callback failed: {callbackEx.Message}");
            }

            try
            {
                var final = await WaitForJobCompletionAsync(_client, job.Id, cancellationToken)
                    .ConfigureAwait(true);
                return ToConcept(final);
            }
            catch (Exception ex)
            {
                // Job often finishes on the server even when a poll blip aborts the client wait.
                UnityEngine.Debug.LogWarning(
                    $"FashionRise polish wait interrupted for job {job.Id}: {ex.Message}. Trying recovery GET…");
                for (var recoveryAttempt = 0; recoveryAttempt < 5; recoveryAttempt++)
                {
                    try
                    {
                        if (recoveryAttempt > 0)
                            await Task.Delay(750 * recoveryAttempt, cancellationToken).ConfigureAwait(true);
                        var recovered = await _client
                            .GetJsonAsync<AIJobReadDto>($"/ai/jobs/{job.Id}", cancellationToken, true)
                            .ConfigureAwait(true);
                        if (string.Equals(recovered.Status, "completed", StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(recovered.Status, "failed", StringComparison.OrdinalIgnoreCase))
                            return ToConcept(recovered);
                    }
                    catch (Exception recoveryEx)
                    {
                        UnityEngine.Debug.LogWarning(
                            $"FashionRise polish recovery GET attempt {recoveryAttempt + 1} failed: {recoveryEx.Message}");
                    }
                }

                throw;
            }
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

        static int CountColorRegions(string regions)
        {
            if (string.IsNullOrWhiteSpace(regions))
                return 0;
            var n = 0;
            foreach (var part in regions.Split(';'))
                if (part.Split(',').Length >= 3)
                    n++;
            return n;
        }

        static Guid? TryGuid(string? id) =>
            string.IsNullOrEmpty(id) || !Guid.TryParse(id, out var g) ? null : g;

        static async Task<AIJobReadDto> WaitForJobCompletionAsync(ApiClient client, Guid jobId,
            CancellationToken cancellationToken)
        {
            const int delayMs = 500;
            // ~5 min — polish + gpt-image edit is often 45–90s; keep polling through transient HTTP blips
            const int maxAttempts = 600;
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
                catch (ApiException)
                {
                    // Transient HTTP blips during long image jobs — keep polling.
                }
                catch (System.Net.Http.HttpRequestException)
                {
                    // "An error occurred while sending the request" — common mid-Magic; retry.
                }
                catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
                {
                    // HttpClient timeout on a single poll — retry.
                }
                catch (Exception ex) when (!(ex is OperationCanceledException))
                {
                    // Unity / Mono sometimes wraps socket failures oddly — keep polling.
                    UnityEngine.Debug.LogWarning($"FashionRise AI poll blip: {ex.GetType().Name}: {ex.Message}");
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


        public async Task<TechPackResult> GenerateAsync(TechPackRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object>
            {
                ["notes"] = request.Notes ?? "",
                ["local_path_placeholder"] = request.LocalSketchForVision ?? ""
            };
            if (!string.IsNullOrWhiteSpace(request.FabricName))
                inputData["fabric"] = request.FabricName.Trim();
            if (!string.IsNullOrWhiteSpace(request.ColorName))
                inputData["color"] = request.ColorName.Trim();
            if (!string.IsNullOrWhiteSpace(request.MaterialPairs))
                inputData["material_pairs"] = request.MaterialPairs.Trim();
            if (!string.IsNullOrWhiteSpace(request.PolishedImageUrl))
                inputData["polished_image_url"] = request.PolishedImageUrl.Trim();
            await EmbedVisionImageAsync(inputData, request.LocalSketchForVision, cancellationToken)
                .ConfigureAwait(true);
            // Prefer polished look for vision when local sketch missing but URL is public
            if (!inputData.ContainsKey("image_base64") && !inputData.ContainsKey("image_url") &&
                !string.IsNullOrWhiteSpace(request.PolishedImageUrl))
                await EmbedVisionImageAsync(inputData, request.PolishedImageUrl, cancellationToken)
                    .ConfigureAwait(true);

            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/tech-pack",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            try { request.OnJobStarted?.Invoke(job.Id.ToString()); }
            catch (Exception callbackEx)
            {
                UnityEngine.Debug.LogWarning($"FashionRise TechPack OnJobStarted failed: {callbackEx.Message}");
            }

            var final = await WaitForJobCompletionAsync(_client, job.Id, cancellationToken).ConfigureAwait(true);
            return ToTechPack(final);
        }

        static TechPackResult ToTechPack(AIJobReadDto j)
        {
            var rd = j.ResultData;
            var front = AIJobApiService.ExtractImageUrl(rd) ?? "";
            var back = rd?.Value<string>("back_image_url") ?? "";
            var pattern = rd?.Value<string>("pattern_image_url") ?? "";
            var disclaimer = rd?.Value<string>("disclaimer") ?? "";
            return new TechPackResult
            {
                JobId = j.Id.ToString(),
                Status = j.Status,
                Summary = MessageFrom(j),
                Disclaimer = disclaimer,
                FrontImageUrl = front,
                BackImageUrl = back,
                PatternImageUrl = pattern,
                RawJson = rd != null ? rd.ToString(Newtonsoft.Json.Formatting.Indented) : "{}"
            };
        }

        static StyleVariationResult ToStyle(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };
    }
}
