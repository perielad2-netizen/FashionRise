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
            // Field names mirror backend tech_pack_openai so the Unity sheet renders identically offline.
            var json = @"{
  ""summary"": ""Fitted mermaid gown in duchess satin with sculptural puff sleeves and side balloon pods."",
  ""disclaimer"": ""Draft measurements — not final manufacturing specs."",
  ""garment"": {
    ""type"": ""Sculptural Mermaid Dress"",
    ""construction_description"": ""Fitted mermaid silhouette with deep V neckline, princess-seam body, structured puff sleeves tapering to a slim wrist, and dramatic side balloon pods at knee/calf level."",
    ""silhouette"": ""fitted mermaid"",
    ""neckline"": ""deep V"",
    ""sleeves"": ""sculptural puff tapering to slim wrist"",
    ""closure"": ""invisible centre back zipper""
  },
  ""measurements"": {
    ""sample_size"": ""EU 36 / US 4"",
    ""body"": { ""height_cm"": 170, ""bust_cm"": 84, ""waist_cm"": 64, ""hip_cm"": 90 },
    ""finished"": { ""bust_cm"": 88, ""waist_cm"": 66, ""hip_cm"": 94, ""shoulder_to_waist_cm"": 42, ""length_cm"": 128, ""sleeve_length_cm"": 60 }
  },
  ""materials"": [
    { ""name"": ""Duchess satin"", ""role"": ""shell"", ""recommendation"": ""Duchess satin or taffeta, 150 cm width"", ""quantity_m"": 6.0, ""notes"": ""Keep nap direction consistent"" },
    { ""name"": ""Polyester satin lining"", ""role"": ""lining"", ""recommendation"": ""Polyester satin or Bemberg"", ""quantity_m"": 3.0, ""notes"": ""Full lining"" },
    { ""name"": ""Organza / stiff tulle"", ""role"": ""structure"", ""recommendation"": ""For side pods, 150 cm width"", ""quantity_m"": 2.0, ""notes"": ""Pod volume support"" },
    { ""name"": ""Fusible interfacing"", ""role"": ""interfacing"", ""recommendation"": ""Medium weight"", ""quantity_m"": 0.7, ""notes"": ""Neckline and facings"" },
    { ""name"": ""Invisible zipper 60 cm"", ""role"": ""notion"", ""recommendation"": ""Colour matched to shell"", ""quantity_m"": null, ""notes"": ""Centre back"" },
    { ""name"": ""Horsehair braid"", ""role"": ""notion"", ""recommendation"": ""For hem and pod edge support"", ""quantity_m"": 3.0, ""notes"": ""Crinoline tape alternative"" }
  ],
  ""pattern_pieces"": [
    { ""name"": ""Front bodice"", ""qty"": 1, ""approx_w_cm"": 42, ""approx_h_cm"": 48, ""seam_allowance_cm"": 1.0, ""grainline"": ""parallel to CF"", ""on_fold"": true, ""notches"": [""bust"", ""waist""] },
    { ""name"": ""Back bodice"", ""qty"": 2, ""approx_w_cm"": 24, ""approx_h_cm"": 48, ""seam_allowance_cm"": 1.0, ""grainline"": ""parallel to CB"", ""on_fold"": false, ""notches"": [""shoulder"", ""waist"", ""zipper""] },
    { ""name"": ""Puff sleeve"", ""qty"": 2, ""approx_w_cm"": 56, ""approx_h_cm"": 62, ""seam_allowance_cm"": 1.0, ""grainline"": ""centre grain"", ""on_fold"": false, ""notches"": [""sleeve head"", ""underarm"", ""wrist gather""] },
    { ""name"": ""Skirt front"", ""qty"": 1, ""approx_w_cm"": 70, ""approx_h_cm"": 110, ""seam_allowance_cm"": 1.5, ""grainline"": ""parallel to CF"", ""on_fold"": true, ""notches"": [""hip"", ""knee flare""] },
    { ""name"": ""Skirt back"", ""qty"": 2, ""approx_w_cm"": 48, ""approx_h_cm"": 118, ""seam_allowance_cm"": 1.5, ""grainline"": ""parallel to CB"", ""on_fold"": false, ""notches"": [""hip"", ""walking slit""] },
    { ""name"": ""Balloon pod panel"", ""qty"": 4, ""approx_w_cm"": 46, ""approx_h_cm"": 52, ""seam_allowance_cm"": 1.0, ""grainline"": ""bias"", ""on_fold"": false, ""notches"": [""pod top"", ""pod base""] }
  ],
  ""construction_steps"": [
    ""Stay-stitch the neckline and stabilise the deep V with fusible tape."",
    ""Sew princess seams on front and back bodice; press toward centre."",
    ""Gather and set the puff sleeves; steam the sleeve head into shape."",
    ""Insert the invisible zipper at centre back through bodice and skirt."",
    ""Assemble skirt panels and attach to bodice at the waist seam."",
    ""Attach balloon pod panels at knee/calf level; support edges with horsehair braid."",
    ""Hem the skirt and finish the back walking slit; final press.""
  ],
  ""cutting_layout"": {
    ""fabric_width_cm"": 150,
    ""notes"": ""Lay shell single layer for pods to control bias; fold for CF and CB pieces marked on fold. Align grainlines to selvage."",
    ""efficiency_tip"": ""Nest the long skirt panels first, then bodice, sleeves and pods in the remaining bays.""
  },
  ""sections"": [""design"",""measurements"",""pattern"",""cutting"",""materials"",""construction""]
}";
            return Task.FromResult(new TechPackResult
            {
                JobId = Guid.NewGuid().ToString("N"),
                Status = "completed",
                Summary = "Sculptural Mermaid Dress — first production draft.",
                Disclaimer = "Draft measurements — not final manufacturing specs.",
                RawJson = json
            });
        }
    }
}
