using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
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

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            var sb = new StringBuilder();
            sb.AppendLine($"Job: {App.CreateDesign.LastSketchJobId}");
            sb.AppendLine($"{App.CreateDesign.LastSketchSummary}");
            sb.AppendLine();
            sb.AppendLine($"Sketch ref: {App.CreateDesign.SketchReference}");
            _body.text = sb.ToString();

            if (App.IsApiBackend && App.Auth.HasBackendSession &&
                !string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchJobId))
            {
                try
                {
                    var detail = await App.Ai
                        .GetJobStructuredDetailTextAsync(App.CreateDesign.LastSketchJobId, cancellationToken)
                        .ConfigureAwait(true);
                    if (!string.IsNullOrEmpty(detail))
                    {
                        sb.AppendLine();
                        sb.AppendLine(detail);
                        _body.text = sb.ToString();
                    }
                }
                catch (Exception ex)
                {
                    sb.AppendLine();
                    sb.AppendLine($"(Could not load job details: {ex.Message})");
                    _body.text = sb.ToString();
                }
            }
        }
    }
}
