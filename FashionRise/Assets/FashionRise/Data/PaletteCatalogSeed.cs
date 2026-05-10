using System.Collections.Generic;
using FashionRise.Domain;

namespace FashionRise.Data
{
    public static class PaletteCatalogSeed
    {
        public static IReadOnlyList<ColorPalette> All => new[]
        {
            Pal("pal_ivory_noir", "Ivory & Noir",
                RgbaColor.FromBytes(247, 242, 234), RgbaColor.FromBytes(28, 26, 24),
                RgbaColor.FromBytes(92, 82, 74), RgbaColor.FromBytes(214, 198, 176)),
            Pal("pal_dust_rose", "Dust Rose",
                RgbaColor.FromBytes(232, 210, 208), RgbaColor.FromBytes(158, 120, 122),
                RgbaColor.FromBytes(94, 58, 62), RgbaColor.FromBytes(250, 236, 234)),
            Pal("pal_sea_mist", "Sea Mist",
                RgbaColor.FromBytes(218, 232, 228), RgbaColor.FromBytes(76, 118, 112),
                RgbaColor.FromBytes(42, 68, 64), RgbaColor.FromBytes(236, 246, 242)),
            Pal("pal_graphite_champagne", "Graphite Champagne",
                RgbaColor.FromBytes(62, 62, 66), RgbaColor.FromBytes(224, 216, 200),
                RgbaColor.FromBytes(184, 160, 128), RgbaColor.FromBytes(92, 92, 98))
        };

        private static ColorPalette Pal(string id, string name, RgbaColor p, RgbaColor s, RgbaColor a, RgbaColor h)
        {
            return new ColorPalette
            {
                Id = id,
                Name = name,
                Primary = p,
                Secondary = s,
                Accent = a,
                Highlight = h
            };
        }
    }
}
