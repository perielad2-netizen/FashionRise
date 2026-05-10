using System;
using System.Collections.Generic;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class GarmentDesign
    {
        public string Id { get; set; } = "";
        public string OwnerUserId { get; set; } = "";
        public DesignMetadata Metadata { get; set; } = new();
        public GarmentCategory Category { get; set; }
        public string TemplateId { get; set; } = "";
        public NecklineType Neckline { get; set; }
        public SleeveType Sleeve { get; set; }
        public GarmentLength Length { get; set; }
        public FitStyle Fit { get; set; }
        public WaistStyle Waist { get; set; }
        public string ColorPaletteId { get; set; } = "";
        public string MaterialId { get; set; } = "";
        public string Status { get; set; } = "draft";
        public IReadOnlyDictionary<string, string> ExtensionData { get; set; } =
            new Dictionary<string, string>();

        public SilhouetteVolume SilhouetteVolume { get; set; } = SilhouetteVolume.Balanced;
        public DrapeExpression DrapeExpression { get; set; } = DrapeExpression.Fluid;
        public LayeringDepth LayeringDepth { get; set; } = LayeringDepth.None;
        public SeamAccentStyle SeamAccent { get; set; } = SeamAccentStyle.Minimal;
        public string TrimNotes { get; set; } = "";
        public string AccentNotes { get; set; } = "";
        public string SketchReference { get; set; } = "";
    }
}
