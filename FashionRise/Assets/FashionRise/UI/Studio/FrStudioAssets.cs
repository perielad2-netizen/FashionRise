using System.Collections.Generic;
using UnityEngine;

namespace FashionRise.UI.Studio
{
    /// <summary>
    /// Runtime loader for FashionRise Studio PNG assets under Resources/StudioUI.
    /// Falls back to null so callers can keep programmatic chrome when a sprite is absent.
    /// </summary>
    public static class FrStudioAssets
    {
        const string IconRoot = "StudioUI/Icons/";
        const string ModelRoot = "StudioUI/Models/";

        static readonly Dictionary<string, Sprite?> IconCache = new();
        static readonly Dictionary<string, Texture2D?> ModelCache = new();

        public static Sprite? Icon(FrStudioIconKind kind)
        {
            var key = kind switch
            {
                FrStudioIconKind.Back => "fr_icon_back",
                FrStudioIconKind.Import => "fr_icon_import",
                FrStudioIconKind.Profile => "fr_icon_profile",
                FrStudioIconKind.Magic => "fr_icon_magic",
                FrStudioIconKind.Draw => "fr_icon_draw",
                FrStudioIconKind.Erase => "fr_icon_erase",
                FrStudioIconKind.Undo => "fr_icon_undo",
                FrStudioIconKind.Clear => "fr_icon_clear",
                FrStudioIconKind.Dim => "fr_icon_reference",
                FrStudioIconKind.Blank => "fr_icon_clear",
                _ => null
            };
            return key == null ? null : LoadIcon(key);
        }

        public static Sprite? IconNamed(string resourceName) => LoadIcon(resourceName);

        public static Texture2D? ModelFemale => LoadModel("fr_model_female");
        public static Texture2D? ModelMale => LoadModel("fr_model_male");
        public static Texture2D? ModelCustom => LoadModel("fr_model_custom");
        public static Texture2D? ModelBlank => LoadModel("fr_model_blank");

        static Sprite? LoadIcon(string name)
        {
            if (IconCache.TryGetValue(name, out var hit))
                return hit;
            var sprite = Resources.Load<Sprite>(IconRoot + name);
            IconCache[name] = sprite;
            return sprite;
        }

        static Texture2D? LoadModel(string name)
        {
            if (ModelCache.TryGetValue(name, out var hit))
                return hit;
            var tex = Resources.Load<Texture2D>(ModelRoot + name);
            if (tex == null)
            {
                var sprite = Resources.Load<Sprite>(ModelRoot + name);
                if (sprite != null)
                    tex = sprite.texture;
            }

            ModelCache[name] = tex;
            return tex;
        }
    }
}
