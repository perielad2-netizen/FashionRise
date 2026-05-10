using System.Collections.Generic;
using FashionRise.Domain;

namespace FashionRise.Data
{
    public static class MaterialCatalogSeed
    {
        public static IReadOnlyList<MaterialDefinition> All => new[]
        {
            Mat("mat_satin", "Satin", "High-sheen woven face with fluid drape — evening and occasionwear.",
                sheen: 0.92f, softness: 0.78f, "light", "fluid", stretch: 0.05f, "formal", 9,
                new[] { "spring", "summer", "holiday" },
                new[] { GarmentCategory.Dress, GarmentCategory.TwoPiece, GarmentCategory.Top },
                "placeholder/satin", "{\"mill\":\"TBD\",\"sku\":\"TBD\"}"),
            Mat("mat_silk", "Silk", "Luxurious natural protein fiber with soft luster and excellent drape.",
                sheen: 0.85f, softness: 0.95f, "light", "fluid", stretch: 0.08f, "formal", 10,
                new[] { "spring", "summer", "fall" },
                new[] { GarmentCategory.Dress, GarmentCategory.Top, GarmentCategory.Skirt },
                "placeholder/silk", "{\"mill\":\"TBD\"}"),
            Mat("mat_cotton", "Cotton", "Breathable staple fiber — crisp to soft depending on weave.",
                sheen: 0.15f, softness: 0.72f, "medium", "soft-tailored", stretch: 0.12f, "casual", 5,
                new[] { "spring", "summer", "fall" },
                new[] { GarmentCategory.Top, GarmentCategory.Dress, GarmentCategory.Skirt },
                "placeholder/cotton", "{}"),
            Mat("mat_linen", "Linen", "Cool, textured plant fiber with relaxed structure.",
                sheen: 0.12f, softness: 0.55f, "medium", "structured-relaxed", stretch: 0.04f, "casual", 6,
                new[] { "spring", "summer" },
                new[] { GarmentCategory.Dress, GarmentCategory.Top, GarmentCategory.Skirt },
                "placeholder/linen", "{}"),
            Mat("mat_denim", "Denim", "Sturdy twill — casual utility with modern edge.",
                sheen: 0.08f, softness: 0.45f, "heavy", "firm", stretch: 0.18f, "casual", 4,
                new[] { "fall", "winter", "spring" },
                new[] { GarmentCategory.Skirt, GarmentCategory.Top, GarmentCategory.TwoPiece },
                "placeholder/denim", "{}"),
            Mat("mat_wool", "Wool", "Warm, resilient animal fiber — refined tailoring to cozy knits.",
                sheen: 0.22f, softness: 0.68f, "medium-heavy", "tailored", stretch: 0.15f, "formal", 8,
                new[] { "fall", "winter" },
                new[] { GarmentCategory.Dress, GarmentCategory.Top, GarmentCategory.TwoPiece },
                "placeholder/wool", "{}"),
            Mat("mat_chiffon", "Chiffon", "Sheer, lightweight weave — ethereal layers and movement.",
                sheen: 0.35f, softness: 0.82f, "light", "airy", stretch: 0.06f, "formal", 7,
                new[] { "spring", "summer" },
                new[] { GarmentCategory.Dress, GarmentCategory.Top, GarmentCategory.Skirt },
                "placeholder/chiffon", "{}"),
            Mat("mat_tulle", "Tulle", "Open net structure — volume and couture silhouettes.",
                sheen: 0.28f, softness: 0.35f, "light", "voluminous", stretch: 0.25f, "formal", 7,
                new[] { "spring", "summer", "holiday" },
                new[] { GarmentCategory.Dress, GarmentCategory.Skirt },
                "placeholder/tulle", "{}"),
            Mat("mat_velvet", "Velvet", "Dense pile surface — rich depth and light absorption.",
                sheen: 0.55f, softness: 0.9f, "medium-heavy", "sculptural", stretch: 0.1f, "formal", 9,
                new[] { "fall", "winter", "holiday" },
                new[] { GarmentCategory.Dress, GarmentCategory.Top, GarmentCategory.TwoPiece },
                "placeholder/velvet", "{}"),
            Mat("mat_leather", "Leather", "Structured hide or high-quality alternative — bold edge.",
                sheen: 0.4f, softness: 0.4f, "heavy", "firm", stretch: 0.02f, "formal", 9,
                new[] { "fall", "winter" },
                new[] { GarmentCategory.Top, GarmentCategory.Skirt, GarmentCategory.TwoPiece },
                "placeholder/leather", "{\"compliance\":\"verify-sourcing\"}"),
            Mat("mat_knit", "Knit", "Loop-constructed textile — stretch and comfort.",
                sheen: 0.18f, softness: 0.88f, "light-medium", "soft-drape", stretch: 0.45f, "casual", 5,
                new[] { "spring", "fall", "winter" },
                new[] { GarmentCategory.Top, GarmentCategory.Dress, GarmentCategory.TwoPiece },
                "placeholder/knit", "{}")
        };

        private static MaterialDefinition Mat(
            string id,
            string displayName,
            string description,
            float sheen,
            float softness,
            string weightClass,
            string drape,
            float stretch,
            string formalCasual,
            int luxury,
            string[] seasons,
            GarmentCategory[] categories,
            string placeholderRef,
            string sourcingJson)
        {
            return new MaterialDefinition
            {
                Id = id,
                DisplayName = displayName,
                Description = description,
                SheenLevel = sheen,
                SoftnessLevel = softness,
                WeightClass = weightClass,
                DrapeCharacter = drape,
                StretchLevel = stretch,
                FormalCasualTag = formalCasual,
                LuxuryScore = luxury,
                SeasonTags = seasons,
                RecommendedGarmentCategories = categories,
                PlaceholderMaterialReference = placeholderRef,
                FutureSourcingMetadata = sourcingJson
            };
        }
    }
}
