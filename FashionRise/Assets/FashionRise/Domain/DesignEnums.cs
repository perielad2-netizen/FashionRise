namespace FashionRise.Domain
{
    public enum NecklineType
    {
        Crew = 0,
        VNeck = 1,
        Sweetheart = 2,
        Halter = 3,
        OffShoulder = 4,
        Boat = 5
    }

    public enum SleeveType
    {
        Sleeveless = 0,
        Cap = 1,
        Short = 2,
        ThreeQuarter = 3,
        Long = 4,
        Bell = 5
    }

    public enum GarmentLength
    {
        Micro = 0,
        Mini = 1,
        Midi = 2,
        Maxi = 3,
        Floor = 4
    }

    public enum FitStyle
    {
        Slim = 0,
        Regular = 1,
        Relaxed = 2,
        Oversized = 3,
        Tailored = 4
    }

    public enum WaistStyle
    {
        Natural = 0,
        Empire = 1,
        Drop = 2,
        HighRise = 3,
        Basque = 4
    }

    /// <summary>V2 silhouette tuning — stored in design_data.</summary>
    public enum SilhouetteVolume
    {
        Sleek = 0,
        Balanced = 1,
        Voluminous = 2
    }

    public enum DrapeExpression
    {
        Fluid = 0,
        Tailored = 1,
        Sculpted = 2
    }

    public enum LayeringDepth
    {
        None = 0,
        Light = 1,
        Dramatic = 2
    }

    public enum SeamAccentStyle
    {
        Minimal = 0,
        Piped = 1,
        Topstitched = 2,
        Contrast = 3
    }
}
