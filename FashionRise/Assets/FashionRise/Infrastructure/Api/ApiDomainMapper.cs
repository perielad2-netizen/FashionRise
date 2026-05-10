using System;
using System.Collections.Generic;
using System.Globalization;
using FashionRise.Domain;
using Newtonsoft.Json.Linq;

namespace FashionRise.Infrastructure.Api
{
    static class ApiDomainMapper
    {
        public static bool LooksLikeClientGeneratedDesignId(string id) =>
            !string.IsNullOrEmpty(id) && id.Length == 32 && id.IndexOf('-') < 0;

        public static GarmentDesign ToGarmentDesign(DesignReadDto d)
        {
            var gd = new GarmentDesign
            {
                Id = d.Id.ToString(),
                OwnerUserId = d.UserId.ToString(),
                Category = ParseCategory(d.GarmentCategory),
                TemplateId = d.TemplateId?.ToString() ?? "",
                MaterialId = d.MaterialId?.ToString() ?? "",
                ColorPaletteId = d.ColorPaletteId?.ToString() ?? "",
                Status = d.Status,
                Metadata = new DesignMetadata
                {
                    Title = d.Title,
                    CreatedAtUtc = d.CreatedAt.ToUniversalTime()
                }
            };

            var data = d.DesignData;
            if (data == null || !data.HasValues)
                return gd;

            if (Enum.TryParse<NecklineType>(data.Value<string>("neckline"), true, out var nl))
                gd.Neckline = nl;
            if (Enum.TryParse<SleeveType>(data.Value<string>("sleeve"), true, out var sl))
                gd.Sleeve = sl;
            if (Enum.TryParse<GarmentLength>(data.Value<string>("length"), true, out var len))
                gd.Length = len;
            if (Enum.TryParse<FitStyle>(data.Value<string>("fit"), true, out var fit))
                gd.Fit = fit;
            if (Enum.TryParse<WaistStyle>(data.Value<string>("waist"), true, out var waist))
                gd.Waist = waist;
            if (Enum.TryParse<SilhouetteVolume>(data.Value<string>("silhouette_volume"), true, out var sv))
                gd.SilhouetteVolume = sv;
            if (Enum.TryParse<DrapeExpression>(data.Value<string>("drape_expression"), true, out var dr))
                gd.DrapeExpression = dr;
            if (Enum.TryParse<LayeringDepth>(data.Value<string>("layering_depth"), true, out var ly))
                gd.LayeringDepth = ly;
            if (Enum.TryParse<SeamAccentStyle>(data.Value<string>("seam_accent"), true, out var seam))
                gd.SeamAccent = seam;
            gd.TrimNotes = data.Value<string>("trim_notes") ?? "";
            gd.AccentNotes = data.Value<string>("accent_notes") ?? "";
            gd.SketchReference = data.Value<string>("sketch_reference") ?? "";

            return gd;
        }

        public static GarmentCategory ParseCategory(string raw)
        {
            if (Enum.TryParse<GarmentCategory>(raw, true, out var c))
                return c;
            return raw.ToLowerInvariant().Replace("-", "_") switch
            {
                "skirt" => GarmentCategory.Skirt,
                "two_piece" or "two-piece" or "twopiece" => GarmentCategory.TwoPiece,
                "evening_gown" or "eveninggown" => GarmentCategory.EveningGown,
                "cocktail_dress" or "cocktaildress" => GarmentCategory.CocktailDress,
                "casual_dress" or "casualdress" => GarmentCategory.CasualDress,
                "blouse" => GarmentCategory.Blouse,
                "jacket" => GarmentCategory.Jacket,
                "pants" or "trousers" => GarmentCategory.Pants,
                "coordinated_set" or "coordinatedset" => GarmentCategory.CoordinatedSet,
                _ => GarmentCategory.Dress
            };
        }

        public static object ToDesignCreateBody(GarmentDesign design)
        {
            var designData = new Dictionary<string, object>
            {
                ["neckline"] = design.Neckline.ToString(),
                ["sleeve"] = design.Sleeve.ToString(),
                ["length"] = design.Length.ToString(),
                ["fit"] = design.Fit.ToString(),
                ["waist"] = design.Waist.ToString(),
                ["silhouette_volume"] = design.SilhouetteVolume.ToString(),
                ["drape_expression"] = design.DrapeExpression.ToString(),
                ["layering_depth"] = design.LayeringDepth.ToString(),
                ["seam_accent"] = design.SeamAccent.ToString(),
                ["trim_notes"] = design.TrimNotes,
                ["accent_notes"] = design.AccentNotes,
                ["sketch_reference"] = design.SketchReference
            };

