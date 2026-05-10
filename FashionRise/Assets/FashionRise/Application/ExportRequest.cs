using System;

namespace FashionRise.Application
{
    [Serializable]
    public sealed class ExportRequest
    {
        public string DesignId { get; set; } = "";
        public string FileName { get; set; } = "fashionrise_export";
        public int Width { get; set; } = 1080;
        public int Height { get; set; } = 1920;
        public bool IncludeWatermark { get; set; }
    }
}
