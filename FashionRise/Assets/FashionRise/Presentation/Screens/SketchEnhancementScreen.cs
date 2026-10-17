using System;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Kid front door: one Magic action. Extra AI tools stay under More.</summary>
    public sealed class SketchEnhancementScreen : ScreenBase
    {
        Text _status = null!;
        bool _moreOpen;
        bool _autoMagicArmed;
        bool _busy;

        public override ScreenId Id => ScreenId.SketchEnhancement;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Magic", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "AI polishes your sketch into a cleaner fashion look.", t,
                Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);
            _status = FrUiFactory.AddLabel(col, "St", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            var magic = FrUiFactory.AddButton(col, "Make it magical!", t, () => { _ = RunPolishAsync(); },
                FrButtonEmphasis.Primary);
            var le = magic.GetComponent<LayoutElement>();
            if (le != null)
            {
                le.minHeight = 72f;
                le.preferredHeight = 72f;
            }

            // Always visible — open Your look even if Magic's poll failed after the server finished.
            FrUiFactory.AddButton(col, "See last result", t, () => { _ = OpenLastResultAsync(); },
                FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(col, "More AI tools…", t, ToggleMore);
            FrUiFactory.AddButton(col, "Clean lines", t, () => { _ = RunCleanAsync(); });
            FrUiFactory.AddButton(col, "Style ideas", t, () => { _ = RunStyleAsync(); });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });

            SetMoreVisible(false);
        }

        protected override void OnShown(object? payload)
        {
            _status.text = "Ready when you are.";
            _autoMagicArmed = payload is true ||
                              (payload is string s && string.Equals(s, "auto", StringComparison.OrdinalIgnoreCase));
            SetMoreVisible(_moreOpen);
            if (_autoMagicArmed)
            {
                _autoMagicArmed = false;
                _ = RunPolishAsync();
            }
        }

        void ToggleMore()
        {
            _moreOpen = !_moreOpen;
            SetMoreVisible(_moreOpen);
        }

        void SetMoreVisible(bool open)
        {
            var col = transform.Find("Root/Col");
            if (col == null)
                return;
            SetSiblingActive(col, "Clean lines_Btn", open);
            SetSiblingActive(col, "Style ideas_Btn", open);
            // "See last result" stays visible so a finished look can always be opened.
        }

        static void SetSiblingActive(Transform col, string name, bool active)
        {
            var child = col.Find(name);
            if (child != null)
                child.gameObject.SetActive(active);
        }

        async Task OpenLastResultAsync()
        {
            _status.text = "Loading your last look…";
            try
            {
                if (App.IsApiBackend && App.Auth.HasBackendSession &&
                    !string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchJobId))
                {
                    var url = await App.Ai
                        .GetJobImageUrlAsync(App.CreateDesign.LastSketchJobId)
                        .ConfigureAwait(true);
                    if (!string.IsNullOrEmpty(url))
                        App.CreateDesign.LastPolishedImageUrl = url!;
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise See last result refresh failed: {ex.Message}");
            }

            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
        }

        async Task RunCleanAsync()
        {
            if (_busy) return;
            _busy = true;
            _status.text = "Cleaning lines…";
            try
            {
                var r = await App.SketchClean.CleanAsync(new SketchEnhancementRequest
                {
                    DesignId = null,
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
            finally
            {
                _busy = false;
            }
        }

        async Task RunPolishAsync()
        {
            if (_busy)
            {
                _status.text = "Magic is already working… hang tight.";
                return;
            }

            _busy = true;
            _status.text = "Working magic… this can take about a minute.";
            try
            {
                var r = await App.ConceptPolish.PolishAsync(new ConceptRefinementRequest
                {
                    DesignId = null,
                    Notes = "polish concept",
                    LocalSketchForVision = App.CreateDesign.SketchReference,
                    OnJobStarted = jobId =>
                    {
                        if (!string.IsNullOrWhiteSpace(jobId))
                            App.CreateDesign.LastSketchJobId = jobId;
                    }
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary, r.ImageUrl);
                if (string.IsNullOrEmpty(r.ImageUrl))
                    Debug.LogWarning($"FashionRise Magic finished job {r.JobId} with empty image_url");
                else
                    Debug.Log($"FashionRise Magic finished job {r.JobId} image_url={r.ImageUrl}");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise Magic failed: {ex}");
                // Server may already have finished — recover into Your look if possible.
                if (await TryRecoverCompletedLookAsync().ConfigureAwait(true))
                    return;
                _status.text =
                    ex.Message + "\n\nIf Magic finished on the server, tap See last result.";
            }
            finally
            {
                _busy = false;
            }
        }

        async Task<bool> TryRecoverCompletedLookAsync()
        {
            if (!App.IsApiBackend || !App.Auth.HasBackendSession ||
                string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchJobId))
                return false;
            try
            {
                var url = await App.Ai
                    .GetJobImageUrlAsync(App.CreateDesign.LastSketchJobId)
                    .ConfigureAwait(true);
                if (string.IsNullOrEmpty(url))
                    return false;
                Finish(App.CreateDesign.LastSketchJobId, App.CreateDesign.LastSketchSummary, url);
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise Magic recovery failed: {ex.Message}");
                return false;
            }
        }

        async Task RunStyleAsync()
        {
            if (_busy) return;
            _busy = true;
            _status.text = "Gathering style ideas…";
            try
            {
                var r = await App.StyleSuggest.SuggestAsync(new StyleVariationRequest
                {
                    DesignId = null,
                    MoodNotes = "fun, wearable, viral share",
                    LocalSketchForVision = App.CreateDesign.SketchReference
                }).ConfigureAwait(true);
                Finish(r.JobId, r.Summary);
            }
            catch (Exception ex)
            {
                _status.text = ex.Message;
            }
            finally
            {
                _busy = false;
            }
        }

        void Finish(string jobId, string summary, string? imageUrl = null)
        {
            App.CreateDesign.LastSketchJobId = jobId;
            App.CreateDesign.LastSketchSummary = summary;
            App.CreateDesign.LastPolishedImageUrl = imageUrl?.Trim() ?? "";
            App.CreateDesign.LastPolishedImageLocalPath = "";
            _status.text = "Done — opening your look…";
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
        }
    }
}
