using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class ExportPackage
    {
        public string ExportId { get; set; } = "";
        public string DesignId { get; set; } = "";
        public string LocalPngPath { get; set; } = "";
        public DateTime CreatedAtUtc { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
    }
}
