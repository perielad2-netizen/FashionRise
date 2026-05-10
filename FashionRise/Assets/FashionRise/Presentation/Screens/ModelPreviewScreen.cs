using FashionRise.Core.Navigation;
using FashionRise.Presentation.Preview;
using FashionRise.UI;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class ModelPreviewScreen : ScreenBase
    {
        [SerializeField] ModelPreviewController? previewController;

        public override ScreenId Id => ScreenId.ModelPreview;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Model preview", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "V2 framing presets — hook ModelPreviewController for full garment systems. [V3_READY]",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);

            FrUiFactory.AddButton(col, "Apply session to preview", t, () =>
            {
                var p = previewController != null
                    ? previewController
                    : UnityEngine.Object.FindObjectOfType<ModelPreviewController>();
                p?.Present(App.CreateDesign);
            });

            void FramingBtn(string label, PreviewFraming framing) =>
                FrUiFactory.AddButton(col, label, t, () =>
                {
                    PreviewCameraController? cam = null;
                    if (previewController != null)
                        cam = previewController.GetComponentInChildren<PreviewCameraController>(true);
                    if (cam == null)
                        cam = UnityEngine.Object.FindObjectOfType<PreviewCameraController>();
                    cam?.ApplyFraming(framing);
                });

            FramingBtn("Front", PreviewFraming.Front);
            FramingBtn("Back", PreviewFraming.Back);
            FramingBtn("Side", PreviewFraming.Side);
            FramingBtn("Turntable", PreviewFraming.Turntable);
            FramingBtn("Runway", PreviewFraming.Runway);
            FramingBtn("Lookbook", PreviewFraming.Lookbook);

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }
    }
}
