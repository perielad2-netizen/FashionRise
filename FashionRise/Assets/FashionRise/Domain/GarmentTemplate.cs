using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class GarmentTemplate
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Description { get; set; } = "";
        public GarmentCategory Category { get; set; }
        public string PreviewPlaceholderKey { get; set; } = "";
    }
}
