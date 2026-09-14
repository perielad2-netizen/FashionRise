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
        /// <summary>Optional local file: URI or path — embedded as image_base64 for the worker when using API mode.</summary>
        public string LocalSketchForVision { get; set; } = "";
        /// <summary>
        /// Invoked as soon as the polish job id is known (before the long wait), so the UI can recover if polling fails.
        /// </summary>
        [NonSerialized]
        public Action<string>? OnJobStarted;
    }

    [Serializable]
    public sealed class ConceptRefinementResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
        /// <summary>Public URL of the AI-polished look image when the backend generated one.</summary>
        public string ImageUrl { get; set; } = "";
    }

    [Serializable]
    public sealed class StyleVariationRequest
    {
        public string? DesignId { get; set; }
        public string MoodNotes { get; set; } = "";
        /// <summary>Optional local sketch — embedded as image_base64 when using API mode.</summary>
        public string LocalSketchForVision { get; set; } = "";
    }

    [Serializable]
    public sealed class StyleVariationResult
    {
        public string JobId { get; set; } = "";
        public string Status { get; set; } = "";
        public string Summary { get; set; } = "";
    }
}
