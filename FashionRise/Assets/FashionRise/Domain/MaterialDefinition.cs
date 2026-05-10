using System;
using System.Collections.Generic;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class MaterialDefinition
    {
        public string Id { get; set; } = "";
        public string DisplayName { get; set; } = "";
        public string Description { get; set; } = "";
        public float SheenLevel { get; set; }
        public float SoftnessLevel { get; set; }
        public string WeightClass { get; set; } = "";
        public string DrapeCharacter { get; set; } = "";
        public float StretchLevel { get; set; }
        public string FormalCasualTag { get; set; } = "";
        public int LuxuryScore { get; set; }
        public IReadOnlyList<string> SeasonTags { get; set; } = Array.Empty<string>();
        public IReadOnlyList<GarmentCategory> RecommendedGarmentCategories { get; set; } =
            Array.Empty<GarmentCategory>();
        public string PlaceholderMaterialReference { get; set; } = "";
        public string FutureSourcingMetadata { get; set; } = "";

        public int PremiumTier { get; set; }
        public string RealWorldUsageNotes { get; set; } = "";
        public string CareComplexity { get; set; } = "";
        public IReadOnlyList<string> DrapeTags { get; set; } = Array.Empty<string>();
        public IReadOnlyList<string> OccasionSuitability { get; set; } = Array.Empty<string>();
        public string MaterialRole { get; set; } = "";
        public IReadOnlyList<string> PairingRecommendations { get; set; } = Array.Empty<string>();
        public IReadOnlyList<string> TextureSetRefs { get; set; } = Array.Empty<string>();
        public string RenderParameterGroup { get; set; } = "";
    }
}