            Guid? tpl = TryGuid(design.TemplateId);
            Guid? mat = TryGuid(design.MaterialId);
            Guid? pal = TryGuid(design.ColorPaletteId);

            return new
            {
                title = string.IsNullOrEmpty(design.Metadata.Title) ? "Untitled" : design.Metadata.Title,
                description = (string?)null,
                garment_category = CategoryApiValue(design.Category),
                template_id = tpl,
                material_id = mat,
                color_palette_id = pal,
                design_data = designData,
                metadata = new Dictionary<string, object>
                {
                    ["created_at_utc"] = design.Metadata.CreatedAtUtc.ToString("o", CultureInfo.InvariantCulture)
                },
                visibility = "private",
                status = string.IsNullOrEmpty(design.Status) ? "draft" : design.Status
            };
        }

        public static object ToDesignUpdateBody(GarmentDesign design)
        {
            var designData = new Dictionary<string, object>
            {
                ["neckline"] = design.Neckline.ToString(),
                ["sleeve"] = design.Sleeve.ToString(),
                ["length"] = design.Length.ToString(),
                ["fit"] = design.Fit.ToString(),
                ["waist"] = design.Waist.ToString(),
                ["silhouette_volume"] = design.SilhouetteVolume.ToString(),
                ["drape_expression"] = design.DrapeExpression.ToString(),
                ["layering_depth"] = design.LayeringDepth.ToString(),
                ["seam_accent"] = design.SeamAccent.ToString(),
                ["trim_notes"] = design.TrimNotes,
                ["accent_notes"] = design.AccentNotes,
                ["sketch_reference"] = design.SketchReference
            };

            return new
            {
                title = string.IsNullOrEmpty(design.Metadata.Title) ? "Untitled" : design.Metadata.Title,
                description = (string?)null,
                garment_category = CategoryApiValue(design.Category),
                template_id = TryGuid(design.TemplateId),
                material_id = TryGuid(design.MaterialId),
                color_palette_id = TryGuid(design.ColorPaletteId),
                design_data = designData,
                metadata = new Dictionary<string, object>
                {
                    ["created_at_utc"] = design.Metadata.CreatedAtUtc.ToString("o", CultureInfo.InvariantCulture)
                },
                visibility = (string?)null,
                status = design.Status
            };
        }

        static string CategoryApiValue(GarmentCategory c) =>
            c switch
            {
                GarmentCategory.Dress => "dress",
                GarmentCategory.Top => "top",
                GarmentCategory.Skirt => "skirt",
                GarmentCategory.TwoPiece => "two_piece",
                GarmentCategory.EveningGown => "evening_gown",
                GarmentCategory.CocktailDress => "cocktail_dress",
                GarmentCategory.CasualDress => "casual_dress",
                GarmentCategory.Blouse => "blouse",
                GarmentCategory.Jacket => "jacket",
                GarmentCategory.Pants => "pants",
                GarmentCategory.CoordinatedSet => "coordinated_set",
                _ => "dress"
            };

        static Guid? TryGuid(string? s)
        {
            if (string.IsNullOrWhiteSpace(s))
                return null;
            return Guid.TryParse(s, out var g) ? g : null;
        }

