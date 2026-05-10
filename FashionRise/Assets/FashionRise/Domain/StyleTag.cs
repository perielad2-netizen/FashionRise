using System;

namespace FashionRise.Domain
{
    [Serializable]
    public sealed class StyleTag
    {
        public string Id { get; set; } = "";
        public string Label { get; set; } = "";
    }
}
