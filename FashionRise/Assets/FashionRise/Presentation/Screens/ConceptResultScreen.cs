using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class ConceptResultScreen : ScreenBase
    {
        Text _body = null!;

        public override ScreenId Id => ScreenId.ConceptResult;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Concept result", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _body = FrUiFactory.AddLabel(col, "B", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            FrUiFactory.AddButton(col, "Apply sketch ref to design session", t, () =>
            {
                if (!string.IsNullOrEmpty(App.CreateDesign.LastSketchJobId))
                    App.CreateDesign.SketchReference = "job:" + App.CreateDesign.LastSketchJobId;
                _body.text = "Sketch reference updated on CreateDesign session.";
            });
            FrUiFactory.AddButton(col, "Back to enhancement", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement);
            });
            FrUiFactory.AddButton(col, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            });
        }

        protected override void OnShown(object? payload) =>
            _body.text =
                $"Job: {App.CreateDesign.LastSketchJobId}\n" +
                $"{App.CreateDesign.LastSketchSummary}\n\n" +
                $"Sketch ref: {App.CreateDesign.SketchReference}";
    }
}
