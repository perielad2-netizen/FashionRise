namespace FashionRise.Domain
{
    /// <summary>Payload when opening the sketch canvas / magic pipeline from the kid front door.</summary>
    public sealed class SketchNavContext
    {
        public SketchFigureTemplate? Figure { get; set; }

        /// <summary>When true, enhancement screen auto-runs polish once.</summary>
        public bool AutoMagic { get; set; }
    }
}
