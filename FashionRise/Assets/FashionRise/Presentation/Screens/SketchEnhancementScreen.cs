using System;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Kid Magic step. Happy path is one-shot: run Magic → open Your look.
    /// If a look already exists, the primary action is See your look (not Magical again).
    /// </summary>
    public sealed class SketchEnhancementScreen : ScreenBase
    {
        Text _blurb = null!;
        Text _status = null!;
        Button _magicBtn = null!;
        Button _seeLookBtn = null!;
        Button _retryBtn = null!;
        bool _moreOpen;
        bool _autoMagicArmed;
        bool _busy;

        public override ScreenId Id => ScreenId.SketchEnhancement;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "MAGIC", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _blurb = FrUiFactory.AddLabel(col, "B",
                "One tap. Your sketch becomes a runway look.", t,
                Mathf.RoundToInt(t.SubtitleSize), FontStyle.Bold, TextAnchor.UpperCenter,
                useSecondaryTextColor: true);
            _status = FrUiFactory.AddLabel(col, "St", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperCenter);

            _magicBtn = FrUiFactory.AddButton(col, "MAKE IT MAGICAL!", t, () => { _ = RunPolishAsync(); },
                FrButtonEmphasis.Primary);
            Enlarge(_magicBtn);

            _seeLookBtn = FrUiFactory.AddButton(col, "SEE YOUR LOOK", t, () => { _ = OpenLastResultAsync(); },
                FrButtonEmphasis.Primary);
            Enlarge(_seeLookBtn);

            // Retry stays under More so kids don't re-run Magic by accident.
            _retryBtn = FrUiFactory.AddButton(col, "Try magic again", t, () => { _ = RunPolishAsync(); });
            FrUiFactory.AddButton(col, "More…", t, ToggleMore);
            FrUiFactory.AddButton(col, "Clean lines", t, () => { _ = RunCleanAsync(); });
            FrUiFactory.AddButton(col, "Style ideas", t, () => { _ = RunStyleAsync(); });
            FrUiFactory.AddButton(col, "Edit sketch", t, () =>
            {
                App.CreateDesign.ClearLastLook();
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas,
                        new SketchNavContext { RestoreSketch = true });
            });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });

            SetMoreVisible(false);
            RefreshHappyPathChrome();
        }

        protected override void OnShown(object? payload)
        {
            _autoMagicArmed = payload is SketchNavContext { AutoMagic: true } ||
                              payload is true ||
                              (payload is string s && string.Equals(s, "auto", StringComparison.OrdinalIgnoreCase));
            SetMoreVisible(_moreOpen);
            RefreshHappyPathChrome();

            if (_autoMagicArmed)
            {
                _autoMagicArmed = false;
                // Fresh sketch → Magic: clear any previous look so Magical is the action.
                if (!HasReadyLook())
                    _ = RunPolishAsync();
                else
                    _ = OpenLastResultAsync();
            }
        }

        void ToggleMore()
        {
            _moreOpen = !_moreOpen;
            SetMoreVisible(_moreOpen);
            RefreshHappyPathChrome();
        }

        void SetMoreVisible(bool open)
        {
            var col = transform.Find("Root/Col");
            if (col == null)
                return;
            SetSiblingActive(col, "Clean lines_Btn", open);
            SetSiblingActive(col, "Style ideas_Btn", open);
        }

        void RefreshHappyPathChrome()
        {
            var ready = HasReadyLook();
            if (_busy)
            {
                _blurb.text = "Hang tight — Magic is working on your sketch.";
                if (!_status.text.StartsWith("Working", StringComparison.Ordinal) &&
                    !_status.text.StartsWith("Magic is already", StringComparison.Ordinal))
                    _status.text = "Working magic… this can take about a minute.";
                _magicBtn.gameObject.SetActive(false);
                _seeLookBtn.gameObject.SetActive(false);
                _retryBtn.gameObject.SetActive(false);
                return;
            }

            if (ready)
            {
                _blurb.text = "Your look is ready!";
                _status.text = "Open it — or try Magic again under More…";
                _magicBtn.gameObject.SetActive(false);
                _seeLookBtn.gameObject.SetActive(true);
                _retryBtn.gameObject.SetActive(_moreOpen);
            }
            else
            {
                _blurb.text = "One tap. Your sketch becomes a runway look.";
                if (string.IsNullOrWhiteSpace(_status.text) ||
                    _status.text is "Ready." or "Ready when you are.")
                    _status.text = "Ready when you are.";
                _magicBtn.gameObject.SetActive(true);
                _seeLookBtn.gameObject.SetActive(false);
                _retryBtn.gameObject.SetActive(false);
            }
        }

        bool HasReadyLook() =>
            App != null &&
            (!string.IsNullOrWhiteSpace(App.CreateDesign.LastPolishedImageUrl) ||
             !string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchJobId));

        static void SetSiblingActive(Transform col, string name, bool active)
        {
            var child = col.Find(name);
            if (child != null)
                child.gameObject.SetActive(active);
        }

        static void Enlarge(Button btn)
        {
            var le = btn.GetComponent<LayoutElement>();
            if (le != null)
            {
                le.minHeight = 72f;
                le.preferredHeight = 72f;
            }

            var txt = btn.GetComponentInChildren<Text>();
            if (txt != null)
                txt.fontSize = Mathf.Max(txt.fontSize, 22);
        }

        async Task OpenLastResultAsync()
        {
            _status.text = "Opening your look…";
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
                Debug.LogWarning($"FashionRise See your look refresh failed: {ex.Message}");
            }

            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
        }

        async Task RunCleanAsync()
        {
            if (_busy) return;
            _busy = true;
            RefreshHappyPathChrome();
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
                RefreshHappyPathChrome();
            }
        }

        async Task RunPolishAsync()
        {
            if (_busy)
            {
                _status.text = "Magic is already working… hang tight.";
                RefreshHappyPathChrome();
                return;
            }

            _busy = true;
            RefreshHappyPathChrome();
            _status.text = "Working magic… this can take about a minute.";
            try
            {
                var r = await App.ConceptPolish.PolishAsync(new ConceptRefinementRequest
                {
                    DesignId = null,
                    Notes = BuildMagicNotes(),
                    LocalSketchForVision = App.CreateDesign.SketchReference,
                    FabricName = App.CreateDesign.SketchFabricName ?? "",
                    ColorName = App.CreateDesign.SketchColorName ?? "",
                    MaterialPairs = App.CreateDesign.SketchMaterialPairs ?? "",
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
                if (await TryRecoverCompletedLookAsync().ConfigureAwait(true))
                    return;
                _status.text =
                    "Magic hiccuped.\n\nIf it finished, tap See your look — or open More… and try Magic again.";
                // Recover path: if we at least have a job id, surface See your look.
                RefreshHappyPathChrome();
            }
            finally
            {
                _busy = false;
                if (App.Navigation == null ||
                    string.IsNullOrWhiteSpace(App.CreateDesign.LastPolishedImageUrl))
                    RefreshHappyPathChrome();
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
            RefreshHappyPathChrome();
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
                RefreshHappyPathChrome();
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

        string BuildMagicNotes()
        {
            var fabric = App.CreateDesign.SketchFabricName?.Trim() ?? "";
            if (string.IsNullOrEmpty(fabric))
                fabric = App.CreateDesign.MaterialId?.Trim() ?? "";
            var color = App.CreateDesign.SketchColorName?.Trim() ?? "";
            var pairs = App.CreateDesign.SketchMaterialPairs?.Trim() ?? "";

            var sb = new System.Text.StringBuilder();
            sb.Append("CRITICAL: Preserve every colored garment region from the sketch. ");
            sb.Append("Example: an orange silk blouse must stay orange silk; blue denim jeans must stay blue denim. ");
            sb.Append("Never merge a blouse and jeans into one dress. Never recolor one garment with another garment's color. ");

            if (!string.IsNullOrEmpty(pairs))
            {
                sb.Append("Color→fabric map (match sketch ink by color name / hex): ");
                foreach (var part in pairs.Split(';'))
                {
                    var bits = part.Split(':');
                    if (bits.Length < 2)
                        continue;
                    var cName = bits[0].Trim();
                    var fName = bits[1].Trim();
                    var hex = bits.Length >= 3 ? bits[2].Trim() : "";
                    sb.Append(cName);
                    if (!string.IsNullOrEmpty(hex))
                        sb.Append(" (").Append(hex).Append(')');
                    sb.Append(" ink regions = ").Append(fName)
                        .Append(" fabric (").Append(FabricLookHint(fName)).Append("). ");
                }
            }
            else if (!string.IsNullOrEmpty(fabric))
            {
                sb.Append("Primary fabric chosen by the designer: ").Append(fabric).Append(". ");
                sb.Append(FabricLookHint(fabric)).Append(' ');
            }

            if (!string.IsNullOrEmpty(color))
                sb.Append("Last selected studio color: ").Append(color).Append(". ");

            sb.Append(
                "Make each colored region look fashion-forward and nearly real for its paired fabric — " +
                "while staying true to what was drawn.");
            return sb.ToString();
        }

        static string FabricLookHint(string fabric)
        {
            switch (fabric.Trim().ToLowerInvariant())
            {
                case "silk":
                    return "Render garments in luxurious silk: soft sheen, fluid drape, subtle highlights.";
                case "denim":
                    return "Render garments in fashion denim: visible twill weave, structured seams, casual-chic.";
                case "velvet":
                    return "Render garments in rich velvet: deep pile, soft light absorption, luxe runway feel.";
                case "glitter":
                    return "Render garments with glam glitter/sparkle fabric: catch lights, party-fashion energy.";
                case "leather":
                    return "Render garments in fashion leather: smooth grain, soft specular edges, modern edge.";
                case "cotton":
                    return "Render garments in soft fashion cotton: matte, clean folds, fresh ready-to-wear.";
                default:
                    return $"Emphasize realistic {fabric} material qualities on the garments.";
            }
        }
    }
}
