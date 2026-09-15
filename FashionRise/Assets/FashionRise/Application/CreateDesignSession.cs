using System;
using FashionRise.Domain;

namespace FashionRise.Application
{
    /// <summary>
    /// Authoring state for the create-design flow. [API_READY] Serialize to backend design_data JSON.
    /// </summary>
    public sealed class CreateDesignSession
    {
        public GarmentCategory Category { get; set; } = GarmentCategory.Dress;
        public string TemplateId { get; set; } = "";
        public NecklineType Neckline { get; set; } = NecklineType.VNeck;
        public SleeveType Sleeve { get; set; } = SleeveType.Long;
        public GarmentLength Length { get; set; } = GarmentLength.Midi;
        public FitStyle Fit { get; set; } = FitStyle.Tailored;
        public WaistStyle Waist { get; set; } = WaistStyle.Natural;
        public string ColorPaletteId { get; set; } = "";
        public string MaterialId { get; set; } = "";
        public SilhouetteVolume SilhouetteVolume { get; set; } = SilhouetteVolume.Balanced;
        public DrapeExpression DrapeExpression { get; set; } = DrapeExpression.Fluid;
        public LayeringDepth LayeringDepth { get; set; } = LayeringDepth.None;
        public SeamAccentStyle SeamAccent { get; set; } = SeamAccentStyle.Minimal;
        public string TrimNotes { get; set; } = "";
        public string AccentNotes { get; set; } = "";
        public string SketchReference { get; set; } = "";
        /// <summary>Absolute path to an image to load as trace reference on the sketch canvas; cleared after load.</summary>
        public string PendingReferenceImagePath { get; set; } = "";
        /// <summary>Fabric chip chosen on the sketch studio (e.g. Silk) — sent into Magic notes.</summary>
        public string SketchFabricName { get; set; } = "";
        /// <summary>Last ink/color name chosen on the sketch studio (e.g. Rose).</summary>
        public string SketchColorName { get; set; } = "";
        public string LastSketchJobId { get; set; } = "";
        public string LastSketchSummary { get; set; } = "";
        /// <summary>Public HTTP URL of the last Magic polish look image (if any).</summary>
        public string LastPolishedImageUrl { get; set; } = "";
        /// <summary>Local cache of the polished image for Share (downloaded from <see cref="LastPolishedImageUrl"/>).</summary>
        public string LastPolishedImageLocalPath { get; set; } = "";
        /// <summary>After a successful API save, reuse this id so the next save updates the same row.</summary>
        public string PersistedDesignId { get; set; } = "";

        /// <summary>Clears the last Magic look so the kid loop can start a fresh polish.</summary>
        public void ClearLastLook()
        {
            LastSketchJobId = "";
            LastSketchSummary = "";
            LastPolishedImageUrl = "";
            LastPolishedImageLocalPath = "";
        }

        public void Reset()
        {
            Category = GarmentCategory.Dress;
            TemplateId = "";
            Neckline = NecklineType.VNeck;
            Sleeve = SleeveType.Long;
            Length = GarmentLength.Midi;
            Fit = FitStyle.Tailored;
            Waist = WaistStyle.Natural;
            ColorPaletteId = "";
            MaterialId = "";
            SilhouetteVolume = SilhouetteVolume.Balanced;
            DrapeExpression = DrapeExpression.Fluid;
            LayeringDepth = LayeringDepth.None;
            SeamAccent = SeamAccentStyle.Minimal;
            TrimNotes = "";
            AccentNotes = "";
            SketchReference = "";
            PendingReferenceImagePath = "";
            SketchFabricName = "";
            SketchColorName = "";
            ClearLastLook();
            PersistedDesignId = "";
        }

        public GarmentDesign ToDraft(string ownerUserId, string title)
        {
            var id = string.IsNullOrEmpty(PersistedDesignId)
                ? Guid.NewGuid().ToString("N")
                : PersistedDesignId;
            return new GarmentDesign
            {
                Id = id,
                OwnerUserId = ownerUserId,
                Category = Category,
                TemplateId = TemplateId,
                Neckline = Neckline,
                Sleeve = Sleeve,
                Length = Length,
                Fit = Fit,
                Waist = Waist,
                ColorPaletteId = ColorPaletteId,
                MaterialId = MaterialId,
                Status = "draft",
                SilhouetteVolume = SilhouetteVolume,
                DrapeExpression = DrapeExpression,
                LayeringDepth = LayeringDepth,
                SeamAccent = SeamAccent,
                TrimNotes = TrimNotes,
                AccentNotes = AccentNotes,
                SketchReference = SketchReference,
                Metadata = new DesignMetadata
                {
                    Title = title,
                    CreatedAtUtc = DateTime.UtcNow
                }
            };
        }
    }
}
