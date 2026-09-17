using System;

namespace FashionRise.Domain
{
    public sealed class TechPackRequest
    {
        public string DesignId { get; set; } = "";
        public string Notes { get; set; } = "";
        public string LocalSketchForVision { get; set; } = "";
        public string PolishedImageUrl { get; set; } = "";
        public string FabricName { get; set; } = "";
        public string ColorName { get; set; } = "";
        public string MaterialPairs { get; set; } = "";
        public Action<string>? OnJobStarted { get; set; }
    }

    public sealed class TechPackResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
        public string Disclaimer { get; set; } = "";
        public string FrontImageUrl { get; set; } = "";
        public string BackImageUrl { get; set; } = "";
        public string PatternImageUrl { get; set; } = "";
        /// <summary>Raw JSON string of result_data for the Tech Pack screen.</summary>
        public string RawJson { get; set; } = "";
    }
}
