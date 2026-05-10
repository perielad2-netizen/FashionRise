using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class RatingSummary
    {
        public double Average { get; set; }
        public int Count { get; set; }
        public int? MyScore { get; set; }
    }
}
