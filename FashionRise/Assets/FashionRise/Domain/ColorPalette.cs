using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class ColorPalette
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public RgbaColor Primary { get; set; } = RgbaColor.White;
        public RgbaColor Secondary { get; set; } = RgbaColor.FromBytes(180, 175, 168);
        public RgbaColor Accent { get; set; } = RgbaColor.FromBytes(42, 38, 35);
        public RgbaColor Highlight { get; set; } = RgbaColor.FromBytes(235, 224, 210);
    }

    [Serializable]
    public struct RgbaColor
    {
        public byte R;
        public byte G;
        public byte B;
        public byte A;

        public static RgbaColor White => new() { R = 255, G = 255, B = 255, A = 255 };

        public static RgbaColor FromBytes(byte r, byte g, byte b, byte a = 255) =>
            new() { R = r, G = g, B = b, A = a };
    }
}
