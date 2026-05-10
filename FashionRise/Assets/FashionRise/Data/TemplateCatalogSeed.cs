using System.Collections.Generic;
using FashionRise.Domain;

namespace FashionRise.Data
{
    public static class TemplateCatalogSeed
    {
        public static IReadOnlyList<GarmentTemplate> All => new[]
        {
            Tpl("tpl_slip_dress", "Bias Slip", "Clean bias-cut silhouette.", GarmentCategory.Dress),
            Tpl("tpl_column", "Column Gown", "Minimal vertical lines.", GarmentCategory.Dress),
            Tpl("tpl_wrap_top", "Wrap Blouse", "Adjustable wrap closure.", GarmentCategory.Top),
            Tpl("tpl_boxy_top", "Boxy Shell", "Modern relaxed shoulder.", GarmentCategory.Top),
            Tpl("tpl_a_line_skirt", "A-Line Skirt", "Classic flattering sweep.", GarmentCategory.Skirt),
            Tpl("tpl_pencil_skirt", "Pencil Skirt", "Tailored pencil silhouette.", GarmentCategory.Skirt),
            Tpl("tpl_coord_set", "Tailored Coord", "Matched jacket + skirt set.", GarmentCategory.TwoPiece),
            Tpl("tpl_twin_set", "Knit Twin Set", "Soft coordinated layers.", GarmentCategory.TwoPiece),
            Tpl("tpl_evening_column", "Evening Column", "Formal floor-length column.", GarmentCategory.EveningGown),
            Tpl("tpl_cocktail_wrap", "Cocktail Wrap", "Structured cocktail wrap.", GarmentCategory.CocktailDress),
            Tpl("tpl_shirt_dress", "Shirt Dress", "Relaxed day dress.", GarmentCategory.CasualDress),
            Tpl("tpl_fluid_blouse", "Fluid Blouse", "Bias-cut blouse body.", GarmentCategory.Blouse),
            Tpl("tpl_tailored_jacket", "Tailored Jacket", "Single-breasted jacket block.", GarmentCategory.Jacket),
            Tpl("tpl_wide_leg", "Wide-Leg Pant", "High-rise wide leg.", GarmentCategory.Pants),
            Tpl("tpl_evening_coord", "Evening Coord", "Matched evening set.", GarmentCategory.CoordinatedSet)
        };

        private static GarmentTemplate Tpl(string id, string name, string desc, GarmentCategory cat)
        {
            return new GarmentTemplate
            {
                Id = id,
                Name = name,
                Description = desc,
                Category = cat,
                PreviewPlaceholderKey = $"preview/{id}"
            };
        }
    }
}
