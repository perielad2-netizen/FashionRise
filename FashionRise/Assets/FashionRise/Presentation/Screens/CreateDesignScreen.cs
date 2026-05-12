using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Infrastructure.Platform;
using FashionRise.UI;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class CreateDesignScreen : ScreenBase
    {
        Text _summary = null!;
        RectTransform _screenColumn = null!;
        string _lastPublishMessage = "";
        string _statusNote = "";
        string _lastSpecSheetPdfUrl = "";
        readonly List<GameObject> _proOnlyControls = new();
        IReadOnlyList<DesignRevisionSnapshot> _revisionCache = Array.Empty<DesignRevisionSnapshot>();
        int _revisionCursor;
        const int RevisionPageSize = 25;
        int _revisionOffset;

        public override ScreenId Id => ScreenId.CreateDesign;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            _screenColumn = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            var col = _screenColumn;
            FrUiFactory.AddLabel(col, "H", "Create design", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _summary = FrUiFactory.AddLabel(col, "Sum", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);
            // AddLabel uses a 48px-tall rect; multi-line state was almost entirely clipped so taps looked broken.
            var sumRt = _summary.GetComponent<RectTransform>();
            sumRt.sizeDelta = new Vector2(0f, 0f);
            var sumFit = _summary.gameObject.AddComponent<ContentSizeFitter>();
            sumFit.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            sumFit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            var sumLe = _summary.gameObject.AddComponent<LayoutElement>();
            sumLe.minHeight = 140f;
            sumLe.flexibleWidth = 1f;
            _summary.raycastTarget = false;

            Button AddProButton(string label, Action onClick, FrButtonEmphasis emphasis = FrButtonEmphasis.Secondary)
            {
                var btn = FrUiFactory.AddButton(col, label, t, () => { onClick(); }, emphasis);
                _proOnlyControls.Add(btn.gameObject);
                return btn;
            }

            FrUiFactory.AddButton(col, "Category -> next", t,
                () => { App.CreateDesign.Category = EnumCycle.Next(App.CreateDesign.Category); Refresh(); });
            FrUiFactory.AddButton(col, "Template -> next in category", t, () => { _ = CycleTemplateAsync(); });
            FrUiFactory.AddButton(col, "Neckline -> next", t,
                () => { App.CreateDesign.Neckline = EnumCycle.Next(App.CreateDesign.Neckline); Refresh(); });
            FrUiFactory.AddButton(col, "Sleeve -> next", t,
                () => { App.CreateDesign.Sleeve = EnumCycle.Next(App.CreateDesign.Sleeve); Refresh(); });
            FrUiFactory.AddButton(col, "Length -> next", t,
                () => { App.CreateDesign.Length = EnumCycle.Next(App.CreateDesign.Length); Refresh(); });
            FrUiFactory.AddButton(col, "Fit -> next", t,
                () => { App.CreateDesign.Fit = EnumCycle.Next(App.CreateDesign.Fit); Refresh(); });
            FrUiFactory.AddButton(col, "Waist -> next", t,
                () => { App.CreateDesign.Waist = EnumCycle.Next(App.CreateDesign.Waist); Refresh(); });
            AddProButton("Silhouette volume (V2)",
                () =>
                {
                    App.CreateDesign.SilhouetteVolume = EnumCycle.Next(App.CreateDesign.SilhouetteVolume);
                    Refresh();
                });
            AddProButton("Drape expression (V2)",
                () =>
                {
                    App.CreateDesign.DrapeExpression = EnumCycle.Next(App.CreateDesign.DrapeExpression);
                    Refresh();
                });
            AddProButton("Layering depth (V2)",
                () =>
                {
                    App.CreateDesign.LayeringDepth = EnumCycle.Next(App.CreateDesign.LayeringDepth);
                    Refresh();
                });
            AddProButton("Seam accent (V2)",
                () => { App.CreateDesign.SeamAccent = EnumCycle.Next(App.CreateDesign.SeamAccent); Refresh(); });
            FrUiFactory.AddButton(col, "Palette -> next", t, () => { _ = CyclePaletteAsync(); });
            FrUiFactory.AddButton(col, "Choose material", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.MaterialSelection);
            });
            AddProButton("Model preview", () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ModelPreview);
            });
            FrUiFactory.AddButton(col, "Save draft", t, () => { _ = SaveDraftAsync(); }, FrButtonEmphasis.Primary);
            AddProButton("Show revision history", () => { _ = ListRevisionsAsync(); });
            AddProButton("Older revision page", () => { _ = LoadRevisionPageAsync(+1); });
            AddProButton("Newer revision page", () => { _ = LoadRevisionPageAsync(-1); });
            AddProButton("Select older revision", () => { ShiftRevisionCursor(+1); });
            AddProButton("Select newer revision", () => { ShiftRevisionCursor(-1); });
            AddProButton("Restore selected revision values", () => { _ = RestoreSelectedRevisionAsync(); });
            AddProButton("Restore latest revision values", () => { _ = RestoreLatestRevisionAsync(); });
            FrUiFactory.AddButton(col, "Publish to gallery", t, () => { _ = PublishToGalleryAsync(); },
                FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(col, "Export PNG (mock)", t, () => { _ = ExportAsync(); });
            AddProButton("Copy maker handoff (JSON)", () => { _ = CopyMakerHandoffAsync(); });
            AddProButton("Copy spec sheet (JSON)", () => { _ = CopySpecSheetHandoffAsync(); });
            AddProButton("Generate spec sheet PDF (placeholder)",
                () => { _ = GenerateSpecSheetPdfPlaceholderAsync(); });
            AddProButton("Open last spec sheet PDF URL", OpenLastSpecSheetPdfUrl);
            AddProButton("Share last spec sheet PDF URL", ShareLastSpecSheetPdfUrl);
            AddProButton("Download last spec sheet PDF", () => { _ = DownloadLastSpecSheetPdfAsync(); });
            if (PcHandoffsFolderOpener.IsSupported)
                AddProButton("Open Handoffs folder (PC)", PcHandoffsFolderOpener.TryOpenHandoffsFolder);
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });

            ApplyAuthoringModeUi();
        }

        protected override void OnShown(object? payload) => _ = BootstrapDefaultsAsync();

        async Task BootstrapDefaultsAsync()
        {
            _statusNote = "";
            if (string.IsNullOrEmpty(App.CreateDesign.TemplateId))
            {
                var tpl = await App.Templates.GetTemplatesAsync(App.CreateDesign.Category).ConfigureAwait(true);
                if (tpl.Count > 0)
                    App.CreateDesign.TemplateId = tpl[0].Id;
            }

            if (string.IsNullOrEmpty(App.CreateDesign.ColorPaletteId))
            {
                var pal = await App.Palettes.GetPalettesAsync().ConfigureAwait(true);
                if (pal.Count > 0)
                    App.CreateDesign.ColorPaletteId = pal[0].Id;
            }

            if (App.IsApiBackend)
            {
                var mats = await App.Materials.GetMaterialsAsync().ConfigureAwait(true);
                if (mats.Count > 0 &&
                    (string.IsNullOrEmpty(App.CreateDesign.MaterialId) ||
                     !System.Guid.TryParse(App.CreateDesign.MaterialId, out _)))
                    App.CreateDesign.MaterialId = mats[0].Id;
            }
            else if (string.IsNullOrEmpty(App.CreateDesign.MaterialId))
            {
                App.CreateDesign.MaterialId = "mat_satin";
            }

            Refresh();
        }

        void Refresh()
        {
            var s = App.CreateDesign;
            var asOn = DesignAutosavePreferences.IsEnabled;
            var asSec = DesignAutosavePreferences.GetIntervalSeconds();
            var mode = AuthoringModePreferences.IsProMode ? "Pro" : "Guided";
            _summary.text =
                $"Category: {s.Category}\n" +
                $"Template: {s.TemplateId}\n" +
                $"Neckline: {s.Neckline}  Sleeve: {s.Sleeve}\n" +
                $"Length: {s.Length}  Fit: {s.Fit}  Waist: {s.Waist}\n" +
                $"V2: vol {s.SilhouetteVolume}  drape {s.DrapeExpression}  layer {s.LayeringDepth}  seam {s.SeamAccent}\n" +
                $"Sketch ref: {s.SketchReference}\n" +
                $"Palette: {s.ColorPaletteId}\n" +
                $"Material: {s.MaterialId}\n" +
                $"Mode: {mode}\n" +
                $"Autosave: {(asOn ? $"on ({asSec}s)" : "off")} — Settings";
            if (!string.IsNullOrEmpty(_statusNote))
                _summary.text += "\n\n" + _statusNote;
            if (!string.IsNullOrEmpty(_lastPublishMessage))
                _summary.text += "\n" + _lastPublishMessage;

            ApplyAuthoringModeUi();
            UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(_screenColumn);
        }

        void ApplyAuthoringModeUi()
        {
            var showPro = AuthoringModePreferences.IsProMode;
            foreach (var go in _proOnlyControls)
            {
                if (go != null)
                    go.SetActive(showPro);
            }
        }

        async Task CycleTemplateAsync()
        {
            var list = await App.Templates.GetTemplatesAsync(App.CreateDesign.Category).ConfigureAwait(true);
            if (list.Count == 0)
            {
                _statusNote = "No templates for this category (check API / catalog).";
                Refresh();
                return;
            }
            var idx = string.IsNullOrEmpty(App.CreateDesign.TemplateId)
                ? 0
                : System.Math.Max(0, list.ToList().FindIndex(t => t.Id == App.CreateDesign.TemplateId));
            var next = list[(idx + 1) % list.Count];
            App.CreateDesign.TemplateId = next.Id;
            Refresh();
        }

        async Task CyclePaletteAsync()
        {
            var list = await App.Palettes.GetPalettesAsync().ConfigureAwait(true);
            if (list.Count == 0)
            {
                _statusNote = "No palettes returned (check API).";
                Refresh();
                return;
            }
            var idx = string.IsNullOrEmpty(App.CreateDesign.ColorPaletteId)
                ? 0
                : System.Math.Max(0, list.ToList().FindIndex(p => p.Id == App.CreateDesign.ColorPaletteId));
            var next = list[(idx + 1) % list.Count];
            App.CreateDesign.ColorPaletteId = next.Id;
            Refresh();
        }

        async Task LoadRevisionPageAsync(int pageDelta)
        {
            _revisionOffset += pageDelta * RevisionPageSize;
            if (_revisionOffset < 0)
                _revisionOffset = 0;
            await ListRevisionsAsync().ConfigureAwait(true);
        }

        async Task ListRevisionsAsync()
        {
            _lastPublishMessage = "";
            if (!App.IsApiBackend || !App.Auth.HasBackendSession)
            {
                _statusNote = "Use API sign-in to load revision history from the server.";
                Refresh();
                return;
            }

            var id = App.CreateDesign.PersistedDesignId;
            if (string.IsNullOrEmpty(id) || !Guid.TryParse(id, out _))
            {
                _statusNote = "Save draft first so this design has a server id and snapshots.";
                Refresh();
                return;
            }

            try
            {
                var list = await App.DesignSave.ListRevisionSnapshotsAsync(id, limit: RevisionPageSize,
                        offset: _revisionOffset)
                    .ConfigureAwait(true);
                if (list.Count == 0 && _revisionOffset > 0)
                {
                    _revisionOffset = Math.Max(0, _revisionOffset - RevisionPageSize);
                    _statusNote = "No more older revisions.";
                    Refresh();
                    return;
                }

                _revisionCache = list;
                _revisionCursor = 0;
                if (list.Count == 0)
                {
                    _statusNote = "No snapshots yet. Save draft again or wait for autosave.";
                    Refresh();
                    return;
                }

                var sb = new StringBuilder();
                var page = (_revisionOffset / RevisionPageSize) + 1;
                sb.AppendLine($"Recent revisions (newest first) — page {page}, offset {_revisionOffset}:");
                var top = Math.Min(20, list.Count);
                for (var i = 0; i < top; i++)
                {
                    var r = list[i];
                    var note = r.Notes;
                    if (!string.IsNullOrEmpty(note) && note.Length > 40)
                        note = note.Substring(0, 37) + "…";
                    var notePart = string.IsNullOrEmpty(note) ? "" : $" — {note}";
                    var marker = i == _revisionCursor ? ">" : " ";
                    sb.AppendLine($"{marker} #{r.RevisionNumber}  {r.CreatedAtUtc:yyyy-MM-dd HH:mm} UTC{notePart}");
                }
                if (_revisionOffset > 0)
                    sb.AppendLine("Use 'Newer revision page' to move toward latest.");
                if (list.Count == RevisionPageSize)
                    sb.AppendLine("Use 'Older revision page' for deeper history.");

                _statusNote = sb.ToString().TrimEnd();
            }
            catch (Exception ex)
            {
                _statusNote = $"Could not load revisions: {ex.Message}";
            }

            Refresh();
        }

        void ShiftRevisionCursor(int delta)
        {
            if (_revisionCache.Count == 0)
            {
                _statusNote = "Load revision history first.";
                Refresh();
                return;
            }

            var next = _revisionCursor + delta;
            if (next < 0)
                next = 0;
            if (next >= _revisionCache.Count)
                next = _revisionCache.Count - 1;
            _revisionCursor = next;

            var selected = _revisionCache[_revisionCursor];
            var page = (_revisionOffset / RevisionPageSize) + 1;
            _statusNote =
                $"Selected revision #{selected.RevisionNumber} ({_revisionCursor + 1}/{_revisionCache.Count}) on page {page}.";
            Refresh();
        }

        void ApplyDraftToSession(GarmentDesign design)
        {
            App.CreateDesign.Category = design.Category;
            App.CreateDesign.TemplateId = design.TemplateId;
            App.CreateDesign.Neckline = design.Neckline;
            App.CreateDesign.Sleeve = design.Sleeve;
            App.CreateDesign.Length = design.Length;
            App.CreateDesign.Fit = design.Fit;
            App.CreateDesign.Waist = design.Waist;
            App.CreateDesign.ColorPaletteId = design.ColorPaletteId;
            App.CreateDesign.MaterialId = design.MaterialId;
            App.CreateDesign.SilhouetteVolume = design.SilhouetteVolume;
            App.CreateDesign.DrapeExpression = design.DrapeExpression;
            App.CreateDesign.LayeringDepth = design.LayeringDepth;
            App.CreateDesign.SeamAccent = design.SeamAccent;
            App.CreateDesign.TrimNotes = design.TrimNotes;
            App.CreateDesign.AccentNotes = design.AccentNotes;
            App.CreateDesign.SketchReference = design.SketchReference;
        }

        async Task RestoreLatestRevisionAsync()
        {
            _lastPublishMessage = "";
            if (!App.IsApiBackend || !App.Auth.HasBackendSession)
            {
                _statusNote = "Use API sign-in to restore revision values.";
                Refresh();
                return;
            }

            var id = App.CreateDesign.PersistedDesignId;
            if (string.IsNullOrEmpty(id) || !Guid.TryParse(id, out _))
            {
                _statusNote = "Save draft first so this design has server revision history.";
                Refresh();
                return;
            }

            try
            {
                var revisions = await App.DesignSave.ListRevisionSnapshotsAsync(id, limit: 1, offset: 0)
                    .ConfigureAwait(true);
                if (revisions.Count == 0)
                {
                    _statusNote = "No snapshots to restore yet.";
                    Refresh();
                    return;
                }

                var latest = revisions[0];
                _revisionCache = revisions;
                _revisionCursor = 0;
                _revisionOffset = 0;
                var baseDraft = App.CreateDesign.ToDraft(App.Auth.CurrentSessionUserId ?? "unknown", "Studio draft");
                var restored = await App.DesignSave
                    .ApplyRevisionToDesignAsync(id, latest.RevisionNumber, baseDraft)
                    .ConfigureAwait(true);
                if (restored == null)
                {
                    _statusNote = $"Could not restore revision #{latest.RevisionNumber}.";
                    Refresh();
                    return;
                }

                ApplyDraftToSession(restored);
                _statusNote = $"Restored values from revision #{latest.RevisionNumber}.";
            }
            catch (Exception ex)
            {
                _statusNote = $"Restore failed: {ex.Message}";
            }

            Refresh();
        }

        async Task RestoreSelectedRevisionAsync()
        {
            _lastPublishMessage = "";
            if (!App.IsApiBackend || !App.Auth.HasBackendSession)
            {
                _statusNote = "Use API sign-in to restore revision values.";
                Refresh();
                return;
            }

            var id = App.CreateDesign.PersistedDesignId;
            if (string.IsNullOrEmpty(id) || !Guid.TryParse(id, out _))
            {
                _statusNote = "Save draft first so this design has server revision history.";
                Refresh();
                return;
            }

            if (_revisionCache.Count == 0)
            {
                _statusNote = "Load revision history first.";
                Refresh();
                return;
            }

            var selected = _revisionCache[_revisionCursor];
            try
            {
                var baseDraft = App.CreateDesign.ToDraft(App.Auth.CurrentSessionUserId ?? "unknown", "Studio draft");
                var restored = await App.DesignSave
                    .ApplyRevisionToDesignAsync(id, selected.RevisionNumber, baseDraft)
                    .ConfigureAwait(true);
                if (restored == null)
                {
                    _statusNote = $"Could not restore revision #{selected.RevisionNumber}.";
                    Refresh();
                    return;
                }

                ApplyDraftToSession(restored);
                _statusNote = $"Restored values from revision #{selected.RevisionNumber}.";
            }
            catch (Exception ex)
            {
                _statusNote = $"Restore failed: {ex.Message}";
            }

            Refresh();
        }

        async Task SaveDraftAsync()
        {
            _statusNote = "";
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
            {
                _statusNote = "Sign in (Profile) to save drafts to the server.";
                Refresh();
                return;
            }

            var d = App.CreateDesign.ToDraft(uid, "Studio draft");
            try
            {
                d = await App.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
                App.CreateDesign.PersistedDesignId = d.Id;
                _statusNote = "Draft saved.";
                Refresh();
            }
            catch (System.Exception ex)
            {
                _statusNote = $"Save draft failed: {ex.Message}";
                UnityEngine.Debug.LogWarning($"Save draft failed: {ex.Message}");
                Refresh();
            }
        }

        async Task ExportAsync()
        {
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return;
            var d = App.CreateDesign.ToDraft(uid, "Export");
            if (App.Auth.HasBackendSession)
            {
                try
                {
                    d = await App.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
                    App.CreateDesign.PersistedDesignId = d.Id;
                }
                catch (System.Exception ex)
                {
                    UnityEngine.Debug.LogWarning($"Save before export failed: {ex.Message}");
                }
            }

            var req = new ExportRequest { DesignId = d.Id, FileName = "fashionrise_look" };
            await App.Export.ExportPngAsync(req).ConfigureAwait(true);
        }

        async Task CopyMakerHandoffAsync()
        {
            await CopyHandoffByKindAsync("manifest_v1", "Maker handoff JSON copied to clipboard.")
                .ConfigureAwait(true);
        }

        async Task CopySpecSheetHandoffAsync()
        {
            await CopyHandoffByKindAsync("spec_sheet_v1", "Spec sheet JSON copied to clipboard.")
                .ConfigureAwait(true);
        }

        async Task GenerateSpecSheetPdfPlaceholderAsync()
        {
            await CopyHandoffByKindAsync("spec_sheet_pdf",
                "Spec sheet PDF placeholder generated; payload copied to clipboard.")
                .ConfigureAwait(true);
        }

        void OpenLastSpecSheetPdfUrl()
        {
            _lastPublishMessage = "";
            if (string.IsNullOrEmpty(_lastSpecSheetPdfUrl))
            {
                _lastPublishMessage = "Generate spec sheet PDF first to get a URL.";
                Refresh();
                return;
            }

            UnityEngine.Application.OpenURL(_lastSpecSheetPdfUrl);
            _lastPublishMessage = $"Opened PDF URL:\n{_lastSpecSheetPdfUrl}";
            Refresh();
        }

        void ShareLastSpecSheetPdfUrl()
        {
            _lastPublishMessage = "";
            if (string.IsNullOrEmpty(_lastSpecSheetPdfUrl))
            {
                _lastPublishMessage = "Generate spec sheet PDF first to get a URL.";
                Refresh();
                return;
            }

            if (NativeShareSheet.TryShareText(_lastSpecSheetPdfUrl, "FashionRise spec sheet PDF"))
                _lastPublishMessage = "Opened native share options for PDF URL.";
            else
            {
                ShareClipboard.Copy(_lastSpecSheetPdfUrl);
                _lastPublishMessage = $"Native share unavailable here; copied PDF URL:\n{_lastSpecSheetPdfUrl}";
            }

            Refresh();
        }

        async Task DownloadLastSpecSheetPdfAsync()
        {
            _lastPublishMessage = "";
            Refresh();
            var url = _lastSpecSheetPdfUrl?.Trim() ?? "";
            if (string.IsNullOrEmpty(url))
            {
                _lastPublishMessage = "Generate spec sheet PDF first to get a URL.";
                Refresh();
                return;
            }

            if (!(url.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                  url.StartsWith("https://", StringComparison.OrdinalIgnoreCase)))
            {
                _lastPublishMessage = "Spec sheet PDF URL is not a web URL.";
                Refresh();
                return;
            }

            try
            {
                using var req = UnityWebRequest.Get(url);
                req.timeout = 30;
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32).ConfigureAwait(true);

                if (req.result != UnityWebRequest.Result.Success)
                {
                    _lastPublishMessage = $"PDF download failed: {req.error}";
                    Refresh();
                    return;
                }

                var bytes = req.downloadHandler.data;
                if (bytes == null || bytes.Length == 0)
                {
                    _lastPublishMessage = "PDF download failed: empty file.";
                    Refresh();
                    return;
                }

                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Handoffs");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"spec_sheet_{DateTime.UtcNow:yyyyMMdd_HHmmss}.pdf");
                File.WriteAllBytes(path, bytes);
                _lastPublishMessage = $"Spec sheet PDF downloaded to:\n{path}";
                Refresh();
            }
            catch (Exception ex)
            {
                _lastPublishMessage = $"PDF download failed: {ex.Message}";
                Refresh();
            }
        }

        static string? TryExtractExportFileUrl(string json)
        {
            try
            {
                var obj = JObject.Parse(json);
                return obj["export"]?["file_url"]?.Value<string>();
            }
            catch
            {
                return null;
            }
        }

        async Task CopyHandoffByKindAsync(string exportKind, string okMessage)
        {
            _lastPublishMessage = "";
            if (!string.Equals(exportKind, "spec_sheet_pdf", StringComparison.Ordinal))
                _lastSpecSheetPdfUrl = "";
            Refresh();
            if (string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
            {
                _lastPublishMessage = "Sign in first.";
                Refresh();
                return;
            }

            if (App.IsApiBackend && !App.Auth.HasBackendSession)
            {
                _lastPublishMessage = "Use API sign-in to fetch handoff from the server.";
                Refresh();
                return;
            }

            if (string.IsNullOrEmpty(App.CreateDesign.PersistedDesignId))
            {
                _lastPublishMessage = "Save draft first (need a persisted design id).";
                Refresh();
                return;
            }

            try
            {
                var json = await App.Handoff.GetHandoffManifestJsonAsync(App.CreateDesign.PersistedDesignId, exportKind)
                    .ConfigureAwait(true);
                if (string.IsNullOrEmpty(json))
                {
                    _lastPublishMessage = "Handoff not available (design not found).";
                    Refresh();
                    return;
                }

                ShareClipboard.Copy(json);
                _lastPublishMessage = okMessage;
                if (exportKind == "spec_sheet_pdf")
                {
                    var fileUrl = TryExtractExportFileUrl(json);
                    if (!string.IsNullOrEmpty(fileUrl))
                    {
                        _lastSpecSheetPdfUrl = fileUrl;
                        _lastPublishMessage += $"\nPDF file URL:\n{fileUrl}";
                    }
                }
                Refresh();
            }
            catch (Exception ex)
            {
                _lastPublishMessage = $"Handoff failed: {ex.Message}";
                Refresh();
            }
        }

        async Task PublishToGalleryAsync()
        {
            _lastPublishMessage = "";
            Refresh();
            var (ok, err) = await EnsurePersistedDesignForGalleryAsync().ConfigureAwait(true);
            if (!ok)
            {
                _lastPublishMessage = err ?? "Could not prepare design for gallery.";
                Refresh();
                return;
            }

            var designId = App.CreateDesign.PersistedDesignId;
            var title = $"{App.CreateDesign.Category} look";
            try
            {
                string? previewUrl = null;
                if (App.IsApiBackend && App.Auth.HasBackendSession)
                {
                    var ex = await App.Export
                        .ExportPngAsync(new ExportRequest
                        {
                            DesignId = designId,
                            FileName = "gallery_preview",
                            SkipExportRegistration = true
                        })
                        .ConfigureAwait(true);
                    previewUrl = ex.UploadedImageUrl;
                }

                var published = await App.Gallery.PublishDesignAsync(designId, title, previewUrl)
                    .ConfigureAwait(true);
                var url = App.ShareLinks.BuildGalleryItemUrl(published.Id);
                var card = App.ShareLinks.BuildShareCardText(title, published.Id, previewUrl);
                var sharedNatively = NativeShareSheet.TryShareText(card, "FashionRise share card");
                if (!sharedNatively)
                    ShareClipboard.Copy(card);
                _lastPublishMessage = (string.IsNullOrEmpty(previewUrl)
                    ? "Published (no preview image).\n"
                    : "Published with preview.\n") +
                    (sharedNatively ? "Opened native share options for share card.\n" : "Share card copied to clipboard.\n") +
                    url;
                Refresh();
                if (App.Navigation != null)
                    await App.Navigation
                        .NavigateToAsync(ScreenId.Gallery,
                            new GalleryNavContext { CommunitySort = GallerySort.Newest })
                        .ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                _lastPublishMessage = $"Publish failed: {ex.Message}";
                Refresh();
            }
        }

        async Task<(bool ok, string? err)> EnsurePersistedDesignForGalleryAsync()
        {
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return (false, "Sign in first.");
            if (App.IsApiBackend && !App.Auth.HasBackendSession)
                return (false, "Use API sign-in (email/password) to publish.");

            if (App.IsApiBackend && App.Auth.HasBackendSession &&
                !string.IsNullOrEmpty(App.CreateDesign.PersistedDesignId) &&
                Guid.TryParse(App.CreateDesign.PersistedDesignId, out _))
                return (true, null);

            if (!App.IsApiBackend &&
                !string.IsNullOrEmpty(App.CreateDesign.PersistedDesignId))
                return (true, null);

            try
            {
                var d = App.CreateDesign.ToDraft(uid, "Studio draft");
                var saved = await App.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
                App.CreateDesign.PersistedDesignId = saved.Id;
                if (App.IsApiBackend && !Guid.TryParse(saved.Id, out _))
                    return (false, "Save draft first — design id is not a server UUID.");
                return (true, null);
            }
            catch (Exception ex)
            {
                return (false, ex.Message);
            }
        }
    }
}
