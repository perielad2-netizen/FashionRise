using FashionRise.Domain;
using UnityEngine;

namespace FashionRise.Application
{
    /// <summary>PlayerPrefs-backed default sketch figure gender + pose.</summary>
    public static class SketchFigurePreferences
    {
        const string TemplateKey = "FashionRise.sketch_figure_template";
        const string PoseKey = "FashionRise.sketch_figure_pose";

        public const int PoseCount = 8;

        static readonly string[] PoseLabels =
        {
            "Stand", "Walk", "Show", "Hip", "Turn", "Arms", "Side", "Back"
        };

        public static SketchFigureTemplate DefaultTemplate
        {
            get => (SketchFigureTemplate)Mathf.Clamp(PlayerPrefs.GetInt(TemplateKey, (int)SketchFigureTemplate.Female), 0, 1);
            set
            {
                PlayerPrefs.SetInt(TemplateKey, (int)value);
                PlayerPrefs.Save();
            }
        }

        /// <summary>0-based pose index (0..PoseCount-1).</summary>
        public static int DefaultPoseIndex
        {
            get => Mathf.Clamp(PlayerPrefs.GetInt(PoseKey, 0), 0, PoseCount - 1);
            set
            {
                PlayerPrefs.SetInt(PoseKey, Mathf.Clamp(value, 0, PoseCount - 1));
                PlayerPrefs.Save();
            }
        }

        public static string PoseLabel(int poseIndex)
        {
            var i = Mathf.Clamp(poseIndex, 0, PoseCount - 1);
            return i < PoseLabels.Length ? PoseLabels[i] : $"Pose {i + 1}";
        }
    }
}