        public static MaterialDefinition ToMaterial(MaterialReadDto m)
        {
            var seasons = new List<string>();
            foreach (var t in m.SeasonTags)
                if (t.Type == JTokenType.String)
                    seasons.Add(t.Value<string>() ?? "");

            var cats = new List<GarmentCategory>();
            foreach (var t in m.RecommendedCategories)
            {
                if (t.Type == JTokenType.String && t.Value<string>() is { } s)
                    cats.Add(ParseCategory(s));
            }

            var mat = new MaterialDefinition
            {
                Id = m.Id.ToString(),
                DisplayName = m.Name,
                Description = m.Description ?? "",
                SheenLevel = (float)(m.SheenLevel ?? 0),
                SoftnessLevel = (float)(m.SoftnessLevel ?? 0),
                WeightClass = m.WeightClass ?? "",
                DrapeCharacter = m.DrapeCharacter ?? "",
                StretchLevel = (float)(m.StretchLevel ?? 0),
                LuxuryScore = m.LuxuryScore ?? 0,
                SeasonTags = seasons,
                RecommendedGarmentCategories = cats,
                PlaceholderMaterialReference = m.TextureUrl ?? "",
                FutureSourcingMetadata = m.Metadata?.ToString() ?? ""
            };

            if (m.Metadata != null && m.Metadata["v2"] is JObject v2)
            {
                mat.PremiumTier = v2.Value<int?>("premium_tier") ?? 0;
                mat.RealWorldUsageNotes = v2.Value<string>("real_world_usage") ?? "";
                mat.CareComplexity = v2.Value<string>("care_complexity") ?? "";
                mat.OccasionSuitability = SplitJsonStrings(v2["occasion_suitability"]);
                mat.DrapeTags = SplitJsonStrings(v2["drape_tags"]);
                mat.PairingRecommendations = SplitJsonStrings(v2["pairing_recommendations"]);
                mat.MaterialRole = v2.Value<string>("material_role") ?? "";
                mat.TextureSetRefs = SplitJsonStrings(v2["texture_set_refs"]);
                mat.RenderParameterGroup = v2.Value<string>("render_parameter_group") ?? "";
            }

            return mat;
        }

        static IReadOnlyList<string> SplitJsonStrings(JToken? tok)
        {
            if (tok is not JArray arr)
                return Array.Empty<string>();
            var list = new List<string>();
            foreach (var t in arr)
                if (t.Type == JTokenType.String && t.Value<string>() is { } s)
                    list.Add(s);
            return list;
        }

        public static GarmentTemplate ToTemplate(GarmentTemplateReadDto t) =>
            new()
            {
                Id = t.Id.ToString(),
                Name = t.Name,
                Description = t.Description ?? "",
                Category = ParseCategory(t.Category),
                PreviewPlaceholderKey = t.PreviewUrl ?? ""
            };

        public static ColorPalette ToPalette(ColorPaletteReadDto p)
        {
            RgbaColor primary = RgbaColor.White, secondary = RgbaColor.FromBytes(180, 175, 168),
                accent = RgbaColor.FromBytes(42, 38, 35), highlight = RgbaColor.FromBytes(235, 224, 210);
            foreach (var token in p.Colors)
            {
                if (token is not JObject o)
                    continue;
                var role = o.Value<string>("role")?.ToLowerInvariant();
                var hex = o.Value<string>("hex");
                var col = ParseHexColor(hex);
                switch (role)
                {
                    case "primary":
                        primary = col;
                        break;
                    case "secondary":
                        secondary = col;
                        break;
                    case "accent":
                        accent = col;
                        break;
                    case "highlight":
                        highlight = col;
                        break;
                }
            }

            return new ColorPalette
            {
                Id = p.Id.ToString(),
                Name = p.Name,
                Primary = primary,
                Secondary = secondary,
                Accent = accent,
                Highlight = highlight
            };
        }

        static RgbaColor ParseHexColor(string? hex)
        {
            if (string.IsNullOrEmpty(hex) || hex[0] != '#' || hex.Length < 7)
                return RgbaColor.White;
            try
            {
                var r = byte.Parse(hex.AsSpan(1, 2), NumberStyles.HexNumber);
                var g = byte.Parse(hex.AsSpan(3, 2), NumberStyles.HexNumber);
                var b = byte.Parse(hex.AsSpan(5, 2), NumberStyles.HexNumber);
                return RgbaColor.FromBytes(r, g, b);
            }
            catch
            {
                return RgbaColor.White;
            }
        }

        public static GalleryItem ToGalleryItem(GalleryReadDto g) =>
            new()
            {
                Id = g.Id.ToString(),
                OwnerUserId = g.UserId.ToString(),
                DesignId = g.DesignId.ToString(),
                Title = g.Title,
                ThumbnailPlaceholderKey = g.ImageUrl ?? "",
                Rating = new RatingSummary
                {
                    Average = g.RatingAverage ?? 0,
                    Count = g.RatingCount
                },
                LikesCount = g.LikesCount,
                LikedByMe = g.LikedByMe ?? false
            };

        public static GalleryComment ToGalleryComment(GalleryCommentReadDto c) =>
            new()
            {
                Id = c.Id.ToString(),
                GalleryItemId = c.GalleryItemId.ToString(),
                AuthorUserId = c.UserId.ToString(),
                Body = c.Body,
                CreatedAtUtc = c.CreatedAt.ToUniversalTime()
            };
    }
}
