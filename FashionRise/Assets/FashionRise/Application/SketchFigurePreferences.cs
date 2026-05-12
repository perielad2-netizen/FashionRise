using FashionRise.Domain;
using UnityEngine;

namespace FashionRise.Application
{
    /// <summary>PlayerPrefs-backed default sketch figure (female / male croquis).</summary>
    public static class SketchFigurePreferences
    {
        const string Key = "FashionRise.sketch_figure_template";

        public static SketchFigureTemplate DefaultTemplate
        {
            get => (SketchFigureTemplate)Mathf.Clamp(PlayerPrefs.GetInt(Key, (int)SketchFigureTemplate.Female), 0, 1);
            set
            {
                PlayerPrefs.SetInt(Key, (int)value);
                PlayerPrefs.Save();
            }
        }
    }
}
