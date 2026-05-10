using System;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Queues sketch_clean / polish / style jobs (API or mock). [AI_READY]</summary>
    public sealed class SketchEnhancementScreen : ScreenBase
    {
        Text _status = null!;

        public override ScreenId Id => ScreenId.SketchEnhancement;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Sketch enhancement", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _status = FrUiFactory.AddLabel(col, "St", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            FrUiFactory.AddButton(col, "AI cleanup (sketch/clean)", t, () => { _ = RunCleanAsync(); });
            FrUiFactory.AddButton(col, "Polish concept (sketch/polish)", t, () => { _ = RunPolishAsync(); });
            FrUiFactory.AddButton(col, "Style suggestions (style/suggest)", t, () => { _ = RunStyleAsync(); });
            FrUiFactory.AddButton(col, "Refine image (maps to polish)", t, () => { _ = RunRefineAsync(); });
            FrUiFactory.AddButton(col, "View last result", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
            });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) =>
            _status.text = $"Sketch ref: {App.CreateDesign.SketchReference}\nChoose a pipeline step.";

        async Task RunCleanAsync()
        {
            _status.text = "Running cleanup…";
            try
            {
                var r = await App.SketchClean.CleanAsync(new SketchEnhancementRequest
                {
                    DesignId = TryDesignId(),
                    Input = new SketchInputData
                    {
                        Notes = "cleanup",
                        LocalImagePathPlaceholder = App.CreateDesign.SketchReference
                    }
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary);
            }
            catch (Exception ex)
            {
                _status.text = ex.Message;
            }
        }

        async Task RunPolishAsync()
        {
            _status.text = "Polishing…";
            try
            {
                var r = await App.ConceptPolish.PolishAsync(new ConceptRefinementRequest
                {
                    DesignId = TryDesignId(),
                    Notes = "polish concept"
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary);
            }
            catch (Exception ex)
            {
                _status.text = ex.Message;
            }
        }

        async Task RunStyleAsync()
        {
            _status.text = "Suggesting styles…";
            try
            {
                var r = await App.StyleSuggest.SuggestAsync(new StyleVariationRequest
                {
                    DesignId = TryDesignId(),
                    MoodNotes = "evening, sculptural"
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary);
            }
            catch (Exception ex)
            {
                _status.text = ex.Message;
            }
        }

        async Task RunRefineAsync()
        {
            _status.text = "Refining…";
            try
            {
                var r = await App.ImageRefine.RefineAsync(new ConceptRefinementRequest
                {
                    DesignId = TryDesignId(),
                    Notes = "refine edges"
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary);
            }
            catch (Exception ex)
            {
                _status.text = ex.Message;
            }
        }

        string? TryDesignId()
        {
            /* Optional: attach to last saved design in API mode — omitted for minimal V2 slice */
            return null;
        }

        void Finish(string jobId, string summary)
        {
            App.CreateDesign.LastSketchJobId = jobId;
            App.CreateDesign.LastSketchSummary = summary;
            _status.text = $"Job {jobId}\n{summary}\n\nOpening result screen…";
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
        }
    }
}
