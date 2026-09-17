using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    /// <summary>Offline sketch/style pipeline — returns completed placeholder jobs. [AI_READY]</summary>
    public sealed class MockSketchPipelineService : ISketchProcessingService, IConceptPolishService,
        IStyleSuggestionService, IImageRefinementService, ITechPackService
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

        public Task<TechPackResult> GenerateAsync(TechPackRequest request,
            CancellationToken cancellationToken = default)
        {
            var json = @"{
  ""summary"": ""Mock tech pack — Sculptural Mermaid Dress draft."",
  ""disclaimer"": ""Draft measurements — not final manufacturing specs."",
  ""garment"": { ""type"": ""Sculptural Mermaid Dress"", ""construction_description"": ""Fitted mermaid with puff sleeves and side balloon pods."" },
  ""measurements"": {
    ""sample_size"": ""EU 36 / US 4"",
    ""body"": { ""height_cm"": 170, ""bust_cm"": 84, ""waist_cm"": 64, ""hip_cm"": 90 },
    ""finished"": { ""bust_cm"": 88, ""waist_cm"": 66, ""hip_cm"": 94, ""length_cm"": 155 }
  },
  ""materials"": [
    { ""name"": ""Duchess satin"", ""role"": ""shell"", ""quantity_m"": 3.2 },
    { ""name"": ""Organza"", ""role"": ""structure"", ""quantity_m"": 1.5 },
    { ""name"": ""Invisible zipper 60cm"", ""role"": ""notion"", ""quantity_m"": null }
  ],
  ""pattern_pieces"": [
    { ""name"": ""Front bodice"", ""qty"": 1, ""width_cm"": 42, ""height_cm"": 48, ""seam_allowance_cm"": 1.0 },
    { ""name"": ""Back bodice"", ""qty"": 2, ""width_cm"": 24, ""height_cm"": 48, ""seam_allowance_cm"": 1.0 },
    { ""name"": ""Skirt front"", ""qty"": 1, ""width_cm"": 70, ""height_cm"": 110, ""seam_allowance_cm"": 1.5 }
  ],
  ""construction_steps"": [
    ""Stay-stitch neckline and stabilize V."",
    ""Set puff sleeves; gather and steam."",
    ""Insert invisible CB zipper."",
    ""Attach balloon pod panels; pad lightly."",
    ""Hem with horsehair tape; final press.""
  ],
  ""cutting_layout"": { ""fabric_width_cm"": 150, ""notes"": ""Place grain parallel to CB; nest pods efficiently."" },
  ""sections"": [""design"",""measurements"",""pattern"",""cutting"",""materials"",""construction""]
}";
            return Task.FromResult(new TechPackResult
            {
                JobId = Guid.NewGuid().ToString("N"),
                Status = "completed",
                Summary = "Mock tech pack — Sculptural Mermaid Dress draft.",
                Disclaimer = "Draft measurements — not final manufacturing specs.",
                RawJson = json
            });
        }
    }
}
