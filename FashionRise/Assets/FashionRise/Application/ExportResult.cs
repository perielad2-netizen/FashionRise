using System;
using FashionRise.Domain;

namespace FashionRise.Application
{
    [Serializable]
    public sealed class ExportResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = "";
        public ExportPackage? Package { get; set; }

        /// <summary>Public URL after the PNG was uploaded to the API (gallery publish / export pipeline).</summary>
        public string? UploadedImageUrl { get; set; }
    }
}
