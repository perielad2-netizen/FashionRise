using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class SketchInputData
    {
        public string Notes { get; set; } = "";
        public string LocalImagePathPlaceholder { get; set; } = "";
    }

    [Serializable]
    public sealed class SketchEnhancementRequest
    {
        public string? DesignId { get; set; }
        public SketchInputData Input { get; set; } = new();
    }

    [Serializable]
    public sealed class SketchEnhancementResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
    }

    [Serializable]
    public sealed class ConceptRefinementRequest
    {
        public string? DesignId { get; set; }
        public string Notes { get; set; } = "";
    }

    [Serializable]
    public sealed class ConceptRefinementResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
    }

    [Serializable]
    public sealed class StyleVariationRequest
    {
        public string? DesignId { get; set; }
        public string MoodNotes { get; set; } = "";
    }

    [Serializable]
    public sealed class StyleVariationResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
    }
}
