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

        /// <summary>When true, API path uploads the PNG for a URL only (e.g. gallery <c>image_url</c>) and skips <c>POST /exports</c>.</summary>
        public bool SkipExportRegistration { get; set; }
    }
}
