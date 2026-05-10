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
    }
}
