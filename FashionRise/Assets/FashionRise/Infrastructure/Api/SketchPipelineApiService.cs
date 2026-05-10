using System;
using System.Collections.Generic;
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
                ["local_path_placeholder"] = request.Input.LocalImagePathPlaceholder
            };
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/sketch/clean",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            return ToEnhance(job);
        }

        public async Task<ConceptRefinementResult> PolishAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object> { ["notes"] = request.Notes };
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/sketch/polish",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            return ToConcept(job);
        }

        public async Task<StyleVariationResult> SuggestAsync(StyleVariationRequest request,
            CancellationToken cancellationToken = default)
        {
            var inputData = new Dictionary<string, object> { ["mood_notes"] = request.MoodNotes };
            var job = await _client
                .PostJsonAsync<AIJobReadDto>("/ai/style/suggest",
                    new { design_id = TryGuid(request.DesignId), input_data = inputData }, cancellationToken, true)
                .ConfigureAwait(true);
            return ToStyle(job);
        }

        public Task<ConceptRefinementResult> RefineAsync(ConceptRefinementRequest request,
            CancellationToken cancellationToken = default) =>
            PolishAsync(request, cancellationToken);

        static Guid? TryGuid(string? id) =>
            string.IsNullOrEmpty(id) || !Guid.TryParse(id, out var g) ? null : g;

        static string MessageFrom(AIJobReadDto j)
        {
            if (j.ResultData == null)
                return j.Status;
            return j.ResultData.Value<string>("message") ?? j.Status;
        }

        static SketchEnhancementResult ToEnhance(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };

        static ConceptRefinementResult ToConcept(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };

        static StyleVariationResult ToStyle(AIJobReadDto j) =>
            new() { JobId = j.Id.ToString(), Status = j.Status, Summary = MessageFrom(j) };
    }
}
