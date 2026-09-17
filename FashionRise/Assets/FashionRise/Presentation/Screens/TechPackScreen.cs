using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Content;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Create Real Design output — a printed-style FASHION TECHNICAL SPECIFICATION sheet:
    /// header block, front/back flats, sample size base, materials &amp; notions, pattern
    /// pieces, cutting layout and construction order. Measurements are a first draft.
    /// The sheet is built one card per frame so a long spec never stalls a frame, and every
    /// step leaves a breadcrumb in <see cref="FrDiag"/>.
    /// </summary>
    public sealed class TechPackScreen : ScreenBase
    {
        // Hard caps: a runaway model response must not build an unbounded UI mesh.
        const int MaxRowsPerTable = 40;
        const int MaxCellChars = 260;
        const int MaxParagraphChars = 1400;

        FashionRiseTheme _t = null!;
        Text _styleLine = null!;
        Text _garmentLine = null!;
        RectTransform _sheet = null!;
        RawImage? _front;
        RawImage? _back;
        RawImage? _pattern;
        Texture2D? _ownedFront;
        Texture2D? _ownedBack;
        Texture2D? _ownedPattern;
        FrAiLoadingFx? _loading;
        CancellationTokenSource? _cts;
        readonly CancellationTokenSource _life = new();
        Coroutine? _render;
        Coroutine? _copy;
        bool _busy;
        bool _rendering;
        bool _renderPending;
        bool _chromeReady;

        public override ScreenId Id => ScreenId.TechPack;

        void Awake()
        {
            try
            {
                _t = ThemeOrDefault;
                var root = FrUiFactory.CreateStretchPanel(transform, "Root", _t);
                _loading = FrAiLoadingFx.Create(root, _t);

                BuildHeader(root);
                BuildBottomBar(root);
                BuildSheetScroll(root);
                _chromeReady = true;
            }
            catch (Exception ex)
            {
                FrDiag.Fail("techpack build chrome", ex);
                Debug.LogError($"FashionRise TechPackScreen could not build its UI: {ex}");
            }
        }

        void BuildHeader(RectTransform root)
        {
            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var rt = top.GetComponent<RectTransform>();
            rt.SetParent(root, false);
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(0f, 96f);
            var v = top.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(20, 20, 14, 4);
            v.spacing = 1f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            var title = FrUiFactory.AddLabel(top.transform, "H",
                FrUiFactory.Space("Fashion Technical Specification"), _t,
                Mathf.RoundToInt(_t.SubtitleSize), FontStyle.Normal, TextAnchor.MiddleCenter);
            title.font = FrUiFonts.UiMedium;
            FrUiFactory.AddHairline(top.transform, _t);
            _styleLine = FrUiFactory.AddLabel(top.transform, "Style", "STYLE NO.  FR-001", _t,
                Mathf.RoundToInt(_t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);
            _garmentLine = FrUiFactory.AddLabel(top.transform, "Garment", "", _t,
                Mathf.RoundToInt(_t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);
        }

        void BuildBottomBar(RectTransform root)
        {
            const float h = 104f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var rt = bottom.GetComponent<RectTransform>();
            rt.SetParent(root, false);
            rt.anchorMin = new Vector2(0f, 0f);
            rt.anchorMax = new Vector2(1f, 0f);
            rt.pivot = new Vector2(0.5f, 0f);
            rt.sizeDelta = new Vector2(0f, h);
            var v = bottom.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(18, 18, 4, 12);
            v.spacing = 6f;
            v.childAlignment = TextAnchor.LowerCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            var note = FrUiFactory.AddLabel(bottom.transform, "Disc",
                "First production draft — edit measurements, fabric and pattern before manufacturing.",
                _t, Mathf.RoundToInt(_t.OverlineSize + 1f), FontStyle.Normal, TextAnchor.MiddleCenter, true);
            var noteLe = note.GetComponent<LayoutElement>();
            noteLe.minHeight = 16f;
            noteLe.preferredHeight = 18f;

            var row = new GameObject("Actions", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(bottom.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.minHeight = 46f;
            rowLe.preferredHeight = 46f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 8f;
            rowH.childForceExpandWidth = true;
            rowH.childControlWidth = true;
            rowH.childControlHeight = true;

            FrUiFactory.AddButton(row.transform, "Export PDF", _t, ExportSpec, FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(row.transform, "Regenerate", _t, Regenerate);
            FrUiFactory.AddButton(row.transform, "Back", _t, GoBack, FrButtonEmphasis.Ghost);
        }

        void BuildSheetScroll(RectTransform root)
        {
            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(RectMask2D));
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.SetParent(root, false);
            scrollRt.anchorMin = Vector2.zero;
            scrollRt.anchorMax = Vector2.one;
            scrollRt.offsetMin = new Vector2(14f, 108f);
            scrollRt.offsetMax = new Vector2(-14f, -100f);

            var content = new GameObject("Sheet", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            _sheet = content.GetComponent<RectTransform>();
            _sheet.SetParent(scrollRt, false);
            _sheet.anchorMin = new Vector2(0f, 1f);
            _sheet.anchorMax = new Vector2(1f, 1f);
            _sheet.pivot = new Vector2(0.5f, 1f);
            _sheet.sizeDelta = Vector2.zero;
            var v = content.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(0, 0, 0, 24);
            v.spacing = 12f;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.content = _sheet;
            scroll.viewport = scrollRt;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Elastic;
            scroll.scrollSensitivity = 34f;
        }

        // ---------- lifecycle ----------

        public override Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            Debug.Log("FashionRise TechPack: ShowAsync");
            gameObject.SetActive(true);
            if (!_chromeReady)
                return Task.CompletedTask;

            if (!string.IsNullOrWhiteSpace(App.CreateDesign.LastTechPackJson))
            {
                FrDiag.Step("techpack: reuse cached spec");
                RequestRender();
                return Task.CompletedTask;
            }

            // Never await generation from navigation: the flow stays responsive and a slow or
            // failing job can't hold the screen transition open.
            FrDiag.Fire(GenerateAsync(), "techpack generate");
            return Task.CompletedTask;
        }

        public override Task HideAsync(CancellationToken cancellationToken = default)
        {
            CancelWork();
            gameObject.SetActive(false);
            return Task.CompletedTask;
        }

        void GoBack()
        {
            CancelWork();
            if (App.Navigation != null)
                FrDiag.Fire(App.Navigation.NavigateToAsync(ScreenId.ConceptResult), "navigate ConceptResult");
        }

        void Regenerate()
        {
            if (_busy)
                return;
            App.CreateDesign.ClearTechPack();
            FrDiag.Fire(GenerateAsync(), "techpack regenerate");
        }

        void CancelWork()
        {
            try
            {
                _cts?.Cancel();
            }
            catch (ObjectDisposedException)
            {
                /* already gone */
            }

            StopLoadingCopy();
            _loading?.Hide();
        }

        void OnDisable()
        {
            StopLoadingCopy();
            if (_rendering)
                _renderPending = true; // Unity kills coroutines on disable; finish the sheet on return
        }

        // ---------- generation ----------

        async Task GenerateAsync()
        {
            if (_busy)
                return;
            _busy = true;
            ClearSheet();
            ShowLoading("Reading your look…");
            FrDiag.Step("techpack: generate start");

            var cts = new CancellationTokenSource(TimeSpan.FromMinutes(7));
            _cts?.Dispose();
            _cts = cts;
            try
            {
                var result = await App.TechPack.GenerateAsync(new Domain.TechPackRequest
                {
                    DesignId = App.CreateDesign.PersistedDesignId,
                    Notes = App.CreateDesign.LastSketchSummary,
                    LocalSketchForVision = ResolveVisionImagePath(),
                    PolishedImageUrl = App.CreateDesign.LastPolishedImageUrl,
                    FabricName = App.CreateDesign.SketchFabricName,
                    ColorName = App.CreateDesign.SketchColorName,
                    MaterialPairs = App.CreateDesign.SketchMaterialPairs,
                    OnJobStarted = id =>
                    {
                        App.CreateDesign.LastTechPackJobId = id;
                        FrDiag.Step($"techpack: job {id} queued");
                        SetLoadingStatus("Drafting pattern pieces & measurements…");
                    }
                }, cts.Token).ConfigureAwait(true);

                App.CreateDesign.LastTechPackJobId = result.JobId;
                App.CreateDesign.LastTechPackJson = result.RawJson;
                App.CreateDesign.LastTechPackFrontImageUrl = result.FrontImageUrl;
                App.CreateDesign.LastTechPackBackImageUrl = result.BackImageUrl;
                App.CreateDesign.LastTechPackPatternImageUrl = result.PatternImageUrl;
                App.CreateDesign.LastTechPackPdfUrl = result.PdfUrl;
                FrDiag.Step($"techpack: job {result.JobId} {result.Status}, json {result.RawJson?.Length ?? 0} chars");

                if (string.Equals(result.Status, "failed", StringComparison.OrdinalIgnoreCase))
                {
                    ShowError(string.IsNullOrWhiteSpace(result.Summary) ? "The studio job failed." : result.Summary);
                    return;
                }

                RequestRender();
            }
            catch (OperationCanceledException)
            {
                FrDiag.Step("techpack: generation cancelled");
            }
            catch (Exception ex)
            {
                FrDiag.Fail("techpack generate", ex);
                ShowError(ex.Message);
            }
            finally
            {
                _busy = false;
                StopLoadingCopy();
                _loading?.Hide();
            }
        }

        /// <summary>
        /// Prefer the finished Magic look (real colours, fabric, shading) over the transparent
        /// ink layer — the tech pack should describe what the designer actually approved.
        /// </summary>
        string ResolveVisionImagePath()
        {
            var look = App.CreateDesign.LastPolishedImageLocalPath?.Trim() ?? "";
            if (!string.IsNullOrEmpty(look) && File.Exists(look))
                return look;

            var ink = App.CreateDesign.LastInkImagePath?.Trim() ?? "";
            if (!string.IsNullOrEmpty(ink) && File.Exists(ink))
                return ink;

            var raw = App.CreateDesign.SketchReference?.Trim() ?? "";
            return raw.StartsWith("file:", StringComparison.OrdinalIgnoreCase) ? raw.Substring(5) : raw;
        }

        // ---------- loading state ----------

        void ShowLoading(string status)
        {
            if (_loading == null)
                return;
            _loading.Show(status);
            StopLoadingCopy();
            if (isActiveAndEnabled)
                _copy = StartCoroutine(LoadingCopyRoutine());
        }

        void SetLoadingStatus(string status) => _loading?.SetStatus(status);

        void StopLoadingCopy()
        {
            if (_copy == null)
                return;
            StopCoroutine(_copy);
            _copy = null;
        }

        IEnumerator LoadingCopyRoutine()
        {
            var lines = new[]
            {
                "Measuring the sample body — 170 cm, 84 / 64 / 90…",
                "Drafting pattern pieces and seam allowances…",
                "Drawing the technical flats…",
                "Nesting the cutting layout on 150 cm fabric…",
                "Writing the construction order…"
            };
            var i = 0;
            while (true)
            {
                yield return new WaitForSecondsRealtime(4.5f);
                SetLoadingStatus(lines[i % lines.Length]);
                i++;
            }
        }

        // ---------- sheet rendering ----------

        void ClearSheet()
        {
            if (_render != null)
            {
                StopCoroutine(_render);
                _render = null;
            }

            _rendering = false;
            _front = null;
            _back = null;
            _pattern = null;
            if (_sheet == null)
                return;
            for (var i = _sheet.childCount - 1; i >= 0; i--)
                Destroy(_sheet.GetChild(i).gameObject);
        }

        void RequestRender()
        {
            if (!_chromeReady)
                return;
            if (!isActiveAndEnabled)
            {
                _renderPending = true;
                return;
            }

            _renderPending = false;
            ClearSheet();
            _render = StartCoroutine(RenderRoutine());
        }

        void OnEnable()
        {
            if (_renderPending)
                RequestRender();
        }

        IEnumerator RenderRoutine()
        {
            _rendering = true;
            var json = App.CreateDesign.LastTechPackJson;
            if (string.IsNullOrWhiteSpace(json))
            {
                _rendering = false;
                yield break;
            }

            JObject? root = null;
            try
            {
                root = JObject.Parse(json);
            }
            catch (Exception ex)
            {
                FrDiag.Fail("techpack parse", ex);
            }

            if (root == null)
            {
                var raw = FrUiFactory.AddSpecCard(_sheet, "Raw result", _t);
                FrUiFactory.AddSpecParagraph(raw, Clamp(json, MaxParagraphChars), _t, ContentWidth);
                _rendering = false;
                yield break;
            }

            var garment = root["garment"] as JObject;
            var garmentType = Str(garment?["type"], "Garment");
            SafeSet(_garmentLine, "GARMENT   " + garmentType.ToUpperInvariant());
            SafeSet(_styleLine, "STYLE NO.  FR-" + ShortCode(App.CreateDesign.LastTechPackJobId));

            var steps = new List<(string Name, Action Build)>
            {
                ("design", () => BuildDesignCard(root!, garment, garmentType)),
                ("flats", BuildFlatsCard),
                ("measurements", () => BuildMeasurementsCard(root!)),
                ("materials", () => BuildMaterialsCard(root!)),
                ("pattern", () => BuildPatternCard(root!)),
                ("cutting", () => BuildCuttingCard(root!)),
                ("construction", () => BuildConstructionCard(root!)),
                ("special", () => BuildSpecialCard(root!))
            };

            foreach (var step in steps)
            {
                try
                {
                    step.Build();
                }
                catch (Exception ex)
                {
                    FrDiag.Fail("techpack render " + step.Name, ex);
                }

                yield return null; // one card per frame keeps the sheet smooth on any device
            }

            _rendering = false;
            _render = null;
            FrDiag.Step("techpack: sheet rendered");
            FrDiag.Fire(LoadFlatsAsync(_life.Token), "techpack load flats");
        }

        float ContentWidth
        {
            get
            {
                var w = _sheet != null ? _sheet.rect.width : 0f;
                if (w < 40f && transform is RectTransform self)
                    w = self.rect.width - 28f;
                return Mathf.Clamp(w, 320f, 2200f);
            }
        }

        void BuildDesignCard(JObject root, JObject? garment, string garmentType)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Design", _t);
            AddRow(card, "Garment", garmentType);
            if (garment != null)
            {
                AddIfPresent(card, "Silhouette", garment["silhouette"]);
                AddIfPresent(card, "Neckline", garment["neckline"]);
                AddIfPresent(card, "Sleeves", garment["sleeves"]);
                AddIfPresent(card, "Closure", garment["closure"]);
            }

            var fabric = App.CreateDesign.SketchFabricName;
            if (!string.IsNullOrWhiteSpace(fabric))
                AddRow(card, "Studio fabric", fabric);
            var color = App.CreateDesign.SketchColorName;
            if (!string.IsNullOrWhiteSpace(color))
                AddRow(card, "Studio colour", color);

            var description = Str(garment?["construction_description"], "");
            if (string.IsNullOrEmpty(description))
                description = Str(root["summary"], "");
            if (!string.IsNullOrEmpty(description))
            {
                FrUiFactory.AddSpecBandRow(card, "Description", _t);
                FrUiFactory.AddSpecParagraph(card, Clamp(description, MaxParagraphChars), _t, ContentWidth);
            }
        }

        void BuildFlatsCard()
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Technical flats", _t);
            var row = new GameObject("Flats", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(card, false);
            var le = row.GetComponent<LayoutElement>();
            le.minHeight = 320f;
            le.preferredHeight = 320f;
            le.flexibleHeight = 0f;
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(10, 10, 10, 10);
            h.spacing = 10f;
            h.childForceExpandWidth = true;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandHeight = true;

            _front = MakeFlatPane(row.transform, "Front view");
            _back = MakeFlatPane(row.transform, "Back view");
        }

        /// <summary>
        /// Fixed-size flat pane. The image is centred with plain anchors and resized once the
        /// texture arrives — no AspectRatioFitter inside the layout chain, so nothing can drive
        /// a rebuild loop while the sheet is being measured.
        /// </summary>
        RawImage MakeFlatPane(Transform parent, string caption)
        {
            var pane = new GameObject(caption, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            pane.transform.SetParent(parent, false);
            pane.GetComponent<Image>().color = Color.white;
            var edge = pane.AddComponent<Outline>();
            edge.effectColor = new Color(_t.PrimaryText.r, _t.PrimaryText.g, _t.PrimaryText.b, 0.2f);
            edge.effectDistance = new Vector2(1f, -1f);
            pane.GetComponent<LayoutElement>().flexibleWidth = 1f;

            var capGo = new GameObject("Cap", typeof(Text));
            capGo.transform.SetParent(pane.transform, false);
            var cap = capGo.GetComponent<Text>();
            cap.font = FrUiFonts.UiMedium;
            cap.text = FrUiFactory.Space(caption.ToUpperInvariant());
            cap.fontSize = Mathf.RoundToInt(_t.OverlineSize);
            cap.color = _t.SecondaryText;
            cap.alignment = TextAnchor.UpperCenter;
            var capRt = capGo.GetComponent<RectTransform>();
            capRt.anchorMin = new Vector2(0f, 1f);
            capRt.anchorMax = new Vector2(1f, 1f);
            capRt.pivot = new Vector2(0.5f, 1f);
            capRt.sizeDelta = new Vector2(0f, 20f);
            capRt.anchoredPosition = new Vector2(0f, -6f);

            var imgGo = new GameObject("Img", typeof(RectTransform), typeof(RawImage));
            var rt = imgGo.GetComponent<RectTransform>();
            rt.SetParent(pane.transform, false);
            rt.anchorMin = new Vector2(0.5f, 0f);
            rt.anchorMax = new Vector2(0.5f, 1f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.offsetMin = new Vector2(-90f, 10f);
            rt.offsetMax = new Vector2(90f, -28f);
            var raw = imgGo.GetComponent<RawImage>();
            raw.texture = null;
            raw.color = Color.white;
            raw.raycastTarget = false;

            var placeholder = new GameObject("Pending", typeof(Text));
            placeholder.transform.SetParent(pane.transform, false);
            var ph = placeholder.GetComponent<Text>();
            ph.font = FrUiFonts.Ui;
            ph.text = "flat pending";
            ph.fontSize = Mathf.RoundToInt(_t.OverlineSize);
            ph.color = new Color(_t.SecondaryText.r, _t.SecondaryText.g, _t.SecondaryText.b, 0.7f);
            ph.alignment = TextAnchor.MiddleCenter;
            var phRt = placeholder.GetComponent<RectTransform>();
            phRt.anchorMin = Vector2.zero;
            phRt.anchorMax = Vector2.one;
            phRt.offsetMin = Vector2.zero;
            phRt.offsetMax = Vector2.zero;
            return raw;
        }

        void BuildMeasurementsCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Sample size base", _t);
            var m = root["measurements"] as JObject;
            AddRow(card, "Sample size", Str(m?["sample_size"], "EU 36 / US 4"));

            FrUiFactory.AddSpecBandRow(card, "Body measurements", _t);
            AddMeasurementRows(card, m?["body"] as JObject);

            FrUiFactory.AddSpecBandRow(card, "Finished garment measurements", _t);
            AddMeasurementRows(card, m?["finished"] as JObject);
        }

        void AddMeasurementRows(Transform card, JObject? obj)
        {
            if (obj == null)
            {
                FrUiFactory.AddSpecParagraph(card, "Not provided.", _t, ContentWidth);
                return;
            }

            var n = 0;
            foreach (var p in obj.Properties())
            {
                if (n++ >= MaxRowsPerTable)
                    break;
                var value = Scalar(p.Value);
                if (string.IsNullOrWhiteSpace(value))
                    continue;
                AddRow(card, PrettyKey(p.Name), FormatCm(p.Name, value));
            }

            if (n == 0)
                FrUiFactory.AddSpecParagraph(card, "Not provided.", _t, ContentWidth);
        }

        void BuildMaterialsCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Materials & notions", _t);
            AddRow3(card, "Item", "Specification", "Qty", true);
            if (root["materials"] is not JArray materials || materials.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No materials returned.", _t, ContentWidth);
                return;
            }

            var n = 0;
            foreach (var mat in materials)
            {
                if (n++ >= MaxRowsPerTable)
                    break;
                var name = Str(mat["name"], "Item");
                var role = Str(mat["role"], "");
                if (!string.IsNullOrEmpty(role))
                    name += "\n" + role;
                var spec = Str(mat["recommendation"], "");
                var notes = Str(mat["notes"], "");
                if (!string.IsNullOrEmpty(notes))
                    spec = string.IsNullOrEmpty(spec) ? notes : spec + "\n" + notes;
                var qty = Number(mat["quantity_m"]);
                var qtyText = qty == null
                    ? "1 pc"
                    : qty.Value.ToString("0.##", CultureInfo.InvariantCulture) + " m";
                AddRow3(card, name, spec, qtyText);
            }
        }

        void BuildPatternCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Pattern pieces", _t);
            if (!string.IsNullOrWhiteSpace(App.CreateDesign.LastTechPackPatternImageUrl))
            {
                var host = new GameObject("PatternArt", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                    typeof(LayoutElement));
                host.transform.SetParent(card, false);
                var hostLe = host.GetComponent<LayoutElement>();
                hostLe.minHeight = 260f;
                hostLe.preferredHeight = 300f;
                hostLe.flexibleWidth = 1f;
                var hostH = host.GetComponent<HorizontalLayoutGroup>();
                hostH.padding = new RectOffset(10, 10, 10, 10);
                hostH.childForceExpandWidth = true;
                hostH.childControlWidth = true;
                hostH.childControlHeight = true;
                _pattern = MakeFlatPane(host.transform, "Pattern draft");
            }
            else
            {
                _pattern = null;
            }

            AddRow3(card, "Piece", "Grain / notches", "Size", true);
            if (root["pattern_pieces"] is not JArray pieces || pieces.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No pattern pieces returned.", _t, ContentWidth);
                return;
            }

            var n = 0;
            foreach (var p in pieces)
            {
                if (n++ >= MaxRowsPerTable)
                    break;
                var name = Str(p["name"], "Piece");
                var qty = Scalar(p["qty"]);
                if (!string.IsNullOrEmpty(qty))
                    name += "\ncut " + qty;

                var detail = new StringBuilder();
                var grain = Str(p["grainline"], "");
                if (!string.IsNullOrEmpty(grain))
                    detail.Append("Grain: ").Append(grain);
                if (p["on_fold"] != null && p["on_fold"]!.Type == JTokenType.Boolean &&
                    p["on_fold"]!.ToObject<bool>())
                    detail.Append(detail.Length > 0 ? " · " : "").Append("place on fold");
                if (p["notches"] is JArray notches && notches.Count > 0)
                {
                    var list = new List<string>();
                    foreach (var notch in notches)
                    {
                        var text = Scalar(notch);
                        if (!string.IsNullOrEmpty(text))
                            list.Add(text);
                    }

                    if (list.Count > 0)
                        detail.Append(detail.Length > 0 ? "\n" : "")
                            .Append("Notches: ")
                            .Append(string.Join(", ", list));
                }

                var sa = Number(p["seam_allowance_cm"]);
                if (sa != null)
                    detail.Append(detail.Length > 0 ? "\n" : "")
                        .Append("SA ")
                        .Append(sa.Value.ToString("0.#", CultureInfo.InvariantCulture))
                        .Append(" cm");

                var w = FirstNumber(p, "approx_w_cm", "width_cm");
                var hgt = FirstNumber(p, "approx_h_cm", "height_cm");
                var size = w != null && hgt != null
                    ? $"{w.Value.ToString("0.#", CultureInfo.InvariantCulture)} × " +
                      $"{hgt.Value.ToString("0.#", CultureInfo.InvariantCulture)} cm"
                    : "—";

                AddRow3(card, name, detail.ToString(), size);
            }
        }

        void BuildCuttingCard(JObject root)
        {
            if (root["cutting_layout"] is not JObject cutting)
                return;
            var card = FrUiFactory.AddSpecCard(_sheet, "Cutting layout", _t);
            var width = Number(cutting["fabric_width_cm"]);
            AddRow(card, "Fabric width",
                (width?.ToString("0.#", CultureInfo.InvariantCulture) ?? "150") + " cm");
            var notes = Str(cutting["notes"], "");
            if (!string.IsNullOrEmpty(notes))
                FrUiFactory.AddSpecParagraph(card, Clamp(notes, MaxParagraphChars), _t, ContentWidth);
            var tip = Str(cutting["efficiency_tip"], "");
            if (!string.IsNullOrEmpty(tip))
                FrUiFactory.AddSpecParagraph(card, "Tip: " + Clamp(tip, MaxParagraphChars), _t, ContentWidth);
        }

        void BuildConstructionCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Construction order", _t);
            if (root["construction_steps"] is not JArray steps || steps.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No construction steps returned.", _t, ContentWidth);
                return;
            }

            var i = 1;
            foreach (var s in steps)
            {
                if (i > MaxRowsPerTable)
                    break;
                var text = Scalar(s).Trim();
                if (string.IsNullOrEmpty(text))
                    continue;
                FrUiFactory.AddSpecParagraph(card, i + ".  " + Clamp(text, MaxParagraphChars), _t, ContentWidth);
                FrUiFactory.AddHairline(card, _t);
                i++;
            }
        }

        void BuildSpecialCard(JObject root)
        {
            if (root["special_instructions"] is not JArray special || special.Count == 0)
                return;
            var card = FrUiFactory.AddSpecCard(_sheet, "Special construction", _t);
            FrUiFactory.AddSpecParagraph(card,
                "Unusual shapes (puff sleeves, pods, sculptural volume) — first-draft notes for a pattern maker.",
                _t, ContentWidth);
            var i = 1;
            foreach (var s in special)
            {
                if (i > MaxRowsPerTable)
                    break;
                var text = Scalar(s).Trim();
                if (string.IsNullOrEmpty(text))
                    continue;
                FrUiFactory.AddSpecParagraph(card, i + ".  " + Clamp(text, MaxParagraphChars), _t, ContentWidth);
                FrUiFactory.AddHairline(card, _t);
                i++;
            }
        }

        void ShowError(string message)
        {
            ClearSheet();
            if (_sheet == null)
                return;
            var card = FrUiFactory.AddSpecCard(_sheet, "Could not build the tech pack", _t);
            FrUiFactory.AddSpecParagraph(card, Clamp(message, MaxParagraphChars), _t, ContentWidth);
            FrUiFactory.AddSpecParagraph(card,
                "Check that the studio API is running and you are signed in, then tap Regenerate. " +
                "A full log of this run is in fashionrise-diag.log.", _t, ContentWidth);
        }

        // ---------- row helpers ----------

        void AddRow(Transform card, string label, string value) =>
            FrUiFactory.AddSpecRow(card, Clamp(label, MaxCellChars), Clamp(value, MaxCellChars), _t, ContentWidth);

        void AddRow3(Transform card, string a, string b, string c, bool header = false) =>
            FrUiFactory.AddSpecRow3(card, Clamp(a, MaxCellChars), Clamp(b, MaxCellChars), Clamp(c, MaxCellChars),
                _t, ContentWidth, header);

        void AddIfPresent(Transform card, string label, JToken? token)
        {
            var value = Str(token, "");
            if (!string.IsNullOrEmpty(value))
                AddRow(card, label, value);
        }

        static void SafeSet(Text? target, string text)
        {
            if (target != null)
                target.text = text;
        }

        static string Clamp(string? text, int max)
        {
            var s = text ?? "";
            return s.Length <= max ? s : s.Substring(0, max - 1) + "…";
        }

        /// <summary>Scalar text for a token; objects/arrays never leak into a table cell.</summary>
        static string Scalar(JToken? token)
        {
            if (token == null)
                return "";
            return token.Type switch
            {
                JTokenType.Null => "",
                JTokenType.Object => "",
                JTokenType.Array => "",
                _ => token.ToString()
            };
        }

        static float? Number(JToken? token)
        {
            var s = Scalar(token);
            return float.TryParse(s, NumberStyles.Any, CultureInfo.InvariantCulture, out var v) ? v : null;
        }

        static float? FirstNumber(JToken parent, params string[] keys)
        {
            foreach (var k in keys)
            {
                var v = Number(parent[k]);
                if (v != null)
                    return v;
            }

            return null;
        }

        static string Str(JToken? token, string fallback)
        {
            var s = Scalar(token).Trim();
            return string.IsNullOrEmpty(s) ? fallback : s;
        }

        static string PrettyKey(string key)
        {
            var clean = key.Replace("_cm", "").Replace('_', ' ').Trim();
            if (clean.Length == 0)
                return key;
            return char.ToUpperInvariant(clean[0]) + clean.Substring(1);
        }

        static string FormatCm(string key, string value) =>
            key.EndsWith("_cm", StringComparison.OrdinalIgnoreCase) &&
            !value.EndsWith("cm", StringComparison.OrdinalIgnoreCase)
                ? value + " cm"
                : value;

        static string ShortCode(string jobId)
        {
            if (string.IsNullOrWhiteSpace(jobId))
                return "001";
            var clean = jobId.Replace("-", "");
            return clean.Length <= 4 ? clean.ToUpperInvariant() : clean.Substring(0, 4).ToUpperInvariant();
        }

        // ---------- export + flats ----------

        void ExportSpec()
        {
            var pdfUrl = App.CreateDesign.LastTechPackPdfUrl?.Trim() ?? "";
            if (!string.IsNullOrEmpty(pdfUrl))
            {
                _ = OpenPdfAsync(pdfUrl);
                return;
            }

            var json = App.CreateDesign.LastTechPackJson;
            if (string.IsNullOrWhiteSpace(json))
                return;

            try
            {
                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "TechPacks");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"techpack_{DateTime.UtcNow:yyyyMMdd_HHmmss}.json");
                File.WriteAllText(path, json);
                if (!NativeShareSheet.TryShareText("FashionRise tech pack: " + path, "FashionRise tech pack"))
                    ShareClipboard.Copy(json);
                FrDiag.Step($"techpack: exported {path}");
            }
            catch (Exception ex)
            {
                ShareClipboard.Copy(json);
                FrDiag.Fail("techpack export", ex);
            }
        }

        async Task OpenPdfAsync(string url)
        {
            try
            {
                var loadUrl = RewriteToApiHost(url);
                using var req = UnityWebRequest.Get(loadUrl);
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32).ConfigureAwait(true);
                if (req.result != UnityWebRequest.Result.Success || req.downloadHandler.data == null ||
                    req.downloadHandler.data.Length < 8)
                {
                    UnityEngine.Application.OpenURL(loadUrl);
                    return;
                }

                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "TechPacks");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"techpack_{DateTime.UtcNow:yyyyMMdd_HHmmss}.pdf");
                File.WriteAllBytes(path, req.downloadHandler.data);
                UnityEngine.Application.OpenURL("file:///" + path.Replace("\\", "/"));
                Debug.Log($"FashionRise tech pack PDF saved {path}");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise PDF export failed: {ex.Message}");
                UnityEngine.Application.OpenURL(RewriteToApiHost(url));
            }
        }

        async Task LoadFlatsAsync(CancellationToken ct)
        {
            var front = await LoadFlatAsync(_front, _ownedFront, App.CreateDesign.LastTechPackFrontImageUrl, ct)
                .ConfigureAwait(true);
            if (front != null)
                _ownedFront = front;
            var back = await LoadFlatAsync(_back, _ownedBack, App.CreateDesign.LastTechPackBackImageUrl, ct)
                .ConfigureAwait(true);
            if (back != null)
                _ownedBack = back;
            if (_pattern != null)
            {
                var pattern = await LoadFlatAsync(_pattern, _ownedPattern, App.CreateDesign.LastTechPackPatternImageUrl, ct)
                    .ConfigureAwait(true);
                if (pattern != null)
                    _ownedPattern = pattern;
            }
        }

        async Task<Texture2D?> LoadFlatAsync(RawImage? target, Texture2D? previous, string url, CancellationToken ct)
        {
            if (string.IsNullOrWhiteSpace(url))
                return null;
            try
            {
                using var req = UnityWebRequestTexture.GetTexture(RewriteToApiHost(url));
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32, ct).ConfigureAwait(true);
                if (req.result != UnityWebRequest.Result.Success)
                {
                    FrDiag.Trace($"techpack flat {url} failed: {req.error}");
                    return null;
                }

                var tex = DownloadHandlerTexture.GetContent(req);
                if (tex == null)
                    return null;
                if (target == null)
                {
                    Destroy(tex);
                    return null;
                }

                if (previous != null)
                    Destroy(previous);
                target.texture = tex;
                FitFlat(target, tex);
                var pending = target.transform.parent != null
                    ? target.transform.parent.Find("Pending")
                    : null;
                if (pending != null)
                    pending.gameObject.SetActive(false);
                return tex;
            }
            catch (OperationCanceledException)
            {
                return null;
            }
            catch (Exception ex)
            {
                FrDiag.Fail("techpack flat load", ex);
                return null;
            }
        }

        /// <summary>Centres the flat at the pane height without touching the layout system.</summary>
        static void FitFlat(RawImage target, Texture2D tex)
        {
            var rt = target.rectTransform;
            var pane = rt.parent as RectTransform;
            if (pane == null || tex.height <= 0)
                return;
            var paneH = Mathf.Max(80f, pane.rect.height - 38f);
            var paneW = Mathf.Max(80f, pane.rect.width - 16f);
            var aspect = tex.width / (float)tex.height;
            var h = paneH;
            var w = h * aspect;
            if (w > paneW)
            {
                w = paneW;
                h = w / Mathf.Max(0.05f, aspect);
            }

            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(0f, -6f);
        }

        string RewriteToApiHost(string url)
        {
            if (string.IsNullOrWhiteSpace(url) || string.IsNullOrWhiteSpace(App.ApiBaseUrl))
                return url;
            try
            {
                var apiUri = new Uri(App.ApiBaseUrl.TrimEnd('/') + "/");
                var imgUri = new Uri(url);
                if (!string.Equals(imgUri.Host, "localhost", StringComparison.OrdinalIgnoreCase) &&
                    imgUri.Host != "127.0.0.1")
                    return url;
                return new UriBuilder(imgUri)
                {
                    Scheme = apiUri.Scheme,
                    Host = apiUri.Host,
                    Port = apiUri.IsDefaultPort ? -1 : apiUri.Port
                }.Uri.ToString();
            }
            catch
            {
                return url;
            }
        }

        void OnDestroy()
        {
            CancelWork();
            _life.Cancel();
            _life.Dispose();
            _cts?.Dispose();
            if (_ownedFront != null)
                Destroy(_ownedFront);
            if (_ownedBack != null)
                Destroy(_ownedBack);
            if (_ownedPattern != null)
                Destroy(_ownedPattern);
        }
    }
}
