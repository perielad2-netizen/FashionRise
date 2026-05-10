using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class CreatorStats
    {
        public int DesignCount { get; set; }
        public int PublishedCount { get; set; }
        public double AverageRating { get; set; }
        public int RatingCount { get; set; }
    }
}
